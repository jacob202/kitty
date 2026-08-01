#!/usr/bin/env python3
"""Record and summarize cross-tool workflow-learning signals.

The script writes observations to the existing cross-tool knowledge base under
``~/kb/workflow-signals``. It does not create Builder tasks, mutate the Builder
queue, edit the roadmap, or decide that an annoyance deserves engineering work.

Promotion is deliberately conservative:

- an integrity/safety incident is promoted immediately;
- any critical signal is promoted immediately;
- an ordinary signal is promoted only after the same stable key appears in at
  least two sessions within the rolling window.

Session-end owns extraction from the conversation. This module owns validation,
stable identity, repeat counting, and a machine-readable summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
DEFAULT_WINDOW_DAYS = 30

CATEGORIES = frozenset(
    {
        "architecture_boundary",
        "collision",
        "data_loss_risk",
        "duplicate_work",
        "fabricated_success",
        "manual_repetition",
        "missing_automation",
        "paid_waste",
        "provider_failure",
        "queue_integrity",
        "runtime_failure",
        "security_boundary",
        "stale_context",
        "test_gap",
        "tool_failure",
        "unverified_claim",
        "user_correction",
    }
)
SEVERITIES = frozenset({"low", "medium", "high", "critical"})
SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
IMMEDIATE_CATEGORIES = frozenset(
    {
        "data_loss_risk",
        "fabricated_success",
        "paid_waste",
        "queue_integrity",
        "security_boundary",
    }
)
_STABLE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")


class SignalError(ValueError):
    """Raised when a learning signal or existing signal store is invalid."""


@dataclass(frozen=True)
class Store:
    root: Path
    scope: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise SignalError(f"{field} must be a non-empty ISO-8601 string")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SignalError(f"{field} is not valid ISO-8601: {value!r}") from exc
    if parsed.tzinfo is None:
        raise SignalError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def resolve_store(
    *,
    kb_root: Path | None = None,
    repo_root: Path | None = None,
) -> Store:
    kb = (kb_root or (Path.home() / "kb")).expanduser()
    if kb.is_dir():
        return Store(kb / "workflow-signals", "kb")
    repo = (repo_root or Path.cwd()).resolve()
    return Store(repo / "docs" / "session-notes" / "workflow-signals", "repo-fallback")


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SignalError(f"{key} must be a non-empty string")
    return value.strip()


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SignalError("signal payload must be a JSON object")

    allowed = {
        "stable_key",
        "category",
        "severity",
        "summary",
        "evidence",
        "impact",
        "suggested_change",
        "source_session",
        "verified_by",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise SignalError(f"unknown signal keys: {unknown}")

    stable_key = _require_text(payload, "stable_key")
    if not _STABLE_KEY_RE.fullmatch(stable_key):
        raise SignalError(
            "stable_key must be 3-80 lowercase letters, digits, or hyphens"
        )

    category = _require_text(payload, "category")
    if category not in CATEGORIES:
        raise SignalError(
            f"category must be one of {sorted(CATEGORIES)}, got {category!r}"
        )

    severity = _require_text(payload, "severity")
    if severity not in SEVERITIES:
        raise SignalError(
            f"severity must be one of {sorted(SEVERITIES)}, got {severity!r}"
        )

    normalized = {
        "stable_key": stable_key,
        "category": category,
        "severity": severity,
        "summary": _require_text(payload, "summary"),
        "evidence": _require_text(payload, "evidence"),
        "impact": _require_text(payload, "impact"),
        "suggested_change": _require_text(payload, "suggested_change"),
        "source_session": _require_text(payload, "source_session"),
        "verified_by": _require_text(payload, "verified_by"),
    }
    return normalized


def fingerprint(stable_key: str) -> str:
    return hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:16]


def _load_signal(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SignalError(f"cannot read signal {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SignalError(f"signal {path} is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SignalError(f"signal {path} must contain a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SignalError(
            f"signal {path} has unsupported schema_version "
            f"{payload.get('schema_version')!r}"
        )
    for key in (
        "stable_key",
        "fingerprint",
        "recorded_at",
        "category",
        "severity",
        "summary",
        "evidence",
        "impact",
        "suggested_change",
        "source_session",
        "verified_by",
        "promotion_status",
        "promotion_reason",
        "occurrence_count",
        "store_scope",
    ):
        if key not in payload:
            raise SignalError(f"signal {path} is missing {key!r}")
    parse_timestamp(payload["recorded_at"], field=f"{path}:recorded_at")
    return payload


def load_signals(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    if not root.is_dir():
        raise SignalError(f"signal store is not a directory: {root}")
    return [_load_signal(path) for path in sorted(root.glob("*.json"))]


def _in_window(
    signal: dict[str, Any], *, now: datetime, window: timedelta
) -> bool:
    recorded = parse_timestamp(signal["recorded_at"], field="recorded_at")
    return now - window <= recorded <= now + timedelta(minutes=5)


def promotion_decision(
    *,
    category: str,
    severity: str,
    occurrence_count: int,
) -> tuple[str, str]:
    if category in IMMEDIATE_CATEGORIES:
        return "promote", f"{category} is an immediate integrity/cost boundary"
    if severity == "critical":
        return "promote", "critical severity"
    if occurrence_count >= 2:
        return "promote", f"repeated in {occurrence_count} sessions within the window"
    return "observe", "single non-critical observation; collect another occurrence"


def record_signal(
    raw_payload: Any,
    *,
    store: Store,
    now: datetime | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict[str, Any]:
    payload = validate_payload(raw_payload)
    observed_at = (now or utc_now()).astimezone(timezone.utc)
    if window_days < 1:
        raise SignalError("window_days must be >= 1")

    existing = load_signals(store.root)
    window = timedelta(days=window_days)
    occurrence_count = 1 + sum(
        1
        for signal in existing
        if signal.get("stable_key") == payload["stable_key"]
        and _in_window(signal, now=observed_at, window=window)
    )
    status, reason = promotion_decision(
        category=payload["category"],
        severity=payload["severity"],
        occurrence_count=occurrence_count,
    )
    fp = fingerprint(payload["stable_key"])
    timestamp = observed_at.strftime("%Y%m%dT%H%M%SZ")
    record = {
        "schema_version": SCHEMA_VERSION,
        "id": f"wfs_{timestamp.lower()}_{fp}",
        "fingerprint": fp,
        "recorded_at": observed_at.isoformat().replace("+00:00", "Z"),
        **payload,
        "occurrence_count": occurrence_count,
        "promotion_status": status,
        "promotion_reason": reason,
        "store_scope": store.scope,
    }

    store.root.mkdir(parents=True, exist_ok=True)
    path = store.root / f"{timestamp}-{payload['stable_key']}.json"
    if path.exists():
        raise SignalError(f"refusing to overwrite existing signal: {path}")
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(path), "signal": record}


def summarize_signals(
    signals: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict[str, Any]:
    observed_at = (now or utc_now()).astimezone(timezone.utc)
    if window_days < 1:
        raise SignalError("window_days must be >= 1")
    window = timedelta(days=window_days)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        if _in_window(signal, now=observed_at, window=window):
            grouped[str(signal["stable_key"])].append(signal)

    items: list[dict[str, Any]] = []
    for stable_key, entries in grouped.items():
        latest = max(
            entries,
            key=lambda item: parse_timestamp(item["recorded_at"], field="recorded_at"),
        )
        max_severity = max(
            (str(item["severity"]) for item in entries),
            key=lambda severity: SEVERITY_RANK[severity],
        )
        status, reason = promotion_decision(
            category=str(latest["category"]),
            severity=max_severity,
            occurrence_count=len(entries),
        )
        items.append(
            {
                "stable_key": stable_key,
                "fingerprint": fingerprint(stable_key),
                "category": latest["category"],
                "severity": max_severity,
                "occurrence_count": len(entries),
                "last_recorded_at": latest["recorded_at"],
                "summary": latest["summary"],
                "suggested_change": latest["suggested_change"],
                "promotion_status": status,
                "promotion_reason": reason,
            }
        )

    items.sort(
        key=lambda item: (
            item["promotion_status"] == "promote",
            SEVERITY_RANK[str(item["severity"])],
            int(item["occurrence_count"]),
            str(item["last_recorded_at"]),
        ),
        reverse=True,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed_at.isoformat().replace("+00:00", "Z"),
        "window_days": window_days,
        "total_signals": sum(len(entries) for entries in grouped.values()),
        "unique_signals": len(items),
        "promoted": [item for item in items if item["promotion_status"] == "promote"],
        "observed": [item for item in items if item["promotion_status"] == "observe"],
    }


def _load_payload(args: argparse.Namespace) -> Any:
    if bool(args.payload_json) == bool(args.payload_file):
        raise SignalError("provide exactly one of --payload-json or --payload-file")
    if args.payload_json:
        try:
            return json.loads(args.payload_json)
        except json.JSONDecodeError as exc:
            raise SignalError(f"--payload-json is invalid JSON: {exc}") from exc
    try:
        return json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    except OSError as exc:
        raise SignalError(f"cannot read payload file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SignalError(f"payload file is invalid JSON: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb-root", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    record = subparsers.add_parser("record", help="validate and store one signal")
    record.add_argument("--payload-json")
    record.add_argument("--payload-file", type=Path)

    subparsers.add_parser("summary", help="summarize recent signals")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = resolve_store(kb_root=args.kb_root, repo_root=args.repo_root)
        if args.command == "record":
            result = record_signal(
                _load_payload(args),
                store=store,
                window_days=args.window_days,
            )
        else:
            result = {
                "store": str(store.root),
                "store_scope": store.scope,
                **summarize_signals(
                    load_signals(store.root), window_days=args.window_days
                ),
            }
    except SignalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
