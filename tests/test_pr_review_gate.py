from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import pr_review, pr_review_gate

SHA = "a" * 40
OTHER_SHA = "b" * 40


def _comment(body: str, login: str, *, user_type: str = "User") -> dict:
    return {"body": body, "user": {"login": login, "type": user_type}}


def test_agent_no_findings_requires_github_actions_and_full_current_sha() -> None:
    body = pr_review.render_review_body(pr_review.NO_FINDINGS, SHA)
    assert pr_review_gate.agent_review_approved(
        _comment(body, "github-actions[bot]", user_type="Bot"), SHA
    )
    assert not pr_review_gate.agent_review_approved(_comment(body, "stranger"), SHA)
    assert not pr_review_gate.agent_review_approved(
        _comment(body.replace(SHA, OTHER_SHA), "github-actions[bot]", user_type="Bot"), SHA
    )
    assert not pr_review_gate.agent_review_approved(
        _comment(pr_review.render_review_body(pr_review.REVIEW_PENDING, SHA), "github-actions[bot]", user_type="Bot"), SHA
    )


def test_builder_receipt_requires_trusted_actor_exact_sha_and_approve() -> None:
    body = "\n".join([
        pr_review_gate.BUILDER_REVIEW_MARKER,
        "# KittyBuilder review note",
        f"- Reviewed commit: `{SHA}`",
        "- Verdict: approve",
        "- Model: reviewer-model",
    ])
    assert pr_review_gate.builder_review_approved(_comment(body, "jacob202"), SHA, {"jacob202"})
    assert not pr_review_gate.builder_review_approved(_comment(body, "stranger"), SHA, {"jacob202"})
    assert not pr_review_gate.builder_review_approved(
        _comment(body.replace(SHA, OTHER_SHA), "jacob202"), SHA, {"jacob202"}
    )
    assert not pr_review_gate.builder_review_approved(
        _comment(body.replace("approve", "request_changes"), "jacob202"), SHA, {"jacob202"}
    )


def test_evaluate_accepts_live_exact_head_override() -> None:
    pr = {
        "head": {"sha": SHA},
        "body": f"Review override: APPROVE {SHA} — provider unavailable; independently reviewed",
        "labels": [{"name": pr_review.REVIEW_OVERRIDE_LABEL}],
    }
    ok, reason = pr_review_gate.evaluate_review_gate(pr, [], repo_owner="jacob202")
    assert ok
    assert "override" in reason.lower()


def test_evaluate_rejects_missing_or_stale_evidence() -> None:
    pr = {"head": {"sha": SHA}, "body": "", "labels": []}
    stale = _comment(
        pr_review.render_review_body(pr_review.NO_FINDINGS, OTHER_SHA),
        "github-actions[bot]",
        user_type="Bot",
    )
    ok, reason = pr_review_gate.evaluate_review_gate(pr, [stale], repo_owner="jacob202")
    assert not ok
    assert SHA in reason


def test_main_reads_live_pr_and_comments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    event = {
        "pull_request": {"number": 510},
        "repository": {"owner": {"login": "jacob202"}, "name": "kitty"},
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    current_pr = {"head": {"sha": SHA}, "body": "", "labels": []}
    approved = _comment(
        pr_review.render_review_body(pr_review.NO_FINDINGS, SHA),
        "github-actions[bot]",
        user_type="Bot",
    )

    def fake_json(url: str, _token: str = "", **_kwargs):
        if url.endswith("/pulls/510"):
            return current_pr
        if "/issues/510/comments?" in url:
            return [approved]
        raise AssertionError(url)

    # Only this module's own transport seam is stubbed: the gate passes it into
    # the paginated helper, so the seam is preserved rather than bypassed.
    monkeypatch.setattr(pr_review_gate, "_github_json", fake_json)
    pr_review_gate.main()

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == f"GitHub agent review approved exact head {SHA}.\n"


def test_conflicting_exact_head_agent_finding_blocks_builder_approval() -> None:
    finding = _comment(
        pr_review.render_review_body("- gateway/x.py: exact broken outcome", SHA),
        "github-actions[bot]",
        user_type="Bot",
    )
    builder_body = "\n".join([
        pr_review_gate.BUILDER_REVIEW_MARKER,
        "# KittyBuilder review note",
        f"- Reviewed commit: `{SHA}`",
        "- Verdict: approve",
    ])
    builder = _comment(builder_body, "jacob202")
    pr = {"head": {"sha": SHA}, "body": "", "labels": []}

    ok, reason = pr_review_gate.evaluate_review_gate(
        pr, [finding, builder], repo_owner="jacob202"
    )
    assert not ok
    assert "blocking" in reason.lower() or "finding" in reason.lower()


def test_conflicting_exact_head_builder_rejection_blocks_agent_approval() -> None:
    agent = _comment(
        pr_review.render_review_body(pr_review.NO_FINDINGS, SHA),
        "github-actions[bot]",
        user_type="Bot",
    )
    builder_body = "\n".join([
        pr_review_gate.BUILDER_REVIEW_MARKER,
        "# KittyBuilder review note",
        f"- Reviewed commit: `{SHA}`",
        "- Verdict: request_changes",
    ])
    builder = _comment(builder_body, "jacob202")
    pr = {"head": {"sha": SHA}, "body": "", "labels": []}

    ok, reason = pr_review_gate.evaluate_review_gate(
        pr, [agent, builder], repo_owner="jacob202"
    )
    assert not ok
    assert "blocking" in reason.lower() or "request" in reason.lower()


def test_stalled_review_is_reported_as_no_verdict_not_a_finding() -> None:
    """A truncated review must not be reported as a defect that was found.

    Observed live on PR #869: the reviewer stalled, and the workflow rendered the
    model's partial reasoning as a review body. The gate correctly refused to
    approve it, but described it as a blocking finding, sending an operator after a
    finding that was never produced.
    """
    stalled = _comment(
        pr_review.render_review_body(
            "Looking at this diff, I need to verify the claims made in the comments "
            "and check for concrete defects. Let me examine the actual code.",
            SHA,
        ),
        "github-actions[bot]",
        user_type="Bot",
    )
    pr = {"head": {"sha": SHA}, "body": "", "labels": []}

    ok, reason = pr_review_gate.evaluate_review_gate(pr, [stalled], repo_owner="jacob202")
    assert not ok, "an unusable review must never approve"
    assert "no usable verdict" in reason
    assert "Blocking GitHub agent review finding exists" not in reason


def test_finding_without_rubric_fields_still_reports_a_blocking_finding() -> None:
    """The distinction is diagnostic only: a body naming a file is still a finding."""
    finding = _comment(
        pr_review.render_review_body("- gateway/x.py: exact broken outcome", SHA),
        "github-actions[bot]",
        user_type="Bot",
    )
    pr = {"head": {"sha": SHA}, "body": "", "labels": []}

    ok, reason = pr_review_gate.evaluate_review_gate(pr, [finding], repo_owner="jacob202")
    assert not ok
    assert "Blocking GitHub agent review finding exists" in reason


def test_blocking_set_is_unchanged_by_the_reason_split() -> None:
    """Both shapes block identically; only the message differs.

    Guards the property that made this change safe: the reason split must not move
    anything into or out of the blocking set.
    """
    stalled = _comment(
        pr_review.render_review_body("Let me examine the actual code.", SHA),
        "github-actions[bot]",
        user_type="Bot",
    )
    finding = _comment(
        pr_review.render_review_body("- gateway/x.py: exact broken outcome", SHA),
        "github-actions[bot]",
        user_type="Bot",
    )
    assert pr_review_gate.agent_review_blocked(stalled, SHA)
    assert pr_review_gate.agent_review_blocked(finding, SHA)
    assert not pr_review_gate.agent_review_approved(stalled, SHA)
    assert not pr_review_gate.agent_review_approved(finding, SHA)


def test_clean_verdict_that_mentions_a_path_is_still_clean() -> None:
    """A sentinel verdict may discuss a file without becoming a finding.

    Regression (review finding): routing the path heuristic through the approval
    decision meant a clean verdict that merely mentioned `gateway/x.py` while
    explaining why nothing was actionable was treated as a blocking finding. A path
    mention must never veto a sentinel; only the rubric's explicit fields may.
    """
    body = pr_review.render_review_body(
        "Checked gateway/x.py and the changed hunk is correct.\n\n"
        f"{pr_review.NO_FINDINGS}",
        SHA,
    )
    comment = _comment(body, "github-actions[bot]", user_type="Bot")
    assert pr_review_gate.agent_review_approved(comment, SHA)
    assert not pr_review_gate.agent_review_blocked(comment, SHA)


def test_sentinel_with_rubric_fields_is_still_blocking() -> None:
    """The documented contradiction case is unchanged by the reason split."""
    body = pr_review.render_review_body(
        f"{pr_review.NO_FINDINGS}\n\nFailure Mode: the retry loop double-charges.",
        SHA,
    )
    comment = _comment(body, "github-actions[bot]", user_type="Bot")
    assert not pr_review_gate.agent_review_approved(comment, SHA)
    assert pr_review_gate.agent_review_blocked(comment, SHA)
