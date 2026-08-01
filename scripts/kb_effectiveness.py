#!/usr/bin/env python3
"""Record and report whether the cross-tool KB improves engineering outcomes.

Receipts are append-only evidence. This module never mutates KittyBuilder, opens
issues, changes the roadmap, or claims causation from a correlation. Unknown
measurements remain null rather than being converted into reassuring zeroes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
DEFAULT_WINDOW_DAYS = 30
EXECUTION_OWNERS = frozenset({"interactive", "builder"})
OUTCOMES = frozenset(
    {
        "accepted",
        "completed_unreviewed",
        "blocked",
        "failed",
        "cancelled",
        "no_op",
    }
)
NULLABLE_NONNEGATIVE_INTS = frozenset(
    {
        "kb_tokens_loaded",
        "total_tokens",
        "elapsed_seconds",
        "attempts",
        "repair_commits",
        "regressions",
    }
)
NULLABLE_BOOLEANS = frozenset(
    {"first_pass_approved", "duplicate_work_avoided", "correction_prevented"}
)
OPTIONAL_TEXT = frozenset(
    {
        "result_id",
        "task_id",
        "initiative_id",
        "packet_id",
        "branch",
        "head_sha",
        "notes",
    }
)
REQUIRED_LISTS = frozenset(
    {
        "kb_entries_consulted",
        "kb_entries_used",
        "kb_entries_stale_or_wrong",
        "promoted_to_canonical",
    }
)


class ReceiptError(ValueError):
    """Raised when a receipt or receipt store is invalid."""


@dataclass(frozen=True)
class Store:
    path: Path
    scope: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ReceiptError(f"{field} must be a non-empty ISO-8601 string")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ReceiptError(f"{field} is not valid ISO-8601: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ReceiptError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def resolve_store(
    *,
    explicit_path: Path | None = None,
    kb_root: Path | None = None,
    repo_root: Path | None = None,
) -> Store:
    if explicit_path is not None:
        return Store(explicit_path.expanduser(), "explicit")
    kb = (kb_root or (Path.home() / "kb")).expanduser()
    if kb.is_dir():
        return Store(kb / "metrics" / "kb-effectiveness.jsonl", "kb")
    repo = (repo_root or Path.cwd()).resolve()
    return Store(
        repo / "docs" / "session-notes" / "kb-effectiveness.jsonl",
        "repo-fallback",
    )


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReceiptError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ReceiptError(f"{key} must be null or a non-empty string")
    return value.strip()


def _string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ReceiptError(f"{key} must be a JSON array of unique strings")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ReceiptError(f"{key} must contain only non-empty strings")
        normalized.append(item.strip())
    if len(normalized) != len(set(normalized)):
        raise ReceiptError(f"{key} must not contain duplicates")
    return normalized


def _nullable_nonnegative_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReceiptError(f"{key} must be null or a non-negative integer")
    return value


def _nullable_bool(payload: dict[str, Any], key: str) -> bool | None:
    value = payload.get(key)
    if value is not None and not isinstance(value, bool):
        raise ReceiptError(f"{key} must be null or a boolean")
    return value


def validate_payload(payload: Any, *, now: datetime | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ReceiptError("receipt payload must be a JSON object")

    allowed = {
        "schema_version",
        "session_id",
        "recorded_at",
        "execution_owner",
        "tool",
        "task_class",
        "outcome",
        *REQUIRED_LISTS,
        *NULLABLE_NONNEGATIVE_INTS,
        *NULLABLE_BOOLEANS,
        *OPTIONAL_TEXT,
        "estimated_cost_usd",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ReceiptError(f"unknown receipt keys: {unknown}")

    schema_version = payload.get("schema_version", SCHEMA_VERSION)
    if schema_version != SCHEMA_VERSION:
        raise ReceiptError(
            f"schema_version must be {SCHEMA_VERSION}, got {schema_version!r}"
        )

    owner = _require_text(payload, "execution_owner")
    if owner not in EXECUTION_OWNERS:
        raise ReceiptError(
            f"execution_owner must be one of {sorted(EXECUTION_OWNERS)}"
        )

    outcome = _require_text(payload, "outcome")
    if outcome not in OUTCOMES:
        raise ReceiptError(f"outcome must be one of {sorted(OUTCOMES)}")

    recorded_at_raw = payload.get("recorded_at")
    recorded_at = (
        (now or utc_now()).astimezone(timezone.utc)
        if recorded_at_raw is None
        else parse_timestamp(recorded_at_raw, field="recorded_at")
    )

    lists = {key: _string_list(payload, key) for key in REQUIRED_LISTS}
    consulted = set(lists["kb_entries_consulted"])
    used = set(lists["kb_entries_used"])
    stale = set(lists["kb_entries_stale_or_wrong"])
    if not used.issubset(consulted):
        raise ReceiptError("kb_entries_used must be a subset of consulted entries")
    if not stale.issubset(consulted):
        raise ReceiptError(
            "kb_entries_stale_or_wrong must be a subset of consulted entries"
        )
    if used & stale:
        raise ReceiptError(
            "an entry cannot be both useful and stale/wrong in the same receipt"
        )

    estimated_cost = payload.get("estimated_cost_usd")
    if estimated_cost is not None:
        if isinstance(estimated_cost, bool) or not isinstance(
            estimated_cost, (int, float)
        ) or estimated_cost < 0:
            raise ReceiptError(
                "estimated_cost_usd must be null or a non-negative number"
            )
        estimated_cost = float(estimated_cost)

    optional = {key: _optional_text(payload, key) for key in OPTIONAL_TEXT}
    head_sha = optional["head_sha"]
    if head_sha is not None and (
        len(head_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in head_sha)
    ):
        raise ReceiptError("head_sha must be null or a 40-character hexadecimal SHA")

    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": _require_text(payload, "session_id"),
        "recorded_at": recorded_at.isoformat().replace("+00:00", "Z"),
        "execution_owner": owner,
        "tool": _require_text(payload, "tool"),
        "task_class": _require_text(payload, "task_class"),
        "outcome": outcome,
        **lists,
        **{
            key: _nullable_nonnegative_int(payload, key)
            for key in sorted(NULLABLE_NONNEGATIVE_INTS)
        },
        **{
            key: _nullable_bool(payload, key)
            for key in sorted(NULLABLE_BOOLEANS)
        },
        **optional,
        "estimated_cost_usd": estimated_cost,
    }


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def receipt_id(payload: dict[str, Any]) -> str:
    return "kbr_" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()[:20]


def _validate_stored_receipt(raw: Any, *, location: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ReceiptError(f"receipt at {location} must be a JSON object")
    expected_keys = {"receipt_id", "store_scope", "receipt"}
    unknown = sorted(set(raw) - expected_keys)
    missing = sorted(expected_keys - set(raw))
    if unknown or missing:
        raise ReceiptError(
            f"receipt at {location} has unknown={unknown} missing={missing}"
        )
    normalized = validate_payload(raw["receipt"])
    expected_id = receipt_id(normalized)
    if raw["receipt_id"] != expected_id:
        raise ReceiptError(
            f"receipt at {location} has id {raw['receipt_id']!r}; expected {expected_id!r}"
        )
    if not isinstance(raw["store_scope"], str) or not raw["store_scope"]:
        raise ReceiptError(f"receipt at {location} has invalid store_scope")
    return {"receipt_id": expected_id, "store_scope": raw["store_scope"], "receipt": normalized}


def load_receipts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if not path.is_file():
        raise ReceiptError(f"receipt store is not a file: {path}")
    receipts: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ReceiptError(f"blank line in receipt store at {path}:{line_no}")
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReceiptError(
                f"invalid JSON in receipt store at {path}:{line_no}: {exc}"
            ) from exc
        receipts.append(
            _validate_stored_receipt(raw, location=f"{path}:{line_no}")
        )
    return receipts


def record_receipt(
    raw_payload: Any,
    *,
    store: Store,
    now: datetime | None = None,
) -> dict[str, Any]:
    normalized = validate_payload(raw_payload, now=now)
    rid = receipt_id(normalized)
    existing = load_receipts(store.path)
    for item in existing:
        receipt = item["receipt"]
        if item["receipt_id"] == rid:
            return {"created": False, "path": str(store.path), **item}
        if receipt["session_id"] == normalized["session_id"]:
            raise ReceiptError(
                "session_id already exists with different receipt content: "
                f"{normalized['session_id']}"
            )

    stored = {"receipt_id": rid, "store_scope": store.scope, "receipt": normalized}
    store.path.parent.mkdir(parents=True, exist_ok=True)
    with store.path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(stored, sort_keys=True, ensure_ascii=False) + "\n")
    return {"created": True, "path": str(store.path), **stored}


def _in_window(receipt: dict[str, Any], *, now: datetime, days: int) -> bool:
    recorded = parse_timestamp(receipt["recorded_at"], field="recorded_at")
    return now - timedelta(days=days) <= recorded <= now + timedelta(minutes=5)


def _safe_rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _cohort_summary(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [item for item in receipts if item["outcome"] == "accepted"]
    known_tokens = [
        item["total_tokens"]
        for item in accepted
        if item["total_tokens"] is not None
    ]
    known_attempts = [
        item["attempts"] for item in accepted if item["attempts"] is not None
    ]
    first_pass = [
        item["first_pass_approved"]
        for item in receipts
        if item["first_pass_approved"] is not None
    ]
    return {
        "sessions": len(receipts),
        "accepted_results": len(accepted),
        "accepted_rate": _safe_rate(len(accepted), len(receipts)),
        "tokens_known_accepted_results": len(known_tokens),
        "median_tokens_per_accepted_result": (
            statistics.median(known_tokens) if known_tokens else None
        ),
        "attempts_known_accepted_results": len(known_attempts),
        "average_attempts_per_accepted_result": (
            round(statistics.mean(known_attempts), 4) if known_attempts else None
        ),
        "first_pass_known": len(first_pass),
        "first_pass_approval_rate": (
            _safe_rate(sum(value is True for value in first_pass), len(first_pass))
        ),
        "sample_too_small": len(accepted) < 5,
    }


def summarize_receipts(
    stored_receipts: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict[str, Any]:
    if window_days < 1:
        raise ReceiptError("window_days must be >= 1")
    generated_at = (now or utc_now()).astimezone(timezone.utc)
    receipts = [
        item["receipt"]
        for item in stored_receipts
        if _in_window(item["receipt"], now=generated_at, days=window_days)
    ]

    consulted = sum(len(item["kb_entries_consulted"]) for item in receipts)
    used = sum(len(item["kb_entries_used"]) for item in receipts)
    stale = sum(len(item["kb_entries_stale_or_wrong"]) for item in receipts)
    accepted = [item for item in receipts if item["outcome"] == "accepted"]
    known_total_tokens = [
        item["total_tokens"] for item in receipts if item["total_tokens"] is not None
    ]
    known_kb_tokens = [
        item["kb_tokens_loaded"]
        for item in receipts
        if item["kb_tokens_loaded"] is not None
    ]
    known_costs = [
        item["estimated_cost_usd"]
        for item in receipts
        if item["estimated_cost_usd"] is not None
    ]
    first_pass = [
        item["first_pass_approved"]
        for item in receipts
        if item["first_pass_approved"] is not None
    ]
    attempts = [item["attempts"] for item in receipts if item["attempts"] is not None]
    repairs = [
        item["repair_commits"]
        for item in receipts
        if item["repair_commits"] is not None
    ]
    regressions = [
        item["regressions"] for item in receipts if item["regressions"] is not None
    ]

    kb_used_receipts = [item for item in receipts if item["kb_entries_used"]]
    kb_not_used_receipts = [item for item in receipts if not item["kb_entries_used"]]

    gaps: list[str] = []
    if not receipts:
        gaps.append("no receipts in the selected window")
    if len(known_total_tokens) < len(receipts):
        gaps.append("total token counts are incomplete")
    if len(known_kb_tokens) < sum(bool(item["kb_entries_consulted"]) for item in receipts):
        gaps.append("KB context token counts are incomplete")
    if not first_pass:
        gaps.append("no independent first-pass review outcomes are recorded")
    if len(accepted) < 10:
        gaps.append("fewer than 10 independently accepted results are recorded")
    if len(kb_used_receipts) < 5 or len(kb_not_used_receipts) < 5:
        gaps.append("KB-used versus no-KB cohorts are too small for a useful comparison")
    gaps.append("cohort differences are observational and do not prove causation")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "window_days": window_days,
        "sessions": len(receipts),
        "execution_owners": dict(Counter(item["execution_owner"] for item in receipts)),
        "tools": dict(Counter(item["tool"] for item in receipts)),
        "task_classes": dict(Counter(item["task_class"] for item in receipts)),
        "outcomes": dict(Counter(item["outcome"] for item in receipts)),
        "accepted_results": len(accepted),
        "kb_retrieval": {
            "sessions_with_consultation": sum(
                bool(item["kb_entries_consulted"]) for item in receipts
            ),
            "entries_consulted": consulted,
            "entries_used": used,
            "entries_stale_or_wrong": stale,
            "usefulness_rate": _safe_rate(used, consulted),
            "stale_or_wrong_rate": _safe_rate(stale, consulted),
            "promotions_to_canonical": sum(
                len(item["promoted_to_canonical"]) for item in receipts
            ),
        },
        "efficiency": {
            "total_tokens_known_sessions": len(known_total_tokens),
            "total_tokens": sum(known_total_tokens),
            "kb_tokens_known_sessions": len(known_kb_tokens),
            "kb_tokens_loaded": sum(known_kb_tokens),
            "estimated_cost_known_sessions": len(known_costs),
            "estimated_cost_usd": round(sum(known_costs), 6),
            "attempts_known_sessions": len(attempts),
            "average_attempts": round(statistics.mean(attempts), 4) if attempts else None,
            "repair_commits_known_sessions": len(repairs),
            "repair_commits": sum(repairs),
        },
        "quality": {
            "first_pass_known": len(first_pass),
            "first_pass_approved": sum(value is True for value in first_pass),
            "first_pass_approval_rate": _safe_rate(
                sum(value is True for value in first_pass), len(first_pass)
            ),
            "regressions_known_sessions": len(regressions),
            "regressions": sum(regressions),
            "duplicate_work_avoided": sum(
                item["duplicate_work_avoided"] is True for item in receipts
            ),
            "corrections_prevented": sum(
                item["correction_prevented"] is True for item in receipts
            ),
        },
        "cohorts": {
            "kb_used": _cohort_summary(kb_used_receipts),
            "kb_not_used": _cohort_summary(kb_not_used_receipts),
            "interpretation": "observational comparison only; not causal",
        },
        "insufficient_evidence": gaps,
    }


def render_report(summary: dict[str, Any]) -> str:
    retrieval = summary["kb_retrieval"]
    efficiency = summary["efficiency"]
    quality = summary["quality"]
    cohorts = summary["cohorts"]

    lines = [
        "# KB effectiveness report",
        "",
        f"Generated: {summary['generated_at']}",
        f"Window: {summary['window_days']} days",
        f"Sessions recorded: {summary['sessions']}",
        f"Independently accepted results: {summary['accepted_results']}",
        "",
        "## Retrieval quality",
        "",
        f"- Entries consulted: {retrieval['entries_consulted']}",
        f"- Entries used: {retrieval['entries_used']}",
        f"- Entries stale or wrong: {retrieval['entries_stale_or_wrong']}",
        f"- Usefulness rate: {retrieval['usefulness_rate']}",
        f"- Stale/wrong rate: {retrieval['stale_or_wrong_rate']}",
        f"- Promoted to canonical artifacts: {retrieval['promotions_to_canonical']}",
        "",
        "## Efficiency evidence",
        "",
        f"- Sessions with known total tokens: {efficiency['total_tokens_known_sessions']}",
        f"- Total known tokens: {efficiency['total_tokens']}",
        f"- Sessions with known KB tokens: {efficiency['kb_tokens_known_sessions']}",
        f"- Known KB tokens loaded: {efficiency['kb_tokens_loaded']}",
        f"- Estimated known cost (USD): {efficiency['estimated_cost_usd']}",
        f"- Average attempts where known: {efficiency['average_attempts']}",
        "",
        "## Quality evidence",
        "",
        f"- First-pass review outcomes known: {quality['first_pass_known']}",
        f"- First-pass approval rate: {quality['first_pass_approval_rate']}",
        f"- Regressions where known: {quality['regressions']}",
        f"- Duplicate work avoided: {quality['duplicate_work_avoided']}",
        f"- Corrections prevented: {quality['corrections_prevented']}",
        "",
        "## KB-used versus no-KB cohorts",
        "",
        "This comparison is observational only and does not prove causation.",
        "",
    ]
    for name in ("kb_used", "kb_not_used"):
        cohort = cohorts[name]
        lines.extend(
            [
                f"### {name.replace('_', ' ').title()}",
                f"- Sessions: {cohort['sessions']}",
                f"- Accepted results: {cohort['accepted_results']}",
                f"- Accepted rate: {cohort['accepted_rate']}",
                f"- Median tokens per accepted result: {cohort['median_tokens_per_accepted_result']}",
                f"- Average attempts per accepted result: {cohort['average_attempts_per_accepted_result']}",
                f"- First-pass approval rate: {cohort['first_pass_approval_rate']}",
                f"- Sample too small: {cohort['sample_too_small']}",
                "",
            ]
        )
    lines.extend(["## Evidence gaps", ""])
    lines.extend(f"- {gap}" for gap in summary["insufficient_evidence"])
    return "\n".join(lines) + "\n"


def _load_payload(args: argparse.Namespace) -> Any:
    if bool(args.payload_json) == bool(args.payload_file):
        raise ReceiptError("provide exactly one of --payload-json or --payload-file")
    if args.payload_json:
        try:
            return json.loads(args.payload_json)
        except json.JSONDecodeError as exc:
            raise ReceiptError(f"--payload-json is invalid JSON: {exc}") from exc
    try:
        return json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReceiptError(f"cannot read payload file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ReceiptError(f"payload file is invalid JSON: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--kb-root", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    record = subparsers.add_parser("record", help="validate and append one receipt")
    record.add_argument("--payload-json")
    record.add_argument("--payload-file", type=Path)

    summary = subparsers.add_parser("summary", help="summarize recent receipts")
    summary.add_argument("--report", action="store_true")
    summary.add_argument("--out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = resolve_store(
            explicit_path=args.store,
            kb_root=args.kb_root,
            repo_root=args.repo_root,
        )
        if args.command == "record":
            result: Any = record_receipt(_load_payload(args), store=store)
            output = json.dumps(result, indent=2, sort_keys=True)
        else:
            summary = {
                "store": str(store.path),
                "store_scope": store.scope,
                **summarize_receipts(
                    load_receipts(store.path), window_days=args.window_days
                ),
            }
            if args.report:
                output = render_report(summary)
                if args.out:
                    args.out.parent.mkdir(parents=True, exist_ok=True)
                    args.out.write_text(output, encoding="utf-8")
            else:
                output = json.dumps(summary, indent=2, sort_keys=True)
    except ReceiptError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(output, end="" if output.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
