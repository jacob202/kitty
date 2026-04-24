"""Regression detection — compare current eval scores against the most recent artifact."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def detect_regression(
    prev_artifact_dir: Path,
    current_scores: dict[str, float],
    *,
    suite: str = "smoke",
    threshold: float = 0.05,
) -> dict[str, Any]:
    """Compare *current_scores* against the most recent artifact for *suite*.

    Args:
        prev_artifact_dir: Directory containing previous run artifacts.
        current_scores: Mapping of suite name → pass rate (0.0–1.0).
        suite: Which suite to compare.
        threshold: Minimum absolute drop to count as a regression.

    Returns a dict with keys:
        is_regression (bool), delta (float), prev_rate (float),
        curr_rate (float), prev_run_id (str | None), reason (str | None).
    """
    prev_artifact_dir = Path(prev_artifact_dir)

    # Find the most recently written artifact for this suite
    candidates = sorted(
        prev_artifact_dir.glob(f"*_{suite}.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not candidates:
        return {
            "is_regression": False,
            "delta": 0.0,
            "prev_rate": None,
            "curr_rate": current_scores.get(suite),
            "prev_run_id": None,
            "reason": "no prior artifact found for suite",
        }

    prev_data = json.loads(candidates[0].read_text())
    prev_rate = prev_data.get("scores", {}).get(suite, {}).get("rate", 0.0)
    curr_rate = current_scores.get(suite, 0.0)
    delta = curr_rate - prev_rate

    return {
        "is_regression": delta < -threshold,
        "delta": round(delta, 6),
        "prev_rate": prev_rate,
        "curr_rate": curr_rate,
        "prev_run_id": prev_data.get("run_id"),
        "reason": None,
    }
