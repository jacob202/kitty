from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _workflow(name: str) -> tuple[str, dict]:
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    return text, yaml.safe_load(text)


def test_tests_workflow_has_stable_merge_gate_and_frontend_change_detection() -> None:
    text, workflow = _workflow("tests.yml")
    jobs = workflow["jobs"]
    assert "changes" in jobs
    assert "merge-gate" in jobs
    assert jobs["merge-gate"]["name"] == "merge-gate"
    assert "hygiene" not in jobs["merge-gate"]["needs"]
    assert "frontend" in text
    assert "gateway/kitty-chat/" in text
    assert "needs.changes.outputs.frontend" in text


def test_merge_gate_requires_high_signal_checks_but_accepts_skipped_frontend() -> None:
    text, _ = _workflow("tests.yml")
    assert "pytest" in text
    assert "lint" in text
    assert "typecheck" in text
    assert "kitty-chat" in text
    assert "browser-smoke" in text
    assert "skipped" in text


def test_hygiene_is_advisory() -> None:
    _, workflow = _workflow("tests.yml")
    assert workflow["jobs"]["hygiene"]["continue-on-error"] is True


def test_frontend_and_browser_jobs_are_path_scoped_without_workflow_path_filter() -> None:
    text, workflow = _workflow("tests.yml")
    assert "paths:" not in text.split("jobs:", 1)[0]
    assert "if" in workflow["jobs"]["kitty-chat"]
    assert "if" in workflow["jobs"]["browser-smoke"]

def test_auto_label_preserves_manual_approval_labels() -> None:
    _, workflow = _workflow("pr-auto-label.yml")
    step = next(step for step in workflow["jobs"]["auto-label"]["steps"] if step.get("uses") == "actions/labeler@v7")
    assert step["with"]["sync-labels"] is False
