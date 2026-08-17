from __future__ import annotations

from scripts import pr_policy


def _body(*, accepted: bool = False, not_user_facing: bool = False) -> str:
    checks = "x" if accepted else " "
    override = "x" if not_user_facing else " "
    return f"""## Summary
- scoped change

## Test plan
- [x] focused tests

## Scope and risk
- Area: backend
- Risk: low
- User-facing impact: none
- Manual approval: NO

## Product acceptance (required for user-facing changes)
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

### Not user-facing override
- [{override}] Not user-facing; the product-acceptance block above is not applicable.
- Reason (required when checked): backend-only — no user surface changed

## Guardrails
- [x] I did not touch secrets/auth/env paths without explicit approval.
- [x] I kept the diff scoped to the stated task.
- [x] I included observable evidence for behavior changes (logs, screenshots, or command output).
- [ ] Manual approval received for risky scope (auth/secrets/env/CI/destructive changes).
"""


def _pr(body: str, *, labels: tuple[str, ...] = (), additions: int = 20, deletions: int = 5, author: str = "jacob202", head_sha: str = "a" * 40) -> dict:
    return {
        "body": body,
        "user": {"login": author},
        "labels": [{"name": label} for label in labels],
        "additions": additions,
        "deletions": deletions,
        "changed_files": 2,
        "head": {"sha": head_sha},
    }


def test_user_facing_pr_requires_completed_product_acceptance() -> None:
    violations = pr_policy.evaluate_policy(_pr(_body()), ["gateway/agent_workspace.py"])
    assert any("product acceptance" in item.lower() for item in violations)


def test_completed_product_acceptance_passes() -> None:
    violations = pr_policy.evaluate_policy(_pr(_body(accepted=True)), ["gateway/agent_workspace.py"])
    assert violations == []


def test_not_user_facing_override_passes_with_reason() -> None:
    violations = pr_policy.evaluate_policy(_pr(_body(not_user_facing=True)), ["tests/test_example.py"])
    assert violations == []


def test_risky_scope_requires_label_and_exact_head_approval_receipt() -> None:
    sha = "a" * 40
    base = _body(not_user_facing=True)
    missing = pr_policy.evaluate_policy(
        _pr(base, labels=(pr_policy.RISK_APPROVED_LABEL,), head_sha=sha),
        [".github/workflows/tests.yml"],
    )
    assert any("exact-head risk approval" in item.lower() for item in missing)

    approved_body = base + f"\nRisk approval: APPROVE {sha} — workflow hardening approved\n"
    approved = pr_policy.evaluate_policy(
        _pr(approved_body, labels=(pr_policy.RISK_APPROVED_LABEL,), head_sha=sha),
        [".github/workflows/tests.yml"],
    )
    assert approved == []

    stale = pr_policy.evaluate_policy(
        _pr(approved_body, labels=(pr_policy.RISK_APPROVED_LABEL,), head_sha="b" * 40),
        [".github/workflows/tests.yml"],
        event_action="labeled",
    )
    assert any("exact-head risk approval" in item.lower() for item in stale)


def test_large_change_requires_label_and_exact_head_approval_receipt() -> None:
    sha = "a" * 40
    base = _body(not_user_facing=True)
    missing = pr_policy.evaluate_policy(
        _pr(base, labels=(pr_policy.LARGE_CHANGE_APPROVED_LABEL,), additions=1600, deletions=20, head_sha=sha),
        ["gateway/builder_supervisor.py"],
    )
    assert any("exact-head large-change approval" in item.lower() for item in missing)

    approved_body = base + f"\nLarge-change approval: APPROVE {sha} — scope reviewed\n"
    approved = pr_policy.evaluate_policy(
        _pr(approved_body, labels=(pr_policy.LARGE_CHANGE_APPROVED_LABEL,), additions=1600, deletions=20, head_sha=sha),
        ["gateway/builder_supervisor.py"],
    )
    assert approved == []


def test_dependabot_waives_template_but_not_exact_head_risk_approval() -> None:
    pr = _pr("dependency update", author="dependabot[bot]")
    violations = pr_policy.evaluate_policy(pr, ["requirements.txt"])
    assert any("risk/approved" in item for item in violations)


def test_pr_policy_workflow_has_stable_required_check_name() -> None:
    from pathlib import Path

    workflow = Path(__file__).parents[1] / ".github" / "workflows" / "pr-policy.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "pr-policy:" in text
    assert "name: pr-policy" in text
    assert "synchronize" in text
    assert "labeled" in text
    assert "unlabeled" in text


def test_risk_guardrail_uses_label_approval_and_reacts_to_label_changes() -> None:
    from pathlib import Path

    workflow = Path(__file__).parents[1] / ".github" / "workflows" / "pr-risk-guardrails.yml"
    text = workflow.read_text(encoding="utf-8")
    assert pr_policy.RISK_APPROVED_LABEL in text
    assert "labeled" in text and "unlabeled" in text
    assert "Manual approval:\\s*YES" not in text
    assert "isDependabot" not in text
    assert "Risk approval: APPROVE" in text
    assert "pr.head.sha" in text




def test_pr_template_documents_exact_head_approval_receipts() -> None:
    from pathlib import Path

    text = (Path(__file__).parents[1] / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    assert "Risk approval: APPROVE <full-head-SHA>" in text
    assert "Large-change approval: APPROVE <full-head-SHA>" in text
    assert "Review override: APPROVE <full-head-SHA>" in text



def test_main_evaluates_current_pr_from_api_not_event_snapshot(tmp_path, monkeypatch) -> None:
    import json

    sha = "a" * 40
    stale = _pr(_body(not_user_facing=True), head_sha=sha)
    stale["number"] = 12
    current_body = _body(not_user_facing=True) + f"\nRisk approval: APPROVE {sha} — current approval\n"
    current = _pr(current_body, labels=(pr_policy.RISK_APPROVED_LABEL,), head_sha=sha)
    current["number"] = 12
    event = {
        "action": "edited",
        "pull_request": stale,
        "repository": {"owner": {"login": "jacob202"}, "name": "kitty"},
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    def fake_github_json(url: str, _token: str):
        if url.endswith("/pulls/12"):
            return current
        if "/pulls/12/files?" in url:
            return [{"filename": ".github/workflows/tests.yml"}]
        raise AssertionError(url)

    monkeypatch.setattr(pr_policy, "_github_json", fake_github_json)
    pr_policy.main()
