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


def _pr(body: str, *, labels: tuple[str, ...] = (), additions: int = 20, deletions: int = 5, author: str = "jacob202") -> dict:
    return {
        "body": body,
        "user": {"login": author},
        "labels": [{"name": label} for label in labels],
        "additions": additions,
        "deletions": deletions,
        "changed_files": 2,
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


def test_risky_scope_requires_explicit_approval_label_not_body_text() -> None:
    body = _body(not_user_facing=True).replace("Manual approval: NO", "Manual approval: YES")
    violations = pr_policy.evaluate_policy(_pr(body), [".github/workflows/tests.yml"])
    assert any("risk/approved" in item for item in violations)

    approved = pr_policy.evaluate_policy(
        _pr(body, labels=(pr_policy.RISK_APPROVED_LABEL,)),
        [".github/workflows/tests.yml"],
    )
    assert approved == []


def test_large_change_requires_large_change_approval() -> None:
    violations = pr_policy.evaluate_policy(
        _pr(_body(not_user_facing=True), additions=1600, deletions=20),
        ["gateway/builder_supervisor.py"],
    )
    assert any(pr_policy.LARGE_CHANGE_APPROVED_LABEL in item for item in violations)


def test_dependabot_waives_template_but_not_risky_approval() -> None:
    pr = _pr("dependency update", author="dependabot[bot]")
    violations = pr_policy.evaluate_policy(pr, ["requirements.txt"])
    assert violations == [f"risky scope requires label `{pr_policy.RISK_APPROVED_LABEL}`"]


def test_pr_policy_workflow_has_stable_required_check_name() -> None:
    from pathlib import Path

    workflow = Path(__file__).parents[1] / ".github" / "workflows" / "pr-policy.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "pr-policy:" in text
    assert "name: pr-policy" in text
    assert "synchronize" in text
    assert "labeled" in text
    assert "unlabeled" in text
