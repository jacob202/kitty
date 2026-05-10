"""Tests for eval result contracts."""
from contracts.eval_result import EvalReport, EvalResult


def test_eval_result_pass():
    result = EvalResult(name="memory_name", passed=True, score=1.0, detail="Jacob found")
    assert result.passed is True
    assert result.score == 1.0


def test_eval_result_fail():
    result = EvalResult(name="memory_name", passed=False, score=0.0, detail="Not found")
    assert result.passed is False


def test_eval_report_summary():
    results = [
        EvalResult(name="a", passed=True, score=1.0, detail="ok"),
        EvalResult(name="b", passed=False, score=0.0, detail="miss"),
    ]
    report = EvalReport(results=results)
    assert report.total == 2
    assert report.passed == 1
    assert report.score == 0.5
