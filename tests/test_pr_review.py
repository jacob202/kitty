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
    monkeypatch.setattr(pr_review, "get_exact_head_override", lambda _sha: None)
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
    monkeypatch.setattr(pr_review, "get_exact_head_override", lambda _sha: None)
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
    monkeypatch.setattr(pr_review, "get_exact_head_override", lambda _sha: None)
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
    monkeypatch.setattr(pr_review, "upsert_review", lambda review, *_args: seen.append(review))

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
    assert [timeout for _command, timeout in calls] == [90, 90]



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
