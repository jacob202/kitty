from __future__ import annotations

from pathlib import Path

from tests.bench.memorybench import aggregate, load_cases, run_case


FIXTURES = Path(__file__).with_name("memorybench_cases.json")


def test_memorybench_fixture_schema_loads():
    cases = load_cases(FIXTURES)
    assert len(cases) >= 5
    assert {case["id"] for case in cases} >= {
        "correction_precedence_001",
        "source_authority_001",
        "unsupported_recall_001",
        "substring_false_positive_001",
    }


def test_memorybench_preserves_memoryweave_authority(tmp_path):
    cases = {case["id"]: case for case in load_cases(FIXTURES)}

    corrected = run_case(cases["correction_precedence_001"], tmp_path / "corrected.db")
    assert corrected.returned_values[0] == "green"
    assert "blue" not in corrected.returned_values

    authority = run_case(cases["source_authority_001"], tmp_path / "authority.db")
    assert authority.returned_values[0] == "2SA726"


def test_memorybench_records_current_retrieval_quality(tmp_path):
    cases = load_cases(FIXTURES)
    results = [run_case(case, tmp_path / f"{case['id']}.db") for case in cases]
    metrics = aggregate(results)

    assert set(metrics) == {"hit_at_1", "mrr", "recall_at_k", "forbidden_rate"}
    assert all(0.0 <= value <= 1.0 for value in metrics.values())


def test_substring_false_positive_is_eliminated(tmp_path):
    cases = {case["id"]: case for case in load_cases(FIXTURES)}
    result = run_case(
        cases["substring_false_positive_001"],
        tmp_path / "substring.db",
    )
    assert result.forbidden_hit == 0.0
    assert result.returned_values == ()
