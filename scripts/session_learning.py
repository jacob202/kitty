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
import fcntl
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1
DEFAULT_WINDOW_DAYS = 30
PROMOTION_STATUSES = frozenset({"observe", "promote"})

CATEGORIES = frozenset(
    {
        "architecture_boundary",
        "capability_improvement",
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


def _source_session_fingerprint(source_session: str) -> str:
    """Keep filenames collision-safe without exposing arbitrary session text."""
    return hashlib.sha256(source_session.encode("utf-8")).hexdigest()[:16]


def _signal_id(recorded_at: datetime, stable_key: str, source_session: str) -> str:
    timestamp = recorded_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        f"wfs_{timestamp.lower()}_{fingerprint(stable_key)}_"
        f"{_source_session_fingerprint(source_session)}"
    )


def _require_nonnegative_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SignalError(f"{key} must be a non-negative integer")
    return value


def _validate_stored_signal(raw: Any, *, path: Path) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SignalError(f"signal {path} must contain a JSON object")

    expected_keys = {
        "schema_version",
        "id",
        "fingerprint",
        "recorded_at",
        "stable_key",
        "category",
        "severity",
        "summary",
        "evidence",
        "impact",
        "suggested_change",
        "source_session",
        "verified_by",
        "occurrence_count",
        "promotion_status",
        "promotion_reason",
        "store_scope",
        "window_days",
    }
    unknown = sorted(set(raw) - expected_keys)
    missing = sorted(expected_keys - set(raw))
    if unknown or missing:
        raise SignalError(
            f"signal {path} has unknown={unknown} missing={missing}"
        )
    if raw["schema_version"] != SCHEMA_VERSION:
        raise SignalError(
            f"signal {path} has unsupported schema_version "
            f"{raw['schema_version']!r}"
        )

    payload = validate_payload(
        {
            key: raw[key]
            for key in (
                "stable_key",
                "category",
                "severity",
                "summary",
                "evidence",
                "impact",
                "suggested_change",
                "source_session",
                "verified_by",
            )
        }
    )
    recorded_at = parse_timestamp(raw["recorded_at"], field=f"{path}:recorded_at")
    if raw["fingerprint"] != fingerprint(payload["stable_key"]):
        raise SignalError(f"signal {path} has a mismatched fingerprint")
    expected_id = _signal_id(
        recorded_at, payload["stable_key"], payload["source_session"]
    )
    if raw["id"] != expected_id:
        raise SignalError(f"signal {path} has id {raw['id']!r}; expected {expected_id!r}")

    occurrence_count = _require_nonnegative_int(raw, "occurrence_count")
    if occurrence_count < 1:
        raise SignalError(f"signal {path} occurrence_count must be at least 1")
    window_days = _require_nonnegative_int(raw, "window_days")
    if window_days < 1:
        raise SignalError(f"signal {path} window_days must be at least 1")
    promotion_status = raw["promotion_status"]
    if promotion_status not in PROMOTION_STATUSES:
        raise SignalError(
            f"signal {path} promotion_status must be one of "
            f"{sorted(PROMOTION_STATUSES)}"
        )
    expected_status, expected_reason = promotion_decision(
        category=payload["category"],
        severity=payload["severity"],
        occurrence_count=occurrence_count,
    )
    if promotion_status != expected_status:
        raise SignalError(
            f"signal {path} has promotion_status {promotion_status!r}; "
            f"expected {expected_status!r}"
        )
    if raw["promotion_reason"] != expected_reason:
        raise SignalError(f"signal {path} has an invalid promotion_reason")
    if not isinstance(raw["store_scope"], str) or not raw["store_scope"].strip():
        raise SignalError(f"signal {path} has invalid store_scope")

    return {
        "schema_version": SCHEMA_VERSION,
        "id": expected_id,
        "fingerprint": raw["fingerprint"],
        "recorded_at": recorded_at.isoformat().replace("+00:00", "Z"),
        **payload,
        "occurrence_count": occurrence_count,
        "promotion_status": expected_status,
        "promotion_reason": expected_reason,
        "store_scope": raw["store_scope"].strip(),
        "window_days": window_days,
    }


def _load_signal(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SignalError(f"cannot read signal {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SignalError(f"signal {path} is invalid JSON: {exc}") from exc
    return _validate_stored_signal(payload, path=path)


def load_signals(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    if not root.is_dir():
        raise SignalError(f"signal store is not a directory: {root}")
    signals = [_load_signal(path) for path in sorted(root.glob("*.json"))]
    identities: set[tuple[str, str]] = set()
    for signal in signals:
        identity = (signal["stable_key"], signal["source_session"])
        if identity in identities:
            raise SignalError(
                "duplicate stable_key/source_session in signal store: "
                f"{identity[0]!r}/{identity[1]!r}"
            )
        identities.add(identity)
    _validate_occurrence_counts(signals)
    return signals


def _in_window(
    signal: dict[str, Any], *, now: datetime, window: timedelta
) -> bool:
    recorded = parse_timestamp(signal["recorded_at"], field="recorded_at")
    return now - window <= recorded <= now + timedelta(minutes=5)


def _validate_occurrence_counts(signals: Iterable[dict[str, Any]]) -> None:
    """Ensure retained counts describe distinct prior sessions, never file count."""
    entries = list(signals)
    groups: dict[tuple[str, datetime, int], list[dict[str, Any]]] = defaultdict(list)
    for signal in entries:
        recorded_at = parse_timestamp(signal["recorded_at"], field="recorded_at")
        groups[(signal["stable_key"], recorded_at, signal["window_days"])].append(
            signal
        )

    for (stable_key, recorded_at, window_days), group in groups.items():
        window = timedelta(days=window_days)
        prior_sessions = {
            item["source_session"]
            for item in entries
            if item["stable_key"] == stable_key
            and recorded_at - window
            <= parse_timestamp(item["recorded_at"], field="recorded_at")
            < recorded_at
        }
        expected_counts = list(
            range(len(prior_sessions) + 1, len(prior_sessions) + len(group) + 1)
        )
        actual_counts = sorted(signal["occurrence_count"] for signal in group)
        if actual_counts != expected_counts:
            raise SignalError(
                f"signals for {stable_key!r} at "
                f"{recorded_at.isoformat()} have occurrence_count values "
                f"{actual_counts}; expected {expected_counts} distinct "
                "source_session values"
            )


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


def _score_mapping(value: Mapping[str, Any], *, label: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or not value:
        raise SignalError(f"{label} must be a non-empty mapping of task keys to scores")
    normalized: dict[str, float] = {}
    for raw_key, raw_score in value.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise SignalError(f"{label} task keys must be non-empty strings")
        if (
            isinstance(raw_score, bool)
            or not isinstance(raw_score, (int, float))
            or not math.isfinite(raw_score)
        ):
            raise SignalError(f"{label}[{raw_key!r}] must be a finite numeric score")
        normalized[raw_key.strip()] = float(raw_score)
    if len(normalized) != len(value):
        raise SignalError(f"{label} task keys must remain unique after normalization")
    return normalized


def _evaluation_context(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise SignalError("paired evaluation context must be an object")
    required = ("model", "workspace", "scorer")
    normalized: dict[str, str] = {}
    for key in required:
        raw = value.get(key)
        if not isinstance(raw, str) or not raw.strip():
            raise SignalError(
                "paired evaluation context must name non-empty model, workspace, and scorer"
            )
        normalized[key] = raw.strip()
    unknown = sorted(set(value) - set(required))
    if unknown:
        raise SignalError(f"unknown paired evaluation context keys: {unknown}")
    return normalized


def compare_capability_runs(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    minimum_lift: float = 0.0,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare a candidate capability against baseline on exactly matched tasks.

    ``context`` records the shared model, workspace, and scorer. The function
    refuses unmatched task sets so an apparent lift cannot be manufactured by
    evaluating different work.
    """
    base = _score_mapping(baseline, label="baseline")
    cand = _score_mapping(candidate, label="candidate")
    if set(base) != set(cand):
        raise SignalError(
            "paired evaluation requires identical task keys for baseline and candidate"
        )
    if (
        isinstance(minimum_lift, bool)
        or not isinstance(minimum_lift, (int, float))
        or not math.isfinite(minimum_lift)
        or minimum_lift < 0
    ):
        raise SignalError("minimum_lift must be a finite non-negative number")
    matched_context = _evaluation_context(context)
    task_keys = sorted(base)
    baseline_mean = sum(base[key] for key in task_keys) / len(task_keys)
    candidate_mean = sum(cand[key] for key in task_keys) / len(task_keys)
    lift = candidate_mean - baseline_mean
    threshold = float(minimum_lift)
    return {
        "task_keys": task_keys,
        "pair_count": len(task_keys),
        "baseline_mean": baseline_mean,
        "candidate_mean": candidate_mean,
        "absolute_lift": lift,
        "minimum_lift": threshold,
        "improved": lift > 0 and lift >= threshold,
        "context": matched_context,
    }


def record_evaluation_signal(
    evaluation: Mapping[str, Any],
    *,
    stable_key: str,
    capability_name: str,
    source_session: str,
    store: Store,
    now: datetime | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict[str, Any]:
    """Distill positive paired evidence through the existing learning store.

    Raw trajectories remain elsewhere. This writes only a bounded evidence
    signal, and the existing repeat-count promotion gate decides whether the
    lesson is merely observed or promoted.
    """
    if not isinstance(evaluation, Mapping):
        raise SignalError("evaluation must be an object")
    if not isinstance(capability_name, str) or not capability_name.strip():
        raise SignalError("capability_name must be a non-empty string")

    required_numbers = ("baseline_mean", "candidate_mean", "absolute_lift", "minimum_lift")
    numbers: dict[str, float] = {}
    for key in required_numbers:
        raw = evaluation.get(key)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
            raise SignalError(f"evaluation.{key} must be a finite number")
        numbers[key] = float(raw)
    pair_count = evaluation.get("pair_count")
    if isinstance(pair_count, bool) or not isinstance(pair_count, int) or pair_count < 1:
        raise SignalError("evaluation.pair_count must be a positive integer")
    task_keys = evaluation.get("task_keys")
    if not isinstance(task_keys, list) or len(task_keys) != pair_count or not all(
        isinstance(key, str) and key for key in task_keys
    ):
        raise SignalError("evaluation.task_keys must contain one non-empty key per pair")
    context = _evaluation_context(evaluation.get("context"))
    if numbers["minimum_lift"] < 0:
        raise SignalError("evaluation.minimum_lift must be non-negative")
    computed_lift = numbers["candidate_mean"] - numbers["baseline_mean"]
    if not math.isclose(numbers["absolute_lift"], computed_lift, rel_tol=1e-12, abs_tol=1e-12):
        raise SignalError(
            "evaluation.absolute_lift must equal candidate_mean - baseline_mean"
        )
    improved = evaluation.get("improved")
    if not isinstance(improved, bool):
        raise SignalError("evaluation.improved must be boolean")
    expected_improved = computed_lift > 0 and computed_lift >= numbers["minimum_lift"]
    if improved != expected_improved:
        raise SignalError("evaluation.improved is inconsistent with the measured lift")
    if not expected_improved:
        return {
            "created": False,
            "path": None,
            "signal": None,
            "reason": "candidate did not meet the paired-evaluation lift threshold",
        }

    evidence = (
        f"paired evaluation: pair_count={pair_count}; "
        f"baseline_mean={numbers['baseline_mean']:.6f}; "
        f"candidate_mean={numbers['candidate_mean']:.6f}; "
        f"absolute_lift={numbers['absolute_lift']:.6f}; "
        f"minimum_lift={numbers['minimum_lift']:.6f}; "
        f"model={context['model']}; workspace={context['workspace']}; "
        f"scorer={context['scorer']}; task_keys={','.join(task_keys)}"
    )
    raw_payload = {
        "stable_key": stable_key,
        "category": "capability_improvement",
        "severity": "medium",
        "summary": (
            f"{capability_name.strip()} improved matched Builder outcomes by "
            f"{numbers['absolute_lift']:.6f} across {pair_count} task(s)."
        ),
        "evidence": evidence,
        "impact": "Matched evidence indicates the candidate capability improves Builder outcomes.",
        "suggested_change": (
            "Promote the capability into the relevant Builder harness or packet only "
            "after the existing learning gate sees repeated evidence."
        ),
        "source_session": source_session,
        "verified_by": "paired-capability-eval",
    }
    return record_signal(raw_payload, store=store, now=now, window_days=window_days)


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

    store.root.mkdir(parents=True, exist_ok=True)
    lock_path = store.root / ".workflow-signals.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            existing = load_signals(store.root)
            for signal in existing:
                if (
                    signal["stable_key"] == payload["stable_key"]
                    and signal["source_session"] == payload["source_session"]
                ):
                    if all(signal[key] == value for key, value in payload.items()):
                        return {
                            "created": False,
                            "path": str(_signal_path(store.root, signal)),
                            "signal": signal,
                        }
                    raise SignalError(
                        "stable_key/source_session already exists with different "
                        f"signal content: {payload['stable_key']!r}/"
                        f"{payload['source_session']!r}"
                    )

            window = timedelta(days=window_days)
            prior_sessions = {
                signal["source_session"]
                for signal in existing
                if signal["stable_key"] == payload["stable_key"]
                and observed_at - window
                <= parse_timestamp(signal["recorded_at"], field="recorded_at")
                <= observed_at
            }
            occurrence_count = len(prior_sessions | {payload["source_session"]})
            status, reason = promotion_decision(
                category=payload["category"],
                severity=payload["severity"],
                occurrence_count=occurrence_count,
            )
            record = {
                "schema_version": SCHEMA_VERSION,
                "id": _signal_id(
                    observed_at, payload["stable_key"], payload["source_session"]
                ),
                "fingerprint": fingerprint(payload["stable_key"]),
                "recorded_at": observed_at.isoformat().replace("+00:00", "Z"),
                **payload,
                "occurrence_count": occurrence_count,
                "promotion_status": status,
                "promotion_reason": reason,
                "store_scope": store.scope,
                "window_days": window_days,
            }
            path = _signal_path(store.root, record)
            _write_signal_atomically(path, record)
            return {"created": True, "path": str(path), "signal": record}
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _signal_path(root: Path, signal: dict[str, Any]) -> Path:
    recorded_at = parse_timestamp(signal["recorded_at"], field="recorded_at")
    timestamp = recorded_at.strftime("%Y%m%dT%H%M%SZ")
    return root / (
        f"{timestamp}-{signal['stable_key']}-"
        f"{_source_session_fingerprint(signal['source_session'])}.json"
    )


def _write_signal_atomically(path: Path, record: dict[str, Any]) -> None:
    """Publish a fully-written record without a check-then-write overwrite race."""
    temp_fd, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_name, path)
        except FileExistsError as exc:
            raise SignalError(
                f"refusing to overwrite existing signal collision: {path}"
            ) from exc
    except OSError as exc:
        raise SignalError(f"cannot atomically write signal {path}: {exc}") from exc
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


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
