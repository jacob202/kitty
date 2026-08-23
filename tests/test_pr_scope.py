"""The canonical scope classifier every delivery-pipeline consumer reads."""

from __future__ import annotations

import json

import pytest

from scripts import pr_policy, pr_scope

SHA = "a" * 40
OTHER_SHA = "b" * 40


def test_docs_only_change_needs_no_code_or_frontend_evidence() -> None:
    scope = pr_scope.classify(["docs/WORKFLOW.md", "README.md", "docs/adr/0025.mdx"])
    assert scope.docs_only is True
    assert (scope.code, scope.frontend, scope.sensitive) == (False, False, False)


def test_backend_change_is_code_but_not_frontend() -> None:
    scope = pr_scope.classify(["gateway/memory_graph.py", "tests/test_memory_graph.py"])
    assert (scope.code, scope.frontend, scope.sensitive) == (True, False, False)


def test_frontend_source_change_is_code_and_frontend_and_user_facing() -> None:
    scope = pr_scope.classify(["gateway/kitty-chat/src/components/Rail.tsx"])
    assert (scope.code, scope.frontend, scope.user_facing) == (True, True, True)


def test_markdown_inside_the_frontend_tree_does_not_start_browser_evidence() -> None:
    scope = pr_scope.classify(["gateway/kitty-chat/README.md"])
    assert (scope.code, scope.frontend) == (False, False)


def test_empty_change_set_is_docs_only_rather_than_full_scope() -> None:
    assert pr_scope.classify([]).docs_only is True


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/tests.yml",
        ".github/workflows/nightly-health.yml",
        "scripts/pr_policy.py",
        "scripts/pr_review.py",
        "scripts/pr_review_gate.py",
        "scripts/pr_scope.py",
        "requirements.txt",
        "pyproject.toml",
        "gateway/auth_tokens.py",
        ".env.example",
    ],
)
def test_trust_bearing_paths_are_sensitive(path: str) -> None:
    assert pr_scope.classify([path]).sensitive is True, path


def test_the_classifier_itself_is_sensitive_scope() -> None:
    """A classifier that could be edited without review would be the trust hole."""
    violations = pr_policy.evaluate_policy(
        {"body": "", "user": {"login": "someone"}, "labels": [], "head": {"sha": SHA}},
        ["scripts/pr_scope.py"],
        independent_review_approved=False,
    )
    assert any("risk/approved" in item for item in violations)
    assert any("independent review" in item.lower() for item in violations)


def test_policy_and_ci_read_one_pattern_source() -> None:
    assert pr_policy.RISK_PATTERNS is pr_scope.RISK_PATTERNS
    assert pr_policy.USER_FACING_PATTERNS is pr_scope.USER_FACING_PATTERNS


def test_scope_outputs_are_workflow_ready_strings() -> None:
    outputs = pr_scope.classify(["gateway/app.py"]).as_outputs()
    assert outputs == {
        "code": "true",
        "frontend": "false",
        "sensitive": "false",
        "docs_only": "false",
    }


def _compare(monkeypatch, files: list[str]) -> None:
    monkeypatch.setattr(
        pr_scope,
        "_github_json",
        lambda url, token: {"files": [{"filename": name} for name in files]},
    )


def test_push_scope_classifies_a_docs_only_merge_as_docs_only(monkeypatch) -> None:
    _compare(monkeypatch, ["docs/audit/pr-gate-live-proof.md"])
    scope = pr_scope.push_scope("jacob202", "kitty", SHA, OTHER_SHA, "token")
    assert scope.docs_only is True


def test_push_scope_keeps_full_evidence_for_a_code_merge(monkeypatch) -> None:
    _compare(monkeypatch, ["docs/WORKFLOW.md", "gateway/agent.py"])
    scope = pr_scope.push_scope("jacob202", "kitty", SHA, OTHER_SHA, "token")
    assert (scope.code, scope.docs_only) == (True, False)


def test_push_without_a_predecessor_commit_validates_everything(monkeypatch) -> None:
    def explode(url: str, token: str):  # pragma: no cover - must not be reached
        raise AssertionError("comparison must not be attempted")

    monkeypatch.setattr(pr_scope, "_github_json", explode)
    scope = pr_scope.push_scope("jacob202", "kitty", "0" * 40, OTHER_SHA, "token")
    assert scope == pr_scope.FULL_SCOPE


def test_truncated_comparison_validates_everything(monkeypatch) -> None:
    _compare(monkeypatch, [f"docs/file-{index}.md" for index in range(pr_scope.COMPARE_FILE_LIMIT)])
    scope = pr_scope.push_scope("jacob202", "kitty", SHA, OTHER_SHA, "token")
    assert scope == pr_scope.FULL_SCOPE


def test_unresolvable_comparison_raises_instead_of_narrowing_ci(monkeypatch) -> None:
    monkeypatch.setattr(pr_scope, "_github_json", lambda url, token: {"message": "Not Found"})
    with pytest.raises(RuntimeError):
        pr_scope.push_scope("jacob202", "kitty", SHA, OTHER_SHA, "token")


def test_pull_request_event_classifies_from_the_live_file_list(monkeypatch) -> None:
    monkeypatch.setattr(
        pr_scope,
        "_github_json",
        lambda url, token: [{"filename": "gateway/kitty-chat/src/app/page.tsx"}],
    )
    event = {
        "repository": {"owner": {"login": "jacob202"}, "name": "kitty"},
        "pull_request": {"number": 611},
    }
    scope = pr_scope.scope_for_event(event, "pull_request_target", "token")
    assert (scope.code, scope.frontend) == (True, True)


def test_dispatch_and_schedule_events_validate_everything() -> None:
    event = {"repository": {"owner": {"login": "jacob202"}, "name": "kitty"}}
    assert pr_scope.scope_for_event(event, "workflow_dispatch", "") == pr_scope.FULL_SCOPE
    assert pr_scope.scope_for_event(event, "schedule", "") == pr_scope.FULL_SCOPE


def test_main_writes_github_outputs(monkeypatch, tmp_path) -> None:
    event = {
        "repository": {"owner": {"login": "jacob202"}, "name": "kitty"},
        "pull_request": {"number": 611},
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    output_path = tmp_path / "outputs.txt"
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request_target")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
    monkeypatch.setattr(
        pr_scope, "_github_json", lambda url, token: [{"filename": "docs/ROADMAP.md"}]
    )

    pr_scope.main()

    written = output_path.read_text(encoding="utf-8")
    assert "docs_only=true" in written
    assert "code=false" in written
    assert "sensitive=false" in written


def test_main_fails_loudly_when_scope_cannot_be_resolved(monkeypatch, tmp_path) -> None:
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps({"pull_request": {"number": 1}}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request_target")
    with pytest.raises(SystemExit) as excinfo:
        pr_scope.main()
    assert excinfo.value.code == 1
