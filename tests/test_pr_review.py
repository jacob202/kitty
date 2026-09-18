import json

import pytest

from scripts import pr_review

APPROVE_REVIEW_JSON = '{"schema_version":1,"verdict":"approve","findings":[]}'


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


def test_prompt_requires_concrete_findings_and_exact_machine_record() -> None:
    assert "name the changed file" in pr_review.SYSTEM_PROMPT
    assert "specific failure mode" in pr_review.SYSTEM_PROMPT
    assert '"schema_version":1' in pr_review.SYSTEM_PROMPT
    assert '"verdict":"approve"' in pr_review.SYSTEM_PROMPT
    assert "no markdown, prose, code fence, or thinking text" in pr_review.SYSTEM_PROMPT


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


def test_default_github_reviewer_prefers_the_subscription_route() -> None:
    """The reviewer route must not depend on OpenRouter credit.

    The default moved from `openrouter/deepseek/deepseek-v4-flash` to the
    subscription route on 2026-09-17: the OpenRouter account ran out, every rung
    failed with "requires more credits", and no PR could obtain the exact-head
    verdict its policy requires. The paid rungs are still in the ladder, behind the
    subscription, so the assertion below pins both halves.
    """
    assert pr_review.DEFAULT_REVIEW_MODEL == "opencode-go/muse-spark-1.3-contributor"
    assert pr_review.DEFAULT_REVIEW_FALLBACK_MODEL == "opencode-go/minimax-m3"
    assert pr_review.OPENROUTER_REVIEW_LADDER == (
        "openrouter/deepseek/deepseek-v4-flash",
        "openrouter/minimax/minimax-m3",
    )
    ladder = pr_review.select_review_models(
        pr_review.DEFAULT_REVIEW_MODEL,
        pr_review.DEFAULT_REVIEW_FALLBACK_MODEL,
        None,
    )
    assert ladder[:2] == (
        "opencode-go/muse-spark-1.3-contributor",
        "opencode-go/minimax-m3",
    )
    assert ladder[2:] == pr_review.OPENROUTER_REVIEW_LADDER


def test_deepseek_implementation_routes_to_an_independent_subscription_ladder() -> None:
    """A deepseek implementer must still never be reviewed by a deepseek model.

    The subscription route leads for both implementer families -- otherwise a
    Builder PR (whose final report names a deepseek model) would still need the
    exhausted OpenRouter account -- and the paid rungs follow as the fallback. The
    family filter is asserted directly, so moving the default can never quietly
    let a model review its own work.
    """
    ladder = pr_review.select_review_models(
        "openrouter/deepseek/deepseek-v4-flash",
        "openrouter/minimax/minimax-m3",
        "openrouter/deepseek/deepseek-v4-pro",
    )
    assert ladder == (
        "opencode-go/muse-spark-1.3-contributor",
        "opencode-go/minimax-m3",
        "openrouter/minimax/minimax-m3",
    )
    assert "openrouter/deepseek/deepseek-v4-flash" not in ladder
    assert all(pr_review._model_family(model) != "deepseek" for model in ladder)
    # The implementer's own model is dropped wherever it sits in the ladder, and a
    # different reasoning-effort variant of it is the same model.
    same_model = pr_review.select_review_models(
        "opencode-go/muse-spark-1.3-contributor:medium",
        "opencode-go/minimax-m3",
        "opencode-go/muse-spark-1.3-contributor:max",
    )
    implementer_family = pr_review._model_family("opencode-go/muse-spark-1.3-contributor:max")
    assert "opencode-go/muse-spark-1.3-contributor:medium" not in same_model
    assert same_model[0] == "opencode-go/minimax-m3"
    assert all(
        pr_review._model_family(model) != implementer_family for model in same_model
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
        stdout = APPROVE_REVIEW_JSON + "\n"
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

def test_timed_out_reviewer_is_not_retried_on_later_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model that times out must not be handed a fresh timeout per chunk.

    Observed 2026-09-15 on PR #879: the primary reviewer timed out on all three
    chunks. Each attempt spent 240s of the one shared 900s budget before the
    fallback ran, the budget ran out, and a single unfinished chunk voided the
    whole review -- discarding the chunks the fallback had already reviewed.
    """
    attempted: list[str] = []

    class Result:
        returncode = 0
        stdout = APPROVE_REVIEW_JSON + "\n"
        stderr = ""

    def fake_run(command, **_kwargs):
        model = command[command.index("--model") + 1]
        attempted.append(model)
        if "deepseek" in model:
            raise pr_review.subprocess.TimeoutExpired(cmd=command, timeout=240)
        return Result()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(pr_review.subprocess, "run", fake_run)
    monkeypatch.setattr(
        pr_review, "review_models_for_current_event",
        lambda: ("openrouter/deepseek/deepseek-v4-flash", "openrouter/minimax/minimax-m3"),
    )

    unresponsive: set[str] = set()
    first = pr_review._review_chunk("diff one", unresponsive=unresponsive)
    second = pr_review._review_chunk("diff two", unresponsive=unresponsive)

    assert first == pr_review.NO_FINDINGS
    assert second == pr_review.NO_FINDINGS
    # Chunk one pays for the timeout once; chunk two must go straight to the
    # model that actually answers.
    assert attempted == [
        "openrouter/deepseek/deepseek-v4-flash",
        "openrouter/minimax/minimax-m3",
        "openrouter/minimax/minimax-m3",
    ]


def test_every_reviewer_timing_out_still_reports_no_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Demotion must not invent a verdict when nothing answered."""

    def fake_run(command, **_kwargs):
        raise pr_review.subprocess.TimeoutExpired(cmd=command, timeout=240)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(pr_review.subprocess, "run", fake_run)
    monkeypatch.setattr(
        pr_review, "review_models_for_current_event",
        lambda: ("openrouter/deepseek/deepseek-v4-flash", "openrouter/minimax/minimax-m3"),
    )

    unresponsive: set[str] = set()
    assert pr_review._review_chunk("a", unresponsive=unresponsive) is None
    # Both are now known bad, and the next chunk must still refuse rather than
    # silently pass because no candidate remains.
    assert pr_review._review_chunk("b", unresponsive=unresponsive) is None


def test_review_request_uses_restricted_opencode_agent_and_paid_flash_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = APPROVE_REVIEW_JSON + "\n"
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
    outputs = iter(["", APPROVE_REVIEW_JSON + "\n"])
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


def test_blank_fallback_response_gets_a_second_attempt_before_the_review_is_voided(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: PR #917, 2026-09-17.

    The primary reviewer timed out and the fallback exited 0 with empty stdout.
    The run voided the whole review, and three consecutive reruns reproduced it
    with no new information. A blank response is a transport failure, so the
    fallback -- which never timed out -- gets one more attempt before the review
    is thrown away. A model that timed out is still never retried (PR #880).
    """
    answers = iter(["", APPROVE_REVIEW_JSON + "\n"])
    attempted: list[str] = []

    class Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def fake_run(command, **_kwargs):
        review_model = command[command.index("--model") + 1]
        attempted.append(review_model)
        if "deepseek" in review_model:
            raise pr_review.subprocess.TimeoutExpired(cmd=command, timeout=240)
        return Result(next(answers))

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(pr_review.subprocess, "run", fake_run)
    monkeypatch.setattr(
        pr_review, "review_models_for_current_event",
        lambda: ("openrouter/deepseek/deepseek-v4-flash", "openrouter/minimax/minimax-m3"),
    )

    assert pr_review.review_diff("diff") == pr_review.NO_FINDINGS
    assert attempted == [
        "openrouter/deepseek/deepseek-v4-flash",
        "openrouter/minimax/minimax-m3",
        "openrouter/minimax/minimax-m3",
    ]
    # The retry is one extra paid submission, and its progression is on the log
    # where an operator can see how close the chunk came to exhaustion.
    logged = capsys.readouterr().err
    assert "pass 2/2" in logged
    assert "attempt 3/3 for this chunk" in logged
    assert "Chunk 1/1 used 3 paid reviewer submission(s)." in logged


def test_reviewer_that_kept_failing_after_its_retry_still_produces_no_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blank response from every reviewer costs one bounded retry, then no verdict.

    The retry must never invent evidence, and it must never spend more than the
    ladder plus one extra paid submission: this is the exact shape of the PR #917
    reruns, where nothing answered and the head stayed unapproved.
    """
    attempted: list[str] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **_kwargs):
        attempted.append(command[command.index("--model") + 1])
        return Result()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(pr_review.subprocess, "run", fake_run)
    monkeypatch.setattr(
        pr_review, "review_models_for_current_event",
        lambda: ("openrouter/deepseek/deepseek-v4-flash", "openrouter/minimax/minimax-m3"),
    )

    assert pr_review.review_diff("diff") is None
    assert pr_review._REVIEW_SUBMISSIONS == [
        "openrouter/deepseek/deepseek-v4-flash",
        "openrouter/minimax/minimax-m3",
        "openrouter/minimax/minimax-m3",
    ]


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


def test_no_verdict_run_names_the_failed_attempts_in_the_published_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: PR #917, 2026-09-17 -- the failure must name its cause.

    The timeout and the blank fallback existed only as log lines, so the durable
    failure comment on the PR said that no verdict existed and nothing about why;
    three reruns surfaced the same nothing. The comment now names each attempt
    that failed, using our own wording rather than the model's response text, and
    stays non-evidence.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **_kwargs):
        if "deepseek" in command[command.index("--model") + 1]:
            raise pr_review.subprocess.TimeoutExpired(cmd=command, timeout=240)
        return Result()

    monkeypatch.setattr(pr_review.subprocess, "run", fake_run)
    monkeypatch.setattr(
        pr_review, "review_models_for_current_event",
        lambda: ("openrouter/deepseek/deepseek-v4-flash", "openrouter/minimax/minimax-m3"),
    )

    assert pr_review.review_diff("diff") is None

    body = pr_review.render_review_body(pr_review.REVIEW_FAILED, "a" * 40)

    assert "openrouter/deepseek/deepseek-v4-flash" in body
    assert "timed out after" in body
    assert "openrouter/minimax/minimax-m3" in body
    assert "without producing a response" in body
    assert "Reviewed commit" not in body
    assert pr_review.NO_FINDINGS not in body
    assert not pr_review._has_findings(body)


def test_main_reports_why_a_no_verdict_run_failed(
    tmp_path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end, the reported rerun scenario: hard exit, fail-closed comment, named cause.

    PR #917 (2026-09-17) ran the real thing three times. Nothing answered, the
    head was left unapproved -- correctly -- and neither the run nor the PR named
    the timeout or the blank fallback, so a rerun could not even tell what to
    retry. The review job is deliberately non-blocking, so this asserts the run's
    own channel as well as the failure comment.
    """
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **_kwargs):
        if "deepseek" in command[command.index("--model") + 1]:
            raise pr_review.subprocess.TimeoutExpired(cmd=command, timeout=240)
        return Result()

    seen: list[str] = []
    monkeypatch.setattr(pr_review, "get_pr_diff", lambda: ("diff", 12, "owner", "repo", "a" * 40))
    monkeypatch.setattr(pr_review, "get_exact_head_override", lambda _sha: None)
    monkeypatch.setattr(pr_review, "_head_still_current", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        pr_review, "upsert_review", lambda review, *_args: seen.append(review) or True
    )
    monkeypatch.setattr(pr_review.subprocess, "run", fake_run)
    monkeypatch.setattr(
        pr_review, "review_models_for_current_event",
        lambda: ("openrouter/deepseek/deepseek-v4-flash", "openrouter/minimax/minimax-m3"),
    )

    with pytest.raises(SystemExit) as exc:
        pr_review.main()

    assert exc.value.code == 1
    assert seen == [pr_review.REVIEW_PENDING, pr_review.REVIEW_FAILED]
    written = summary.read_text(encoding="utf-8")
    assert "openrouter/deepseek/deepseek-v4-flash" in written
    assert "timed out after" in written
    assert "openrouter/minimax/minimax-m3" in written
    assert "without producing a response" in written
    assert "the failure comment and the run summary" in capsys.readouterr().err


def test_main_does_not_claim_a_channel_that_never_received_the_failure(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: PR #930 review -- no success claim for a channel that skipped.

    With no run summary configured and the failure comment declined (the head
    moved, or more conservative evidence is already recorded for it), the causes
    reached neither channel. The final line must send the operator to the workflow
    log instead of claiming both publications succeeded.
    """
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    published = iter([True, False])  # pending marker published, failure declined
    monkeypatch.setattr(pr_review, "get_pr_diff", lambda: ("diff", 12, "owner", "repo", "a" * 40))
    monkeypatch.setattr(pr_review, "get_exact_head_override", lambda _sha: None)
    monkeypatch.setattr(pr_review, "_head_still_current", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pr_review, "upsert_review", lambda *_args, **_kwargs: next(published))
    monkeypatch.setattr(pr_review, "review_diff", lambda _diff: None)

    with pytest.raises(SystemExit) as exc:
        pr_review.main()

    assert exc.value.code == 1
    logged = capsys.readouterr().err
    assert "the workflow log above" in logged
    assert "run summary" not in logged
    assert "failure comment" not in logged


def test_reviewer_failure_detail_names_the_provider_error_not_ansi_noise(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: PR #930, 2026-09-17 -- the log must show the real error.

    opencode left a bare ANSI reset on stderr and the provider's message on
    stdout, so the old ``stderr or stdout`` detail printed ": ^[[0m" as the whole
    failure. The real cause -- an OpenRouter credit ceiling on the fallback model
    -- appeared nowhere, which is why the gate kept failing silently.
    """

    class Result:
        returncode = 1
        stdout = (
            "> pr-reviewer · minimax/minimax-m3\n"
            "Error: This request requires more credits, or fewer max_tokens. "
            "You requested up to 32000 tokens, but can only afford 916\n"
        )
        stderr = "\x1b[0m"

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(pr_review.subprocess, "run", lambda _command, **_kwargs: Result())
    monkeypatch.setattr(
        pr_review, "review_models_for_current_event",
        lambda: ("openrouter/minimax/minimax-m3",),
    )

    assert pr_review.review_diff("diff") is None

    logged = capsys.readouterr().err
    assert "requires more credits" in logged
    assert "\x1b[0m" not in logged


def test_nonzero_exit_with_a_stderr_diagnostic_is_reported_as_a_process_failure(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: PR #930 review -- a nonzero exit must keep its stderr cause.

    The blank-stdout branch used to classify every empty stdout as "without
    producing a response" and drop the captured stderr, so an `opencode` failure
    that reports only on stderr (a missing key, a refused model) was reported as
    a silent no-answer.
    """

    class Result:
        returncode = 2
        stdout = ""
        stderr = "Error: provider authentication failed for openrouter"

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(pr_review.subprocess, "run", lambda _command, **_kwargs: Result())
    monkeypatch.setattr(
        pr_review, "review_models_for_current_event",
        lambda: ("openrouter/minimax/minimax-m3",),
    )

    assert pr_review.review_diff("diff") is None

    logged = capsys.readouterr().err
    assert "process failed (exit 2)" in logged
    assert "provider authentication failed" in logged
    # The durable reason stays workflow-authored: no raw process text is promoted
    # into the workflow-owned failure comment.
    body = pr_review.render_review_body(pr_review.REVIEW_FAILED, "a" * 40)
    assert "provider authentication failed" not in body
    assert "`openrouter/minimax/minimax-m3` failed with exit 2" in body


def test_route_without_a_credential_is_skipped_and_the_review_still_verdicts(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rung whose route has no credential must not void the review.

    With only the subscription credential present, the retained OpenRouter rungs
    cannot run at all; skipping them is what lets the subscription produce the
    verdict instead of aborting on `OPENROUTER_API_KEY is not set` (which is how
    the old route check behaved, and which would have made the route change
    useless anywhere the paid key is absent).
    """
    attempted: list[str] = []

    class Result:
        returncode = 0
        stdout = APPROVE_REVIEW_JSON + "\n"
        stderr = ""

    def fake_run(command, **_kwargs):
        attempted.append(command[command.index("--model") + 1])
        return Result()

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
    monkeypatch.setattr(pr_review.subprocess, "run", fake_run)

    assert pr_review.review_diff("diff") == pr_review.NO_FINDINGS
    assert attempted == ["opencode-go/muse-spark-1.3-contributor"]
    assert "OPENROUTER_API_KEY" in capsys.readouterr().err


def test_no_usable_route_still_fails_closed_and_names_the_missing_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing authenticated means no verdict, and the reason says what is missing."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    monkeypatch.setattr(
        pr_review.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("no reviewer may run without a credential"),
    )

    assert pr_review.review_diff("diff") is None

    body = pr_review.render_review_body(pr_review.REVIEW_FAILED, "a" * 40)
    assert "OPENCODE_API_KEY" in body
    assert "OPENROUTER_API_KEY" in body
    assert "Reviewed commit" not in body


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


def test_off_contract_output_is_not_published_as_a_finding() -> None:
    """Regression: narration must fail loud, not become a finding.

    Observed live on PR #869 and again on #873: the reviewer returned process
    narration, the workflow published it as a review body, and the gate then reported
    a blocking finding for a defect that was never produced. Naming a file does not
    make narration a finding either.
    """
    assert pr_review._normalize_opencode_review(
        "Looking at this diff, I need to verify the claims made in the comments and "
        "check for concrete defects. Let me examine the actual code."
    ) is None
    assert pr_review._normalize_opencode_review(
        "I'll review the PR diff chunk carefully. Let me first understand what's being "
        "changed by examining the repository structure and the relevant files."
    ) is None
    assert pr_review._normalize_opencode_review(
        "I need to inspect scripts/pr_review_gate.py before deciding."
    ) is None


def test_legacy_text_review_shapes_fail_closed() -> None:
    """Sentinels and rubric-looking prose are no longer model evidence."""
    assert pr_review._normalize_opencode_review(pr_review.NO_FINDINGS) is None
    assert pr_review._normalize_opencode_review(
        "Failure Mode: the retry loop double-charges on timeout."
    ) is None
    assert pr_review._normalize_opencode_review(
        f"{pr_review.NO_FINDINGS}\n\nFailure Mode: the loop double-charges."
    ) is None


def test_embedded_json_object_survives_transport_formatting() -> None:
    """Regression: a fenced or narrated record is still the required verdict.

    Observed on every review attempt for PR #877 and #883: the model returned an
    otherwise schema-valid record wrapped in a fence or a sentence of narration,
    the parser rejected the whole response, and the workflow published a
    no-verdict marker that no gate can satisfy. The schema is still enforced
    exactly; only transport formatting is tolerated.
    """
    record = APPROVE_REVIEW_JSON
    assert pr_review._normalize_opencode_review(record) == pr_review.NO_FINDINGS
    assert (
        pr_review._normalize_opencode_review(f"```json\n{record}\n```")
        == pr_review.NO_FINDINGS
    )
    assert (
        pr_review._normalize_opencode_review(f"Here is my review.\n\n{record}\n")
        == pr_review.NO_FINDINGS
    )
    # Braces in prose are not candidate records; only decodable objects count.
    assert (
        pr_review._normalize_opencode_review(
            f"I checked the {{name}} binding.\n```json\n{record}\n```"
        )
        == pr_review.NO_FINDINGS
    )

    # Refused: the record is not the reviewer's final word, so a worked example
    # cannot be promoted to a verdict.
    assert (
        pr_review._normalize_opencode_review(
            f"```json\n{record}\n```\nThat is my only finding set."
        )
        is None
    )
    # Refused: the response says it did not finish.
    assert (
        pr_review._normalize_opencode_review(
            f"I could not complete the review.\n\n{record}"
        )
        is None
    )
    # Refused: no object, several objects, or a valid object off-contract.
    assert pr_review._normalize_opencode_review("No actionable findings.") is None
    assert pr_review._normalize_opencode_review(f"{record}\n{record}") is None
    assert (
        pr_review._normalize_opencode_review('{"schema_version":1,"verdict":"approve"}')
        is None
    )
    assert (
        pr_review._normalize_opencode_review(
            '{"schema_version":2,"verdict":"approve","findings":[]}'
        )
        is None
    )


def test_gate_and_workflow_share_one_finding_definition() -> None:
    """The producer and the reader must not drift apart."""
    from scripts import pr_review_gate

    assert pr_review_gate._agent_body_has_rubric_fields(
        "File / Hunk: gateway/x.py — retry\n"
        "Trigger: timeout after charge\n"
        "Failure Mode: the loop double-charges.\n"
        "Corrective Action: make the retry idempotent."
    )
    assert not pr_review_gate._agent_body_has_rubric_fields(
        "I need to inspect scripts/pr_review_gate.py before deciding."
    )


def test_live_pr876_truncation_narration_is_not_a_verdict() -> None:
    """Regression: the malformed live #876 reviewer transcript is not evidence."""
    output = (
        "Let me look at the diff context. The user message seems to be a PR diff but "
        "the actual diff content is missing. I need to find the actual PR diff. "
        "Let me check the git state. Conclusion: No reportable findings."
    )

    assert pr_review._normalize_opencode_review(output) is None


def test_partial_rubric_labels_are_not_a_review_verdict() -> None:
    """A label-shaped fragment must not satisfy the four-field finding contract."""
    assert pr_review._normalize_opencode_review(
        "Failure Mode: something is wrong."
    ) is None
    assert pr_review._normalize_opencode_review(
        "Failure Mode: something is wrong.\n"
        "Corrective Action: change it."
    ) is None


def test_exact_json_review_contract_normalizes_approve_and_findings() -> None:
    """Only one exact machine-readable record becomes review evidence."""
    approve = '{"schema_version":1,"verdict":"approve","findings":[]}'
    assert pr_review._normalize_opencode_review(approve) == pr_review.NO_FINDINGS

    finding = (
        '{"schema_version":1,"verdict":"findings","findings":['
        '{"file":"scripts/pr_review.py","hunk":"_normalize_opencode_review",'
        '"trigger":"reviewer returns narration with one rubric label",'
        '"failure_mode":"narration is published as a blocking finding",'
        '"corrective_action":"reject non-schema reviewer output"}]}'
    )
    normalized = pr_review._normalize_opencode_review(finding)

    assert normalized is not None
    assert "File / Hunk: scripts/pr_review.py — _normalize_opencode_review" in normalized
    assert "Trigger: reviewer returns narration with one rubric label" in normalized
    assert "Failure Mode: narration is published as a blocking finding" in normalized
    assert "Corrective Action: reject non-schema reviewer output" in normalized


def test_review_json_must_be_schema_exact_and_each_finding_complete() -> None:
    """The contract is the record's shape, not the formatting around it.

    Wrapping an otherwise schema-valid record in a fence or a sentence is how the
    reviewer actually answers, and rejecting that outright turned every attempt
    into a no-verdict. The record itself must still match exactly, and narration
    that reads as a finding must still not be cleared by an embedded approval.
    """
    valid = '{"schema_version":1,"verdict":"approve","findings":[]}'
    assert (
        pr_review._normalize_opencode_review("thinking first\n" + valid)
        == pr_review.NO_FINDINGS
    )
    # Prose *after* the record means the record was not the final verdict.
    assert pr_review._normalize_opencode_review(valid + "\nextra prose") is None
    # A narrated defect is not cleared by an embedded approval.
    assert (
        pr_review._normalize_opencode_review(
            "Failure Mode: the retry loop double-charges on timeout.\n" + valid
        )
        is None
    )
    # Ambiguous: more than one candidate record.
    assert pr_review._normalize_opencode_review(valid + "\n" + valid) is None
    # The record itself must still be schema-exact.
    assert pr_review._normalize_opencode_review(
        '{"schema_version":1,"verdict":"findings","findings":['
        '{"file":"scripts/pr_review.py","hunk":"parser",'
        '"trigger":"bad output","failure_mode":"false evidence"}]}'
    ) is None


def test_validated_json_finding_renders_for_the_existing_gate() -> None:
    rendered = (
        "File / Hunk: scripts/pr_review.py — parser\n"
        "Trigger: malformed model output\n"
        "Failure Mode: false review evidence\n"
        "Corrective Action: reject the output"
    )
    assert pr_review.is_reportable_finding(rendered)
    assert not pr_review.is_reportable_finding(
        "I need to inspect scripts/pr_review.py before deciding."
    )
