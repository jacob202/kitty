"""Contract tests for the three validation clocks.

Clock A is interactive development: a draft PR must not consume the merge suite.
Clock B is ready-to-merge validation: scope-appropriate deterministic evidence
plus the two trusted gates. Clock C is the nightly broad/drift sweep.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

DRAFT_GUARD = "github.event.pull_request.draft == false"
SCOPE_GATED_JOBS = (
    "pytest", "pytest-integration", "lint", "typecheck", "kitty-chat", "browser-smoke"
)


def _workflow(name: str) -> tuple[str, dict]:
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    return text, yaml.safe_load(text)


def _triggers(workflow: dict) -> dict:
    # PyYAML parses a bare `on:` key as the boolean True.
    return workflow.get("on") or workflow[True]


def test_tests_workflow_has_stable_merge_gate_and_scope_detection() -> None:
    text, workflow = _workflow("tests.yml")
    jobs = workflow["jobs"]
    assert "changes" in jobs
    assert "merge-gate" in jobs
    assert jobs["merge-gate"]["name"] == "merge-gate"
    assert "hygiene" not in jobs["merge-gate"]["needs"]
    assert "pytest" in jobs["merge-gate"]["needs"]
    assert "pytest-integration" in jobs["merge-gate"]["needs"]
    assert "needs.changes.outputs.frontend" in text


def test_merge_gate_requires_high_signal_checks_but_accepts_skipped_frontend() -> None:
    text, _ = _workflow("tests.yml")
    for job in SCOPE_GATED_JOBS:
        assert job in text
    assert "skipped" in text


# --- Clock A: draft PRs ----------------------------------------------------


def test_draft_pull_requests_do_not_consume_the_merge_suite() -> None:
    _, workflow = _workflow("tests.yml")
    for name, job in workflow["jobs"].items():
        condition = str(job.get("if", ""))
        if name in ("changes", "merge-gate"):
            assert DRAFT_GUARD in condition, name
        else:
            # Everything else hangs off `changes`, which never runs for a draft.
            assert job["needs"] in ("changes", ["changes", "kitty-chat"]), name


def test_marking_a_pull_request_ready_starts_required_ci_without_another_push() -> None:
    _, workflow = _workflow("tests.yml")
    types = _triggers(workflow)["pull_request"]["types"]
    assert "ready_for_review" in types
    assert "converted_to_draft" in types
    for required in ("opened", "synchronize", "reopened"):
        assert required in types, required


def test_converting_back_to_draft_cancels_superseded_pull_request_work() -> None:
    _, workflow = _workflow("tests.yml")
    concurrency = workflow["concurrency"]
    assert "github.event.pull_request.number" in concurrency["group"]
    assert "github.event_name == 'pull_request'" in str(concurrency["cancel-in-progress"])


# --- Clock B: ready-to-merge validation ------------------------------------


def test_required_jobs_are_scope_gated_on_every_event_including_main_pushes() -> None:
    """A docs-only merge re-running the code suite proves nothing it can act on."""
    _, workflow = _workflow("tests.yml")
    for name in ("pytest", "pytest-integration", "lint", "typecheck"):
        condition = workflow["jobs"][name]["if"]
        assert "needs.changes.outputs.code == 'true'" in condition, name
        assert "github.event_name == 'push'" not in condition, name
    for name in ("kitty-chat", "browser-smoke"):
        condition = workflow["jobs"][name]["if"]
        assert "needs.changes.outputs.frontend == 'true'" in condition, name
        assert "github.event_name == 'push'" not in condition, name


def test_required_checks_run_in_the_merge_queue() -> None:
    """policy-gate and merge-gate are required status checks; a queued PR
    would block forever if either workflow never reports a status for the
    merge_group's temporary commit."""
    _, tests_workflow = _workflow("tests.yml")
    assert "merge_group" in _triggers(tests_workflow)

    _, review_workflow = _workflow("pr-agent-review.yml")
    assert "merge_group" in _triggers(review_workflow)
    for name in ("scope", "policy-gate"):
        condition = str(review_workflow["jobs"][name]["if"])
        assert "github.event_name == 'merge_group'" in condition, name


def test_agent_review_does_not_rerun_for_a_merge_queue_requeue() -> None:
    """Re-spending the model review budget every time a PR is requeued behind
    another merge would be pure waste — the exact-head evidence it already
    produced during the PR's own review still applies."""
    _, workflow = _workflow("pr-agent-review.yml")
    review_if = str(workflow["jobs"]["agent-review"]["if"])
    assert "github.event.action == 'checks_requested'" not in review_if

def test_python_latency_split_keeps_process_integration_required() -> None:
    text, workflow = _workflow("tests.yml")
    jobs = workflow["jobs"]
    assert "pytest-integration" in jobs
    command = "\n".join(
        str(step.get("run", "")) for step in jobs["pytest-integration"]["steps"]
    )
    assert "-m integration" in command
    assert "pytest-integration" in jobs["merge-gate"]["needs"]
    assert "PYTEST_INTEGRATION_RESULT" in text


def test_change_scope_comes_from_the_canonical_classifier() -> None:
    text, workflow = _workflow("tests.yml")
    assert "python -m scripts.pr_scope" in text
    assert "isDocumentation" not in text, "scope logic must not be duplicated in workflow JS"
    outputs = workflow["jobs"]["changes"]["outputs"]
    for key in ("code", "frontend", "sensitive", "docs_only"):
        assert key in outputs, key


def test_model_review_runs_automatically_via_paid_flash_on_each_code_head() -> None:
    text, workflow = _workflow("pr-agent-review.yml")
    review = workflow["jobs"]["agent-review"]
    review_if = str(review["if"])

    assert DRAFT_GUARD in review_if
    assert "github.event.pull_request.author_association == 'OWNER'" in review_if
    assert "needs.scope.outputs.sensitive == 'true'" not in review_if
    for code_action in ("opened", "synchronize", "reopened", "ready_for_review"):
        assert f"github.event.action == '{code_action}'" in review_if
    for metadata_action in ("edited", "labeled", "unlabeled"):
        assert f"github.event.action == '{metadata_action}'" not in review_if

    setup_bun = next(step for step in review["steps"] if str(step.get("uses", "")).startswith("oven-sh/setup-bun@"))
    assert setup_bun
    install = next(step for step in review["steps"] if step.get("name") == "Install OpenCode")
    assert "opencode-ai" in str(install.get("run", ""))

    produce = next(step for step in review["steps"] if step.get("id") == "produce")
    assert produce["run"] == "python scripts/pr_review.py"
    assert produce["env"]["PR_REVIEW_MODEL"] == "openrouter/deepseek/deepseek-v4-flash"
    assert "OPENROUTER_API_KEY" in produce["env"]
    assert "OPENCODE_API_KEY" not in produce["env"]
    assert "claude" not in text.lower()

def test_legacy_claude_code_review_workflow_is_removed() -> None:
    assert not (WORKFLOWS / "claude-code-review.yml").exists()

def test_policy_gate_is_independent_of_the_scope_and_review_jobs() -> None:
    text, workflow = _workflow("pr-agent-review.yml")
    policy_gate = workflow["jobs"]["policy-gate"]
    assert policy_gate["name"] == "policy-gate"
    assert policy_gate["needs"] == ["scope", "agent-review"]
    assert "always()" in policy_gate["if"]
    assert "github.event.repository.default_branch" in text


def test_policy_may_reevaluate_on_metadata_events() -> None:
    _, workflow = _workflow("pr-agent-review.yml")
    types = _triggers(workflow)["pull_request_target"]["types"]
    for action in ("edited", "labeled", "unlabeled"):
        assert action in types, action


def test_auto_label_preserves_manual_approval_labels() -> None:
    _, workflow = _workflow("pr-auto-label.yml")
    step = next(
        step
        for step in workflow["jobs"]["auto-label"]["steps"]
        if step.get("uses") == "actions/labeler@v7"
    )
    assert step["with"]["sync-labels"] is False


# --- Clock C: nightly ------------------------------------------------------


def test_broad_hygiene_moved_off_the_pull_request_clock() -> None:
    _, tests_workflow = _workflow("tests.yml")
    assert "hygiene" not in tests_workflow["jobs"]

    text, nightly = _workflow("nightly-health.yml")
    assert nightly["jobs"]["hygiene"]["continue-on-error"] is True
    for tool in ("vulture", "lychee", "deptry", "pip-audit", "bandit"):
        assert tool in text, tool


def test_nightly_runs_on_a_schedule_and_never_mutates_the_repository() -> None:
    text, nightly = _workflow("nightly-health.yml")
    triggers = _triggers(nightly)
    assert triggers["schedule"][0]["cron"]
    assert "workflow_dispatch" in triggers
    assert nightly["permissions"] == {"contents": "read", "actions": "read"}
    assert "git push" not in text
    assert "--durations" in text
    assert "scripts/ci_metrics.py" in text


# --- Trust: privileged workflows never execute pull-request code ------------


def _checkout_steps(workflow: dict):
    for job_name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            if str(step.get("uses", "")).startswith("actions/checkout"):
                yield job_name, step


def test_privileged_workflows_never_check_out_pull_request_head() -> None:
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text, workflow = _workflow(path.name)
        if "pull_request_target:" not in text and "issue_comment:" not in text:
            continue
        for job_name, step in _checkout_steps(workflow):
            options = step.get("with") or {}
            ref = str(options.get("ref", ""))
            assert "head" not in ref, f"{path.name}:{job_name} checks out PR head"
            assert options.get("persist-credentials") is False, (
                f"{path.name}:{job_name} leaves privileged git credentials in the checkout"
            )


def test_no_workflow_interpolates_untrusted_pull_request_text_into_a_shell() -> None:
    untrusted = (
        "github.event.pull_request.title",
        "github.event.pull_request.body",
        "github.event.pull_request.head.ref",
        "github.event.comment.body",
        "github.event.issue.title",
    )
    for path in sorted(WORKFLOWS.glob("*.yml")):
        _, workflow = _workflow(path.name)
        for job_name, job in workflow.get("jobs", {}).items():
            for step in job.get("steps", []):
                script = str(step.get("run", ""))
                for expression in untrusted:
                    assert expression not in script, f"{path.name}:{job_name} interpolates {expression}"


def test_only_the_repository_owner_can_spend_the_comment_agent_key() -> None:
    _, workflow = _workflow("opencode.yml")
    assert "author_association == 'OWNER'" in workflow["jobs"]["opencode"]["if"]
