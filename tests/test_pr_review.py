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
