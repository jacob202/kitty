"""Evidence-backed Image Lab cost and duration estimates.

Provider spend ceilings are safety policy, not price claims. This module keeps
those concepts separate by estimating from completed provider observations.
Local renderers are known to have zero provider-billed API cost; duration is
still unknown until enough real completions exist.
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Any

from gateway import db as kitty_db
from gateway import paths as _paths
from gateway.paths import DB_MIGRATIONS_DIR

_MIGRATION_FILE = DB_MIGRATIONS_DIR / "033_image_job_observations.sql"
_LOCAL_PROVIDERS = frozenset({"comfyui", "drawthings"})
_MAX_SAMPLES = 20
_MIN_DURATION_SAMPLES = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_db(conn: Any = None) -> None:
    def apply(c: Any) -> None:
        c.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))

    if conn is not None:
        apply(conn)
    else:
        with kitty_db.connect(_paths.KITTY_DB_FILE) as c:
            apply(c)


def _finite_nonnegative(value: float | None, field: str) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be finite and >= 0")
    return number


def _finite_positive(value: float, field: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{field} must be finite and > 0")
    return number


def record_observation(
    *,
    job_id: str,
    provider: str,
    model_id: str | None,
    operation: str,
    actual_cost_usd: float | None,
    duration_seconds: float,
    completed_at: str | None = None,
) -> None:
    if not job_id.strip():
        raise ValueError("job_id must not be empty")
    if not provider.strip():
        raise ValueError("provider must not be empty")
    if not operation.strip():
        raise ValueError("operation must not be empty")
    cost = _finite_nonnegative(actual_cost_usd, "actual_cost_usd")
    duration = _finite_positive(duration_seconds, "duration_seconds")
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute(
            """INSERT OR REPLACE INTO image_job_observations
               (job_id, provider, model_id, operation, actual_cost_usd, duration_seconds, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                provider.strip().lower(),
                model_id,
                operation.strip().lower(),
                cost,
                duration,
                completed_at or _now_iso(),
            ),
        )
        conn.commit()


def _recent(provider: str, model_id: str | None, operation: str) -> list[Any]:
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        rows = conn.execute(
            """SELECT actual_cost_usd, duration_seconds
               FROM image_job_observations
               WHERE provider = ? AND model_id IS ? AND operation = ?
               ORDER BY completed_at DESC LIMIT ?""",
            (provider.strip().lower(), model_id, operation.strip().lower(), _MAX_SAMPLES),
        ).fetchall()
    return list(rows)


def estimate(provider: str, *, model_id: str | None, operation: str) -> dict[str, Any]:
    provider = provider.strip().lower()
    rows = _recent(provider, model_id, operation)
    observed_costs = [float(row["actual_cost_usd"]) for row in rows if row["actual_cost_usd"] is not None]
    durations = [float(row["duration_seconds"]) for row in rows if row["duration_seconds"] is not None]

    if provider in _LOCAL_PROVIDERS:
        cost = {
            "state": "known",
            "usd": 0.0,
            "basis": "local renderer; no provider-billed API usage",
            "samples": 0,
        }
    elif observed_costs:
        cost = {
            "state": "known",
            "usd": round(float(statistics.median(observed_costs)), 6),
            "basis": "median of recent provider-reported completed jobs",
            "samples": len(observed_costs),
        }
    else:
        cost = {
            "state": "unknown",
            "usd": None,
            "basis": "no provider-reported completed-job cost observations",
            "samples": 0,
        }

    if len(durations) >= _MIN_DURATION_SAMPLES:
        duration = {
            "state": "known",
            "seconds": round(float(statistics.median(durations)), 3),
            "basis": "median of recent completed jobs",
            "samples": len(durations),
        }
    else:
        duration = {
            "state": "unknown",
            "seconds": None,
            "basis": f"need {_MIN_DURATION_SAMPLES} completed jobs for a duration estimate",
            "samples": len(durations),
        }

    return {
        "provider": provider,
        "model_id": model_id,
        "operation": operation,
        "cost": cost,
        "duration": duration,
    }


__all__ = ["estimate", "record_observation"]
