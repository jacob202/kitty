from pathlib import Path

import pytest

from scripts import pr_review


def test_render_review_body_replaces_no_findings_sentinel() -> None:
    body = pr_review.render_review_body(
        pr_review.NO_FINDINGS,
        "1234567890abcdef1234567890abcdef12345678",
    )

    assert body.startswith(pr_review.COMMENT_MARKER)
    assert "No actionable findings in this diff." in body
    assert "NO_ACTIONABLE_FINDINGS" not in body
    assert "Reviewed commit `1234567890ab`." in body


def test_find_existing_review_comment_uses_only_owned_marker() -> None:
    comments = [
        {"id": 10, "body": "## Agent PR Review\n\nOld unmarked review"},
        {"id": 11, "body": f"{pr_review.COMMENT_MARKER}\n## Agent PR Review"},
        {"id": 12, "body": "unrelated"},
    ]

    assert pr_review.find_existing_review_comment(comments) == 11


def test_find_existing_review_comment_returns_none_without_marker() -> None:
    assert pr_review.find_existing_review_comment(
        [{"id": 10, "body": "unrelated"}, {"id": "11", "body": pr_review.COMMENT_MARKER}]
    ) is None


def test_prompt_requires_concrete_findings_and_exact_empty_result() -> None:
    assert "name the changed file" in pr_review.SYSTEM_PROMPT
    assert "specific failure mode" in pr_review.SYSTEM_PROMPT
    assert pr_review.NO_FINDINGS in pr_review.SYSTEM_PROMPT


def test_upsert_review_fails_loud_without_github_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(SystemExit) as exc:
        pr_review.upsert_review("review", 1, "owner", "repo", "abc")

    assert exc.value.code == 1


def test_pending_review_body_invalidates_old_approval() -> None:
    body = pr_review.render_review_body(
        pr_review.REVIEW_PENDING,
        "abcdef1234567890abcdef1234567890abcdef12",
    )

    assert "Review pending" in body
    assert "abcdef123456" in body
    assert "No actionable findings" not in body
    assert "approve" not in body.lower()


def test_main_marks_current_head_pending_and_fails_if_model_has_no_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        pr_review,
        "get_pr_diff",
        lambda: ("diff", 12, "owner", "repo", "abcdef1234567890"),
    )
    monkeypatch.setattr(pr_review, "review_diff", lambda _diff: None)
    monkeypatch.setattr(
        pr_review,
        "upsert_review",
        lambda review, *_args: seen.append(review),
    )

    with pytest.raises(SystemExit) as exc:
        pr_review.main()

    assert exc.value.code == 1
    assert seen == [pr_review.REVIEW_PENDING]


def test_agent_review_workflow_rereviews_synchronize_events() -> None:
    workflow = (
        Path(__file__).parents[1]
        / ".github"
        / "workflows"
        / "pr-agent-review.yml"
    ).read_text(encoding="utf-8")

    assert "Skip automatic re-review after a push" not in workflow
    assert "github.event.action != 'synchronize'" not in workflow
