"""Delivery-pipeline efficiency evidence derived from Actions history."""

from __future__ import annotations

import json

from scripts import ci_metrics

RUN_TEMPLATE = {
    "id": 1,
    "status": "completed",
    "conclusion": "success",
    "event": "pull_request",
    "head_sha": "c" * 40,
    "run_started_at": "2026-08-23T07:00:00Z",
    "updated_at": "2026-08-23T07:05:00Z",
    "head_commit": {"message": "fix(gateway): repair recovery race"},
}


def _job(name: str, seconds: int, conclusion: str = "success") -> dict:
    return {
        "name": name,
        "conclusion": conclusion,
        "started_at": "2026-08-23T07:00:00Z",
        "completed_at": f"2026-08-23T07:{seconds // 60:02d}:{seconds % 60:02d}Z",
    }


def _with_jobs(monkeypatch, jobs: list[dict]) -> None:
    monkeypatch.setattr(ci_metrics, "list_jobs", lambda repo, run_id, token: jobs)


def test_a_run_with_only_scope_and_gate_jobs_is_classified_docs_only() -> None:
    jobs = [_job("changes", 4), _job("pytest", 0, "skipped"), _job("merge-gate", 3)]
    assert ci_metrics._classify_run(jobs) == "docs-only"


def test_a_run_that_executed_pytest_is_classified_code() -> None:
    jobs = [_job("changes", 4), _job("pytest", 300), _job("kitty-chat", 0, "skipped")]
    assert ci_metrics._classify_run(jobs) == "code"


def test_a_run_that_executed_browser_evidence_is_classified_frontend() -> None:
    assert ci_metrics._classify_run([_job("browser-smoke", 200)]) == "frontend"


def test_skipped_jobs_do_not_count_toward_runner_time(monkeypatch) -> None:
    _with_jobs(monkeypatch, [_job("changes", 10), _job("pytest", 300, "skipped")])
    summary = ci_metrics.summarize_tests("jacob202/kitty", [dict(RUN_TEMPLATE)], "token")
    assert summary["runs"][0]["runner_seconds"] == 10.0
    assert summary["runs"][0]["classification"] == "docs-only"


def test_cancelled_and_branch_behind_runs_are_counted(monkeypatch) -> None:
    _with_jobs(monkeypatch, [_job("changes", 5)])
    cancelled = dict(RUN_TEMPLATE, id=2, conclusion="cancelled")
    behind = dict(
        RUN_TEMPLATE,
        id=3,
        head_commit={"message": "Merge remote-tracking branch 'origin/main' into feat/x"},
    )
    summary = ci_metrics.summarize_tests(
        "jacob202/kitty", [dict(RUN_TEMPLATE), cancelled, behind], "token"
    )
    assert summary["cancelled_superseded_runs"] == 1
    assert summary["branch_behind_refresh_runs_heuristic"] == 1


def test_model_invocations_and_policy_blocks_are_counted_separately(monkeypatch) -> None:
    _with_jobs(
        monkeypatch,
        [
            _job("scope", 8),
            _job("agent-review", 0, "skipped"),
            _job("policy-gate", 9, "failure"),
        ],
    )
    summary = ci_metrics.summarize_review("jacob202/kitty", [dict(RUN_TEMPLATE)], "token")
    assert summary["model_review_invocations"] == 0
    assert summary["policy_gate_evaluations"] == 1
    assert summary["policy_gate_blocks"] == 1


def test_report_names_what_the_data_cannot_answer(monkeypatch) -> None:
    _with_jobs(monkeypatch, [_job("changes", 5)])
    payload = {
        "repo": "jacob202/kitty",
        "generated_at": "2026-08-23T09:00:00Z",
        "window_days": 14,
        "tests": ci_metrics.summarize_tests("jacob202/kitty", [dict(RUN_TEMPLATE)], "token"),
        "review": ci_metrics.summarize_review("jacob202/kitty", [], "token"),
        "not_derivable": ci_metrics.NOT_DERIVABLE,
    }
    report = ci_metrics.render_report(payload)
    assert "draft_pushes_avoided" in report
    assert "Not derivable from Actions history" in report
    json.dumps(payload)
