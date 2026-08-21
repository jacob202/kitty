"""Small, versioned benchmark contract for choosing Kitty research engines."""

from __future__ import annotations

import json
from pathlib import Path

METRIC_WEIGHTS = {
    "usefulness": 0.24,
    "citation_correctness": 0.20,
    "primary_source_quality": 0.14,
    "coverage": 0.12,
    "contradiction_handling": 0.10,
    "cost_efficiency": 0.06,
    "latency_efficiency": 0.04,
    "resumability": 0.06,
    "integration_maintainability": 0.04,
}

_ALLOWED_STATUSES = {"completed", "partial", "failed", "cancelled", "unknown"}
_ALLOWED_CLAIM_STATUSES = {"VERIFIED", "INFERENCE", "HYPOTHESIS"}


def load_fixture(path: Path) -> dict:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    if fixture.get("version") != 1 or not isinstance(fixture.get("tasks"), list):
        raise ValueError("unsupported ResearchBench fixture")
    return fixture


def validate_result(result: dict) -> None:
    for field in ("task_id", "engine", "engine_version", "status", "report"):
        if not str(result.get(field, "")).strip():
            raise ValueError(f"missing {field}")
    if result["status"] not in _ALLOWED_STATUSES:
        raise ValueError(f"invalid status: {result['status']}")

    sources = result.get("sources")
    claims = result.get("claims")
    if not isinstance(sources, list) or not isinstance(claims, list):
        raise ValueError("sources and claims must be lists")
    source_ids = {str(source.get("source_id", "")) for source in sources}

    for claim in claims:
        claim_id = str(claim.get("claim_id", "")).strip()
        status = claim.get("status")
        refs = claim.get("source_refs") or []
        if status not in _ALLOWED_CLAIM_STATUSES:
            raise ValueError(f"invalid claim status for {claim_id}")
        if status == "VERIFIED" and not refs:
            raise ValueError(f"VERIFIED claim {claim_id} requires source_refs")
        unknown_refs = {str(ref) for ref in refs} - source_ids
        if unknown_refs:
            raise ValueError(f"claim {claim_id} references unknown sources")

    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be a mapping")
    for name in METRIC_WEIGHTS:
        value = metrics.get(name)
        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
            raise ValueError(f"metric {name} must be between 0 and 1")

    for name in ("estimated_cost_usd", "actual_cost_usd", "latency_seconds"):
        value = result.get(name, 0)
        if not isinstance(value, (int, float)) or float(value) < 0:
            raise ValueError(f"{name} must be non-negative")


def _score_result(result: dict) -> float:
    validate_result(result)
    return sum(float(result["metrics"][name]) * weight for name, weight in METRIC_WEIGHTS.items())


def score_engine(fixture: dict, results: list[dict]) -> dict:
    expected = {str(task["task_id"]) for task in fixture.get("tasks", [])}
    actual = {str(result.get("task_id", "")) for result in results}
    missing = expected - actual
    if missing:
        raise ValueError(f"missing benchmark task: {sorted(missing)[0]}")
    if actual - expected:
        raise ValueError(f"unexpected benchmark task: {sorted(actual - expected)[0]}")
    if len(results) != len(expected):
        raise ValueError("benchmark results must contain one result per task")

    engines = {str(result.get("engine", "")) for result in results}
    if len(engines) != 1:
        raise ValueError("score_engine requires results from exactly one engine")

    scores = [_score_result(result) for result in results]
    return {
        "engine": next(iter(engines)),
        "tasks_completed": len(results),
        "score": sum(scores) / len(scores),
        "estimated_cost_usd": sum(float(r.get("estimated_cost_usd", 0)) for r in results),
        "actual_cost_usd": sum(float(r.get("actual_cost_usd", 0)) for r in results),
        "latency_seconds": sum(float(r.get("latency_seconds", 0)) for r in results),
    }
