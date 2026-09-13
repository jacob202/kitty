import json

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
    assert "Reviewed commit `1234567890abcdef1234567890abcdef12345678`." in body


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


def test_find_existing_review_comment_is_scoped_to_the_head() -> None:
    """Runs for different heads must never share one comment."""
    other, mine = "a" * 40, "b" * 40
    comments = [
        {"id": 11, "body": f"{pr_review.COMMENT_MARKER}\nReviewed commit `{other}`."},
        {"id": 12, "body": f"{pr_review.COMMENT_MARKER}\nReviewed commit `{mine}`."},
    ]

    assert pr_review.find_existing_review_comment(comments, mine) == 12
    assert pr_review.find_existing_review_comment(comments, "c" * 40) is None


def test_issue_comments_follows_pagination() -> None:
    """A full first page must not hide the newest evidence from the gate."""
    pages = {1: [{"id": i} for i in range(100)], 2: [{"id": 100}]}
    seen: list[int] = []

    def fetch(url, _token):
        page = int(str(url).rsplit("page=", 1)[1])
        seen.append(page)
        return pages[page]

    comments = pr_review.issue_comments("owner", "repo", 1, "token", fetch=fetch)

    assert len(comments) == 101
    assert seen == [1, 2]


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


def test_main_publishes_an_explicit_failure_and_exits_when_no_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        pr_review,
        "get_pr_diff",
        lambda: ("diff", 12, "owner", "repo", "abcdef1234567890"),
    )
    monkeypatch.setattr(pr_review, "review_diff", lambda _diff: None)
    monkeypatch.setattr(pr_review, "get_exact_head_override", lambda _sha: None)
    monkeypatch.setattr(pr_review, "_head_still_current", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        pr_review,
        "upsert_review",
        lambda review, *_args: seen.append(review) or True,
    )

    with pytest.raises(SystemExit) as exc:
        pr_review.main()

    assert exc.value.code == 1
    assert seen == [pr_review.REVIEW_PENDING, pr_review.REVIEW_FAILED]


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
    monkeypatch.setattr(pr_review, "get_exact_head_override", lambda _sha: None)
    monkeypatch.setattr(pr_review, "_head_still_current", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        pr_review,
        "upsert_review",
        lambda review, *_args: seen.append(review) or True,
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
    monkeypatch.setattr(pr_review, "get_exact_head_override", lambda _sha: None)
    monkeypatch.setattr(pr_review, "_head_still_current", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        pr_review,
        "upsert_review",
        lambda review, *_args: seen.append(review) or True,
    )

    pr_review.main()

    assert seen == [pr_review.REVIEW_PENDING, pr_review.NO_FINDINGS]


def test_review_diff_covers_every_chunk_and_aggregates_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(pr_review, "MAX_REVIEW_CHARS", 12)

    def fake_review_chunk(chunk: str, **_kwargs: object) -> str:
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
    monkeypatch.setattr(pr_review, "_review_chunk", lambda _chunk, **_kwargs: next(answers))

    assert pr_review.review_diff("abcdefghij") is None


def test_agent_review_workflow_uses_trusted_code_and_avoids_model_reruns_on_metadata() -> None:
    from pathlib import Path

    workflow = (
        Path(__file__).parents[1] / ".github" / "workflows" / "pr-agent-review.yml"
    ).read_text(encoding="utf-8")

    assert "pull_request_target:\n" in workflow
    assert "\n  pull_request:\n" not in workflow
    assert "agent-review:" in workflow
    assert "name: agent-review" in workflow
    assert "continue-on-error: true" in workflow
    assert "github.event.repository.default_branch" in workflow
    assert "github.event.action == 'synchronize'" in workflow
    assert "github.event.action == 'edited'" not in workflow
    assert "github.event.action == 'labeled'" not in workflow
    assert "github.event.action == 'unlabeled'" not in workflow
    assert "policy-gate:" in workflow
    assert "name: policy-gate" in workflow
    assert "needs: [scope, agent-review]" in workflow
    assert "python -m scripts.pr_policy" in workflow
    assert "review-gate:" not in workflow
    assert "review/evidence-current" not in workflow
    assert "review-concurrency-class" in workflow

def test_prompt_rejects_generic_speculative_review_noise() -> None:
    prompt = pr_review.SYSTEM_PROMPT.lower()
    assert "may" in prompt and "could" in prompt
    assert "do not report" in prompt
    assert "exact input" in prompt or "exact state" in prompt


def test_default_github_reviewer_uses_paid_flash_model() -> None:
    assert pr_review.DEFAULT_REVIEW_MODEL == "openrouter/deepseek/deepseek-v4-flash"


def test_deepseek_implementation_routes_to_independent_paid_pair() -> None:
    assert pr_review.select_review_models(
        "openrouter/deepseek/deepseek-v4-flash",
        "openrouter/minimax/minimax-m3",
        "openrouter/deepseek/deepseek-v4-pro",
    ) == (
        "openrouter/minimax/minimax-m3",
        "openrouter/qwen/qwen3.7-plus",
    )


def test_builder_event_exposes_recorded_implementation_model() -> None:
    event = {
        "pull_request": {
            "body": """## KittyBuilder task `kb_test`

## Final report

```json
{"model": "openrouter/deepseek/deepseek-v4-pro"}
```
"""
        }
    }

    assert pr_review.implementation_model_from_event(event) == (
        "openrouter/deepseek/deepseek-v4-pro"
    )


def test_review_chunk_uses_independent_model_for_deepseek_builder_event(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps(
            {
                "pull_request": {
                    "body": """## KittyBuilder task `kb_test`

## Final report

```json
{"model": "openrouter/deepseek/deepseek-v4-pro"}
```
"""
                }
            }
        )
    )
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = pr_review.NO_FINDINGS + "\n"
        stderr = ""

    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        pr_review.subprocess, "run", lambda command, **_kwargs: calls.append(command) or Result()
    )

    assert pr_review._review_chunk("diff") == pr_review.NO_FINDINGS
    command = calls[0]
    assert command[command.index("--model") + 1] == "openrouter/minimax/minimax-m3"


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
    monkeypatch.setattr(pr_review, "upsert_review", lambda review, *_args: seen.append(review) or True)

    pr_review.main()

    assert seen[0] == pr_review.REVIEW_PENDING
    assert "verified false positive" in seen[1]
    assert "override" in seen[1].lower()


def test_agent_review_workflow_rechecks_override_metadata_without_recalling_model() -> None:
    from pathlib import Path

    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "pr-agent-review.yml").read_text(encoding="utf-8")
    assert "edited" in workflow
    assert "labeled" in workflow
    assert "unlabeled" in workflow
    assert "github.event.action == 'edited'" not in workflow
    assert "github.event.action == 'labeled'" not in workflow
    assert "github.event.action == 'unlabeled'" not in workflow

def test_review_request_uses_restricted_opencode_agent_and_paid_flash_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = pr_review.NO_FINDINGS + "\n"
        stderr = ""

    def fake_run(command, **_kwargs):
        calls.append(command)
        return Result()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(pr_review.subprocess, "run", fake_run)

    assert pr_review._review_chunk("diff") == pr_review.NO_FINDINGS
    command = calls[0]
    assert command[:2] == ["opencode", "run"]
    assert command[command.index("--agent") + 1] == "pr-reviewer"
    assert command[command.index("--model") + 1] == "openrouter/deepseek/deepseek-v4-flash"
    assert "untrusted review data" in command[-1]


def test_review_chunk_falls_back_to_different_model_once(monkeypatch: pytest.MonkeyPatch) -> None:
    outputs = iter(["", pr_review.NO_FINDINGS + "\n"])
    calls: list[tuple[list[str], int]] = []

    class Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def fake_run(command, **kwargs):
        calls.append((command, kwargs["timeout"]))
        return Result(next(outputs))

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.setattr(pr_review.subprocess, "run", fake_run)

    assert pr_review._review_chunk("diff") == pr_review.NO_FINDINGS
    assert [call[0][call[0].index("--model") + 1] for call in calls] == [
        "openrouter/deepseek/deepseek-v4-flash",
        "openrouter/minimax/minimax-m3",
    ]
    assert [timeout for _command, timeout in calls] == [240, 240]



def test_get_pr_diff_binds_diff_to_live_current_head(tmp_path, monkeypatch) -> None:
    import json

    event = {
        "pull_request": {
            "number": 12,
            "url": "https://api.github.com/repos/jacob202/kitty/pulls/12",
            "head": {"sha": "b" * 40},
        },
        "repository": {"owner": {"login": "jacob202"}, "name": "kitty"},
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    live_sha = "a" * 40
    responses = iter([
        json.dumps({"head": {"sha": live_sha}}).encode(),
        b"diff --git a/a b/a\n",
        json.dumps({"head": {"sha": live_sha}}).encode(),
    ])
    accepts: list[str] = []

    class FakeResponse:
        def __init__(self, data: bytes) -> None:
            self.data = data
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self) -> bytes:
            return self.data

    def fake_urlopen(request, timeout=0):
        accepts.append(request.get_header("Accept"))
        return FakeResponse(next(responses))

    monkeypatch.setattr(pr_review, "urlopen", fake_urlopen)
    diff, number, owner, repo, head_sha = pr_review.get_pr_diff()
    assert (number, owner, repo) == (12, "jacob202", "kitty")
    assert head_sha == live_sha
    assert diff.startswith("diff --git")
    assert accepts == [
        "application/vnd.github+json",
        "application/vnd.github.v3.diff",
        "application/vnd.github+json",
    ]


def test_get_pr_diff_fails_closed_if_head_changes_during_fetch(tmp_path, monkeypatch) -> None:
    import json

    event = {
        "pull_request": {"number": 12, "url": "https://api.github.com/repos/jacob202/kitty/pulls/12"},
        "repository": {"owner": {"login": "jacob202"}, "name": "kitty"},
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    responses = iter([
        json.dumps({"head": {"sha": "a" * 40}}).encode(),
        b"diff --git a/a b/a\n",
        json.dumps({"head": {"sha": "c" * 40}}).encode(),
    ])

    class FakeResponse:
        def __init__(self, data: bytes) -> None:
            self.data = data
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self) -> bytes: return self.data

    monkeypatch.setattr(pr_review, "urlopen", lambda _request, timeout=0: FakeResponse(next(responses)))
    with pytest.raises(SystemExit) as exc:
        pr_review.get_pr_diff()
    assert exc.value.code == 1



def test_exact_head_override_reads_live_pr_state_not_event_snapshot(tmp_path, monkeypatch) -> None:
    import json

    sha = "a" * 40
    event = {
        "pull_request": {
            "number": 12,
            "url": "https://api.github.com/repos/jacob202/kitty/pulls/12",
            "body": "stale event body",
            "labels": [],
        },
        "repository": {"owner": {"login": "jacob202"}, "name": "kitty"},
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    current = {
        "head": {"sha": sha},
        "body": f"Review override: APPROVE {sha} — independently verified provider outage",
        "labels": [{"name": pr_review.REVIEW_OVERRIDE_LABEL}],
    }

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self) -> bytes: return json.dumps(current).encode()

    monkeypatch.setattr(pr_review, "urlopen", lambda _request, timeout=0: FakeResponse())
    assert pr_review.get_exact_head_override(sha) == "independently verified provider outage"


def test_review_diff_stops_at_the_total_budget_without_calling_a_model(monkeypatch) -> None:
    """Exhausting the whole-review budget must fail explicitly, not run past it.

    MAX_REVIEW_CHUNKS permits 12 chunks, so the permitted worst case cannot fit
    inside any sane job timeout. The harness bounds its own total work instead.
    """
    monkeypatch.setattr(pr_review, "REVIEW_TOTAL_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(pr_review, "_review_chunks", lambda _diff: ["a", "b"])
    called: list[str] = []

    def _fail(*_args, **_kwargs):
        called.append("chunk")
        raise AssertionError("no chunk may be reviewed after the budget is gone")

    monkeypatch.setattr(pr_review, "_review_chunk", _fail)
    assert pr_review.review_diff("diff") is None
    assert called == []


def test_failure_body_is_not_exact_head_review_evidence() -> None:
    """A budget failure must read as unapproved, never as a completed review."""
    body = pr_review.render_review_body(pr_review.REVIEW_FAILED, "a" * 40)
    assert "Reviewed commit" not in body
    assert "neither an approval nor a finding" in body


def test_model_timeout_is_reclipped_to_the_remaining_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each fallback attempt gets what is actually left, not a stale per-chunk value."""
    monkeypatch.setattr(pr_review, "REVIEW_MODEL_TIMEOUT_SECONDS", 240)
    now = pr_review.time.monotonic()
    assert pr_review._model_timeout(None) == 240
    assert pr_review._model_timeout(now + 1000) == 240
    assert pr_review._model_timeout(now + 30) <= 30
    assert pr_review._model_timeout(now - 1) <= 0


def test_stale_runs_do_not_overwrite_a_newer_heads_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One shared comment: a run for an old head must not clobber the current one."""
    monkeypatch.setattr(
        pr_review,
        "_fetch_current_pr",
        lambda *_args, **_kwargs: {"head": {"sha": "b" * 40}},
    )
    assert pr_review._head_still_current(1, "owner", "repo", "a" * 40) is False
    assert pr_review._head_still_current(1, "owner", "repo", "b" * 40) is True


def test_head_lookup_failure_is_loud_not_silent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unreadable head must raise: a silent skip would hide the API failure."""

    def _boom(*_args, **_kwargs):
        raise OSError("api down")

    monkeypatch.setattr(pr_review, "_fetch_current_pr", _boom)
    with pytest.raises(OSError, match="api down"):
        pr_review._head_still_current(1, "owner", "repo", "a" * 40)


def test_upsert_review_skips_the_write_when_the_head_moved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard sits last before the write, so a stale run touches nothing."""
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(pr_review, "_head_still_current", lambda *_args, **_kwargs: False)
    calls: list[str] = []
    monkeypatch.setattr(
        pr_review,
        "github_json",
        lambda url, *_args, **_kwargs: calls.append(url) or [],
    )

    published = pr_review.upsert_review(pr_review.NO_FINDINGS, 1, "owner", "repo", "a" * 40)

    # Only the read happened; no mutating request was ever attempted.
    assert published is False
    assert len(calls) == 1
    assert calls[0].endswith("/comments?per_page=100&page=1")


def test_main_aborts_before_the_model_when_the_pending_write_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale head must stop the run before the paid review, not after it."""
    monkeypatch.setattr(
        pr_review, "get_pr_diff", lambda: ("diff", 12, "owner", "repo", "a" * 40)
    )
    monkeypatch.setattr(pr_review, "upsert_review", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(pr_review, "_head_still_current", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        pr_review, "review_diff", lambda _diff: pytest.fail("model review must not run")
    )

    with pytest.raises(SystemExit) as exc:
        pr_review.main()

    assert exc.value.code == 1


def test_main_does_nothing_when_the_head_already_has_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A same-head rerun with existing evidence must not re-run the model."""
    monkeypatch.setattr(
        pr_review, "get_pr_diff", lambda: ("diff", 12, "owner", "repo", "a" * 40)
    )
    monkeypatch.setattr(pr_review, "upsert_review", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(pr_review, "_head_still_current", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        pr_review, "review_diff", lambda _diff: pytest.fail("model review must not run")
    )

    pr_review.main()


def test_pending_publish_does_not_replace_an_existing_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rerun's pending marker must not erase this head's own verdict."""
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(pr_review, "_head_still_current", lambda *_args, **_kwargs: True)
    existing = {
        "id": 9,
        "body": pr_review.render_review_body(pr_review.NO_FINDINGS, "a" * 40),
    }
    calls: list[str] = []
    monkeypatch.setattr(
        pr_review,
        "github_json",
        lambda url, *_args, **_kwargs: calls.append(url) or [existing],
    )

    published = pr_review.upsert_review(
        pr_review.REVIEW_PENDING, 1, "owner", "repo", "a" * 40
    )

    assert published is False
    assert len(calls) == 1  # read only: the verdict survived


def test_failure_publish_replaces_a_pending_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pending marker is not a verdict: a no-verdict run must still say so."""
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(pr_review, "_head_still_current", lambda *_args, **_kwargs: True)
    pending = {
        "id": 9,
        "body": pr_review.render_review_body(pr_review.REVIEW_PENDING, "a" * 40),
    }
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        pr_review,
        "github_json",
        lambda url, *_args, **kwargs: calls.append((url, str(kwargs.get("method"))))
        or [pending],
    )

    published = pr_review.upsert_review(
        pr_review.REVIEW_FAILED, 1, "owner", "repo", "a" * 40
    )

    assert published is True
    assert calls[-1][1] == "PATCH"


def test_marker_bodies_are_distinguishable_from_a_verdict() -> None:
    """The rendered no-verdict bodies must carry their marker, and verdicts must not."""
    pending = pr_review.render_review_body(pr_review.REVIEW_PENDING, "a" * 40)
    failed = pr_review.render_review_body(pr_review.REVIEW_FAILED, "a" * 40)
    verdict = pr_review.render_review_body(pr_review.NO_FINDINGS, "a" * 40)

    assert pr_review._is_no_verdict_body(pending) is True
    assert pr_review._is_no_verdict_body(failed) is True
    assert pr_review._is_no_verdict_body(verdict) is False


def test_clean_verdict_does_not_replace_an_existing_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A clean rerun must not erase a finding and unblock the head."""
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(pr_review, "_head_still_current", lambda *_args, **_kwargs: True)
    finding = {
        "id": 9,
        "body": pr_review.render_review_body("A real problem in this diff.", "a" * 40),
    }
    calls: list[str] = []
    monkeypatch.setattr(
        pr_review,
        "github_json",
        lambda url, *_args, **_kwargs: calls.append(url) or [finding],
    )

    published = pr_review.upsert_review(
        pr_review.NO_FINDINGS, 1, "owner", "repo", "a" * 40
    )

    assert published is False
    assert len(calls) == 1  # read only: the finding survived


def test_finding_verdict_does_replace_a_clean_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The conservative direction stays open so a finding can always land."""
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(pr_review, "_head_still_current", lambda *_args, **_kwargs: True)
    clean = {
        "id": 9,
        "body": pr_review.render_review_body(pr_review.NO_FINDINGS, "a" * 40),
    }
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        pr_review,
        "github_json",
        lambda url, *_args, **kwargs: calls.append((url, str(kwargs.get("method"))))
        or [clean],
    )

    published = pr_review.upsert_review(
        "A real problem in this diff.", 1, "owner", "repo", "a" * 40
    )

    assert published is True
    assert calls[-1][1] == "PATCH"


def test_failure_publish_does_not_replace_an_existing_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rerun that found no verdict must not erase a good one for the same head."""
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(pr_review, "_head_still_current", lambda *_args, **_kwargs: True)
    existing = {
        "id": 9,
        "body": pr_review.render_review_body(pr_review.NO_FINDINGS, "a" * 40),
    }
    calls: list[str] = []
    monkeypatch.setattr(
        pr_review,
        "github_json",
        lambda url, *_args, **_kwargs: calls.append(url) or [existing],
    )

    published = pr_review.upsert_review(
        pr_review.REVIEW_FAILED, 1, "owner", "repo", "a" * 40
    )

    assert published is False
    assert len(calls) == 1  # read only: the existing verdict was left alone
