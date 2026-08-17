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


def test_main_blocks_actionable_findings_on_exact_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    finding = "- File: gateway/example.py\n  Failure: exact bad outcome"
    monkeypatch.setattr(
        pr_review,
        "get_pr_diff",
        lambda: ("diff", 12, "owner", "repo", "abcdef1234567890"),
    )
    monkeypatch.setattr(pr_review, "review_diff", lambda _diff: finding)
    monkeypatch.setattr(
        pr_review,
        "upsert_review",
        lambda review, *_args: seen.append(review),
    )

    with pytest.raises(SystemExit) as exc:
        pr_review.main()

    assert exc.value.code == 1
    assert seen == [pr_review.REVIEW_PENDING, finding]


def test_main_passes_only_no_findings_on_exact_head(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        pr_review,
        "get_pr_diff",
        lambda: ("diff", 12, "owner", "repo", "abcdef1234567890"),
    )
    monkeypatch.setattr(pr_review, "review_diff", lambda _diff: pr_review.NO_FINDINGS)
    monkeypatch.setattr(
        pr_review,
        "upsert_review",
        lambda review, *_args: seen.append(review),
    )

    pr_review.main()

    assert seen == [pr_review.REVIEW_PENDING, pr_review.NO_FINDINGS]


def test_review_diff_covers_every_chunk_and_aggregates_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(pr_review, "MAX_REVIEW_CHARS", 12)

    def fake_review_chunk(chunk: str) -> str:
        seen.append(chunk)
        return "finding-two" if "BBBB" in chunk else pr_review.NO_FINDINGS

    monkeypatch.setattr(pr_review, "_review_chunk", fake_review_chunk)
    diff = "AAAAAAAAAAAA" + "BBBBBBBBBBBB" + "CCCCCCCCCCCC"

    verdict = pr_review.review_diff(diff)

    assert len(seen) == 3
    assert "".join(seen) == diff
    assert verdict == "finding-two"


def test_review_diff_fails_closed_when_any_chunk_has_no_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pr_review, "MAX_REVIEW_CHARS", 5)
    answers = iter([pr_review.NO_FINDINGS, None])
    monkeypatch.setattr(pr_review, "_review_chunk", lambda _chunk: next(answers))

    assert pr_review.review_diff("abcdefghij") is None


def test_agent_review_workflow_rereviews_synchronize_events_and_exposes_required_gate() -> None:
    from pathlib import Path

    workflow = (
        Path(__file__).parents[1] / ".github" / "workflows" / "pr-agent-review.yml"
    ).read_text(encoding="utf-8")

    assert "Skip automatic re-review after a push" not in workflow
    assert "github.event.action != 'synchronize'" not in workflow
    assert "review-gate:" in workflow
    assert "name: review-gate" in workflow


def test_prompt_rejects_generic_speculative_review_noise() -> None:
    prompt = pr_review.SYSTEM_PROMPT.lower()
    assert "may" in prompt and "could" in prompt
    assert "do not report" in prompt
    assert "exact input" in prompt or "exact state" in prompt


def test_default_reviewer_uses_minimax_m3_candidate() -> None:
    assert pr_review.DEFAULT_REVIEW_MODEL == "minimax/minimax-m3"


def test_exact_head_override_requires_label_full_sha_and_reason() -> None:
    sha = "a" * 40
    body = f"Review override: APPROVE {sha} — independently checked false positive"
    assert pr_review.parse_exact_head_override(body, {pr_review.REVIEW_OVERRIDE_LABEL}, sha)
    assert pr_review.parse_exact_head_override(body, set(), sha) is None
    assert pr_review.parse_exact_head_override(body.replace(sha, "b" * 40), {pr_review.REVIEW_OVERRIDE_LABEL}, sha) is None
    assert pr_review.parse_exact_head_override(f"Review override: APPROVE {sha}", {pr_review.REVIEW_OVERRIDE_LABEL}, sha) is None


def test_main_allows_explicit_exact_head_override_without_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        pr_review,
        "get_pr_diff",
        lambda: ("diff", 12, "owner", "repo", "abcdef1234567890"),
    )
    monkeypatch.setattr(pr_review, "get_exact_head_override", lambda _sha: "verified false positive")
    monkeypatch.setattr(
        pr_review,
        "review_diff",
        lambda _diff: (_ for _ in ()).throw(AssertionError("model should not run")),
    )
    monkeypatch.setattr(pr_review, "upsert_review", lambda review, *_args: seen.append(review))

    pr_review.main()

    assert seen[0] == pr_review.REVIEW_PENDING
    assert "verified false positive" in seen[1]
    assert "override" in seen[1].lower()


def test_agent_review_workflow_rechecks_override_metadata_changes() -> None:
    from pathlib import Path

    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "pr-agent-review.yml").read_text(encoding="utf-8")
    assert "edited" in workflow
    assert "labeled" in workflow
    assert "unlabeled" in workflow


def test_review_chunk_retries_transient_empty_content(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps(self.payload).encode()

    replies = iter(
        [
            {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]},
            {"choices": [{"message": {"content": pr_review.NO_FINDINGS}, "finish_reason": "stop"}]},
        ]
    )
    calls: list[int] = []

    def fake_urlopen(_request, timeout=0):
        calls.append(timeout)
        return FakeResponse(next(replies))

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(pr_review, "urlopen", fake_urlopen)
    monkeypatch.setattr(pr_review.time, "sleep", lambda _seconds: None)

    assert pr_review._review_chunk("diff") == pr_review.NO_FINDINGS
    assert len(calls) == 2
