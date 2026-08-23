from __future__ import annotations

import json
from pathlib import Path

from scripts import pr_policy, pr_review

SHA = "a" * 40


def _acceptance_body(*, accepted: bool = False) -> str:
    checks = "x" if accepted else " "
    return f"""## Product acceptance (required for user-facing changes)
- User goal: understand the result
- Starting state and dependent services: service running
- Running-app steps and visible result: exercise the changed flow
- Failure/recovery path tested: provider unavailable
- Viewports tested: phone and desktop
- Evidence: recording-123
- Independent task-completion reviewer: reviewer-2
- Remaining limitations or dead ends: none

- [{checks}] Every visible primary control either completes its task or is disabled with one clear recovery action.
- [{checks}] I tested required services both available and unavailable/misconfigured.
- [{checks}] There is no horizontal page overflow, clipped dialog, obscured action, or off-screen primary navigation at the mobile viewport.
- [{checks}] Errors explain what failed and what the user can do next; no raw server error is the primary message.
- [{checks}] Normal user workflows do not require packet IDs, KTF phases, ports, env vars, YAML, MCP, LiteLLM, terminal commands, or Mac file paths.
- [{checks}] A reviewer who did not implement the change completed the task in the running app.
"""


def _pr(
    body: str = "",
    *,
    labels: tuple[str, ...] = (),
    additions: int = 20,
    deletions: int = 5,
    author: str = "jacob202",
    head_sha: str = SHA,
    changed_files: int = 2,
) -> dict:
    return {
        "body": body,
        "user": {"login": author},
        "labels": [{"name": label} for label in labels],
        "additions": additions,
        "deletions": deletions,
        "changed_files": changed_files,
        "head": {"sha": head_sha},
    }


def test_backend_pr_does_not_require_template_or_product_acceptance() -> None:
    violations = pr_policy.evaluate_policy(_pr(), ["gateway/memory.py"], independent_review_approved=True)
    assert violations == []


def test_ui_source_pr_requires_completed_product_acceptance() -> None:
    path = "gateway/kitty-chat/src/components/HomeState.tsx"
    missing = pr_policy.evaluate_policy(_pr(_acceptance_body()), [path], independent_review_approved=True)
    assert any("product acceptance" in item.lower() for item in missing)

    approved = pr_policy.evaluate_policy(
        _pr(_acceptance_body(accepted=True)), [path], independent_review_approved=True
    )
    assert approved == []


def test_frontend_test_only_pr_does_not_require_product_acceptance() -> None:
    violations = pr_policy.evaluate_policy(
        _pr(), ["gateway/kitty-chat/tests/HomeState.test.tsx"], independent_review_approved=True
    )
    assert violations == []


def test_risky_scope_requires_exact_head_human_approval_and_independent_review() -> None:
    path = ".github/workflows/tests.yml"
    missing = pr_policy.evaluate_policy(_pr(), [path], independent_review_approved=False)
    assert any("risk/approved" in item for item in missing)
    assert any("exact-head risk approval" in item.lower() for item in missing)
    assert any("independent review" in item.lower() for item in missing)

    body = f"Risk approval: APPROVE {SHA} — CI gate migration explicitly approved"
    still_missing_review = pr_policy.evaluate_policy(
        _pr(body, labels=(pr_policy.RISK_APPROVED_LABEL,)),
        [path],
        independent_review_approved=False,
    )
    assert still_missing_review == [
        "risky scope requires trusted independent review approval for the exact current head"
    ]

    approved = pr_policy.evaluate_policy(
        _pr(body, labels=(pr_policy.RISK_APPROVED_LABEL,)),
        [path],
        independent_review_approved=True,
    )
    assert approved == []


def test_policy_and_review_implementation_files_are_risky() -> None:
    for path in ["scripts/pr_policy.py", "scripts/pr_review.py", "scripts/pr_review_gate.py"]:
        violations = pr_policy.evaluate_policy(_pr(), [path], independent_review_approved=False)
        assert any("risk/approved" in item for item in violations), path


def test_large_change_is_advisory_not_blocking() -> None:
    pr = _pr(additions=1600, deletions=20, changed_files=30)
    assert pr_policy.evaluate_policy(pr, ["gateway/memory.py"], independent_review_approved=True) == []
    warnings = pr_policy.policy_warnings(pr)
    assert any("large" in item.lower() for item in warnings)


def test_dependabot_waives_product_prose_but_not_sensitive_scope_approval() -> None:
    pr = _pr(author="dependabot[bot]")
    violations = pr_policy.evaluate_policy(pr, ["requirements.txt"], independent_review_approved=False)
    assert any("risk/approved" in item for item in violations)
    assert any("independent review" in item.lower() for item in violations)


def test_policy_gate_is_consolidated_into_trusted_review_workflow() -> None:
    workflows = Path(__file__).parents[1] / ".github" / "workflows"
    text = (workflows / "pr-agent-review.yml").read_text(encoding="utf-8")
    assert "pull_request_target:" in text
    assert "policy-gate:" in text
    assert "name: policy-gate" in text
    assert "needs: agent-review" in text
    assert "github.event.repository.default_branch" in text


def test_duplicate_pr_workflows_are_removed() -> None:
    workflows = Path(__file__).parents[1] / ".github" / "workflows"
    for filename in [
        "pr-description-check.yml",
        "pr-risk-guardrails.yml",
        "pr-test-hints.yml",
        "pr-release-evidence.yml",
        "pr-policy.yml",
        "pr-policy-trusted.yml",
    ]:
        assert not (workflows / filename).exists(), filename

def test_pr_template_documents_only_live_exact_head_approval_receipts() -> None:
    text = (Path(__file__).parents[1] / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    assert "Risk approval: APPROVE <full-head-SHA>" in text
    assert "Review override: APPROVE <full-head-SHA>" in text
    assert "Large-change approval: APPROVE <full-head-SHA>" not in text


def test_main_reads_current_pr_and_review_evidence_from_api(tmp_path, monkeypatch) -> None:
    current_body = f"Risk approval: APPROVE {SHA} — current approval"
    current = _pr(
        current_body,
        labels=(pr_policy.RISK_APPROVED_LABEL,),
        head_sha=SHA,
    )
    current["number"] = 12
    event = {
        "action": "labeled",
        "pull_request": {"number": 12},
        "repository": {"owner": {"login": "jacob202"}, "name": "kitty"},
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    approved_comment = {
        "body": (
            f"{pr_review.COMMENT_MARKER}\n## Agent PR Review\n\n"
            f"No actionable findings in this diff.\n\n_Reviewed commit `{SHA}`._"
        ),
        "user": {"login": "github-actions[bot]", "type": "Bot"},
    }

    def fake_github_json(url: str, _token: str):
        if url.endswith("/pulls/12"):
            return current
        if "/pulls/12/files?" in url:
            return [{"filename": ".github/workflows/tests.yml"}]
        if url.endswith("/issues/12/comments?per_page=100"):
            return [approved_comment]
        raise AssertionError(url)

    monkeypatch.setattr(pr_policy, "_github_json", fake_github_json)
    pr_policy.main()
