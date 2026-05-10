"""Read-only eval artifact dashboard summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_ARTIFACT_DIR = Path("evals/artifacts")


def load_eval_dashboard(artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR, limit: int = 20) -> dict[str, Any]:
    """Summarize recent eval artifacts without running evals or writing files."""
    root = Path(artifact_dir)
    if not root.exists():
        return _empty_dashboard()

    artifacts = sorted(root.glob("*_smoke.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    parsed: list[dict[str, Any]] = []
    corrupt = 0
    for path in artifacts[: max(limit, 1)]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            corrupt += 1
            continue
        parsed.append(_normalize_artifact(path, data))

    latest = parsed[0] if parsed else None
    previous = parsed[1] if len(parsed) > 1 else None
    trend = _trend(latest, previous)

    return {
        "artifact_count": len(artifacts),
        "parsed_count": len(parsed),
        "corrupt_count": corrupt,
        "latest": latest,
        "trend": trend,
        "recent": parsed,
    }


def _empty_dashboard() -> dict[str, Any]:
    return {
        "artifact_count": 0,
        "parsed_count": 0,
        "corrupt_count": 0,
        "latest": None,
        "trend": {"delta": None, "direction": "unknown", "previous_run_id": None},
        "recent": [],
    }


def _normalize_artifact(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    score = data.get("scores", {}).get("smoke", {})
    checks = data.get("checks", [])
    failed = [
        {
            "name": check.get("name", "unknown"),
            "reason": check.get("reason", ""),
        }
        for check in checks
        if not check.get("passed", False)
    ]
    return {
        "artifact": path.name,
        "run_id": data.get("run_id"),
        "suite": data.get("suite", "smoke"),
        "started_at": data.get("started_at"),
        "score": {
            "passed": int(score.get("passed", 0) or 0),
            "total": int(score.get("total", 0) or 0),
            "rate": float(score.get("rate", 0.0) or 0.0),
        },
        "failed_checks": failed,
    }


def _trend(latest: dict[str, Any] | None, previous: dict[str, Any] | None) -> dict[str, Any]:
    if not latest or not previous:
        return {"delta": None, "direction": "unknown", "previous_run_id": None}
    latest_rate = latest["score"]["rate"]
    previous_rate = previous["score"]["rate"]
    delta = latest_rate - previous_rate
    if delta > 0:
        direction = "up"
    elif delta < 0:
        direction = "down"
    else:
        direction = "flat"
    return {
        "delta": delta,
        "direction": direction,
        "previous_run_id": previous.get("run_id"),
    }
