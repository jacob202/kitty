from __future__ import annotations

from pathlib import Path

import pytest

from gateway.research_bench import (
    METRIC_WEIGHTS,
    load_fixture,
    score_engine,
    validate_result,
)

FIXTURE = Path(__file__).parent / "fixtures" / "research_bench_v1.json"


def _result(task_id: str, *, engine: str = "candidate-a") -> dict:
    return {
        "task_id": task_id,
        "engine": engine,
        "engine_version": "1.0",
        "status": "completed",
        "report": "Supported report",
        "sources": [
            {"source_id": "s1", "url": "https://example.com/source", "title": "Source"}
        ],
        "claims": [
            {
                "claim_id": "c1",
                "text": "Supported claim",
                "status": "VERIFIED",
                "source_refs": ["s1"],
            }
        ],
        "estimated_cost_usd": 0.10,
        "actual_cost_usd": 0.08,
        "latency_seconds": 12.0,
        "metrics": {name: 0.8 for name in METRIC_WEIGHTS},
    }


def test_fixture_has_exactly_five_required_research_scenarios():
    fixture = load_fixture(FIXTURE)
    tasks = fixture["tasks"]
    assert fixture["version"] == 1
    assert len(tasks) == 5
    assert {task["category"] for task in tasks} == {
        "current_facts",
        "technical_primary_sources",
        "comparative_conflict",
        "local_documents_plus_web",
        "obscure_niche",
    }


def test_verified_claim_requires_retained_source_reference():
    result = _result("current-facts")
    result["claims"][0]["source_refs"] = []
    with pytest.raises(ValueError, match="VERIFIED claim c1 requires source_refs"):
        validate_result(result)


def test_metrics_must_be_complete_and_normalized():
    result = _result("current-facts")
    result["metrics"]["citation_correctness"] = 1.5
    with pytest.raises(ValueError, match="citation_correctness"):
        validate_result(result)


def test_engine_score_requires_all_five_tasks_and_preserves_cost_latency():
    fixture = load_fixture(FIXTURE)
    results = [_result(task["task_id"]) for task in fixture["tasks"]]
    scored = score_engine(fixture, results)
    assert scored["engine"] == "candidate-a"
    assert scored["tasks_completed"] == 5
    assert scored["score"] == pytest.approx(0.8)
    assert scored["actual_cost_usd"] == pytest.approx(0.4)
    assert scored["latency_seconds"] == pytest.approx(60.0)


def test_engine_score_refuses_incomplete_benchmark():
    fixture = load_fixture(FIXTURE)
    results = [_result(task["task_id"]) for task in fixture["tasks"][:-1]]
    with pytest.raises(ValueError, match="missing benchmark task"):
        score_engine(fixture, results)
