from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote

from scripts import pr_policy, pr_review, pr_scope

SHA = "a" * 40


def _acceptance_body(*, accepted: bool = False) -> str:
    checks = "x" if accepted else " "
    return f"""## Product acceptance (required only when `gateway/kitty-chat/src/` or `public/` changes)
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
"""


def _pr(
    body: str = "",
    *,
    labels: tuple[str, ...] = (),
    additions: int = 20,
    deletions: int = 5,
    author: str = "jacob202",
    head_sha: str = SHA,
    changed_files: int = 2,
) -> dict:
    return {
        "body": body,
        "user": {"login": author},
        "labels": [{"name": label} for label in labels],
        "additions": additions,
        "deletions": deletions,
        "changed_files": changed_files,
        "head": {"sha": head_sha},
    }


def test_backend_pr_does_not_require_template_or_product_acceptance() -> None:
    violations = pr_policy.evaluate_policy(_pr(), ["gateway/memory.py"], independent_review_approved=True)
    assert violations == []


def test_ui_source_pr_requires_completed_product_acceptance() -> None:
    path = "gateway/kitty-chat/src/components/HomeState.tsx"
    missing = pr_policy.evaluate_policy(_pr(_acceptance_body()), [path], independent_review_approved=True)
    assert any("product acceptance" in item.lower() for item in missing)

    approved = pr_policy.evaluate_policy(
        _pr(_acceptance_body(accepted=True)), [path], independent_review_approved=True
    )
    assert approved == []


def test_frontend_test_only_pr_does_not_require_product_acceptance() -> None:
    violations = pr_policy.evaluate_policy(
        _pr(), ["gateway/kitty-chat/tests/HomeState.test.tsx"], independent_review_approved=True
    )
    assert violations == []


def test_risky_scope_requires_exact_head_human_approval_and_independent_review() -> None:
    path = ".github/workflows/tests.yml"
    missing = pr_policy.evaluate_policy(_pr(), [path], independent_review_approved=False)
    assert any("risk/approved" in item for item in missing)
    assert any("exact-head risk approval" in item.lower() for item in missing)
    assert any("independent review" in item.lower() for item in missing)

    body = f"Risk approval: APPROVE {SHA} — CI gate migration explicitly approved"
    still_missing_review = pr_policy.evaluate_policy(
        _pr(body, labels=(pr_policy.RISK_APPROVED_LABEL,)),
        [path],
        independent_review_approved=False,
    )
    assert still_missing_review == [
        "risky scope requires trusted independent review approval for the exact current head"
    ]

    approved = pr_policy.evaluate_policy(
        _pr(body, labels=(pr_policy.RISK_APPROVED_LABEL,)),
        [path],
        independent_review_approved=True,
    )
    assert approved == []


def test_policy_and_review_implementation_files_are_risky() -> None:
    for path in ["scripts/pr_policy.py", "scripts/pr_review.py", "scripts/pr_review_gate.py"]:
        violations = pr_policy.evaluate_policy(_pr(), [path], independent_review_approved=False)
        assert any("risk/approved" in item for item in violations), path


def test_sensitive_but_reversible_scope_clears_on_review_without_human_approval() -> None:
    for path in [
        "gateway/builder_supervisor.py",
        "gateway/builder_loop.py",
        "gateway/builder_attempt.py",
        "gateway/builder_initiative.py",
    ]:
        awaiting_review = pr_policy.evaluate_policy(
            _pr(), [path], independent_review_approved=False
        )
        assert awaiting_review == [
            "risky scope requires trusted independent review approval for the exact current head"
        ], path

        approved_by_review = pr_policy.evaluate_policy(
            _pr(), [path], independent_review_approved=True
        )
        assert approved_by_review == [], path


def test_irreversible_scope_still_requires_exact_head_human_approval() -> None:
    """Credentials, spend, deletion, dependencies, and the gate itself stay human-gated."""
    for path in [
        "config/compute_governor.json",
        "gateway/compute_governor.py",
        "gateway/security/secrets.py",
        "scripts/purge_users.py",
        "requirements.txt",
        "pyproject.toml",
        "uv.lock",
        "gateway/kitty-chat/package.json",
        "gateway/kitty-chat/package-lock.json",
        "gateway/action_grants.py",
        "gateway/action_queue.py",
        "gateway/routes/actions.py",
        "gateway/builder_publish.py",
        "gateway/builder_pr_janitor.py",
        "gateway/routes/chats.py",
        "gateway/routes/projects.py",
        "scripts/pr_policy.py",
        ".github/workflows/tests.yml",
    ]:
        violations = pr_policy.evaluate_policy(_pr(), [path], independent_review_approved=True)
        assert any("risk/approved" in item for item in violations), path
        assert any("exact-head risk approval" in item.lower() for item in violations), path


def test_large_change_is_advisory_not_blocking() -> None:
    pr = _pr(additions=1600, deletions=20, changed_files=30)
    assert pr_policy.evaluate_policy(pr, ["gateway/memory.py"], independent_review_approved=True) == []
    warnings = pr_policy.policy_warnings(pr)
    assert any("large" in item.lower() for item in warnings)


def test_dependabot_waives_product_prose_but_not_sensitive_scope_approval() -> None:
    pr = _pr(author="dependabot[bot]")
    violations = pr_policy.evaluate_policy(pr, ["requirements.txt"], independent_review_approved=False)
    assert any("risk/approved" in item for item in violations)
    assert any("independent review" in item.lower() for item in violations)


def test_policy_gate_is_consolidated_into_trusted_review_workflow() -> None:
    workflows = Path(__file__).parents[1] / ".github" / "workflows"
    text = (workflows / "pr-agent-review.yml").read_text(encoding="utf-8")
    assert "pull_request_target:" in text
    assert "policy-gate:" in text
    assert "name: policy-gate" in text
    assert "needs: [scope, agent-review]" in text
    assert "github.event.repository.default_branch" in text


def test_duplicate_pr_workflows_are_removed() -> None:
    workflows = Path(__file__).parents[1] / ".github" / "workflows"
    for filename in [
        "pr-description-check.yml",
        "pr-risk-guardrails.yml",
        "pr-test-hints.yml",
        "pr-release-evidence.yml",
        "pr-policy.yml",
        "pr-policy-trusted.yml",
    ]:
        assert not (workflows / filename).exists(), filename

def test_pr_template_documents_only_live_exact_head_approval_receipts() -> None:
    text = (Path(__file__).parents[1] / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    assert "Risk approval: APPROVE <full-head-SHA>" in text
    assert "Review override: APPROVE <full-head-SHA>" in text
    assert "Large-change approval: APPROVE <full-head-SHA>" not in text


def test_pr_number_from_event_prefers_pull_request_payload() -> None:
    event = {"pull_request": {"number": 7}, "merge_group": {"head_ref": "refs/heads/gh-readonly-queue/main/pr-99-aaaa"}}
    assert pr_policy._pr_number_from_event(event) == 7


def test_pr_number_from_event_parses_merge_group_head_ref() -> None:
    event = {
        "merge_group": {
            "head_ref": f"refs/heads/gh-readonly-queue/main/pr-99-{SHA}"
        }
    }
    assert pr_policy._pr_number_from_event(event) == 99


def test_pr_number_from_event_rejects_unparseable_merge_group() -> None:
    event = {"merge_group": {"head_ref": "refs/heads/something-without-a-pr-number"}}
    try:
        pr_policy._pr_number_from_event(event)
    except RuntimeError as exc:
        assert "merge_group head_ref" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_pr_number_from_event_requires_pr_or_merge_group() -> None:
    try:
        pr_policy._pr_number_from_event({"push": {"ref": "refs/heads/main"}})
    except RuntimeError as exc:
        assert "neither pull_request nor merge_group" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_main_resolves_merge_group_event_to_live_pr(tmp_path, monkeypatch) -> None:
    current_body = f"Risk approval: APPROVE {SHA} — current approval"
    current = _pr(
        current_body,
        labels=(pr_policy.RISK_APPROVED_LABEL,),
        head_sha=SHA,
    )
    current["number"] = 42
    event = {
        "action": "checks_requested",
        "merge_group": {
            "head_ref": f"refs/heads/gh-readonly-queue/main/pr-42-{SHA}"
        },
        "repository": {"owner": {"login": "jacob202"}, "name": "kitty"},
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    approved_comment = {
        "body": (
            f"{pr_review.COMMENT_MARKER}\n## Agent PR Review\n\n"
            f"No actionable findings in this diff.\n\n_Reviewed commit `{SHA}`._"
        ),
        "user": {"login": "github-actions[bot]", "type": "Bot"},
    }

    def fake_github_json(url: str, _token: str):
        if url.endswith("/pulls/42"):
            return current
        if "/pulls/42/files?" in url:
            return [{"filename": ".github/workflows/tests.yml"}]
        if url.endswith("/issues/42/comments?per_page=100"):
            return [approved_comment]
        raise AssertionError(url)

    monkeypatch.setattr(pr_policy, "_github_json", fake_github_json)
    pr_policy.main()


def test_main_reads_current_pr_and_review_evidence_from_api(tmp_path, monkeypatch) -> None:
    current_body = f"Risk approval: APPROVE {SHA} — current approval"
    current = _pr(
        current_body,
        labels=(pr_policy.RISK_APPROVED_LABEL,),
        head_sha=SHA,
    )
    current["number"] = 12
    event = {
        "action": "labeled",
        "pull_request": {"number": 12},
        "repository": {"owner": {"login": "jacob202"}, "name": "kitty"},
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    approved_comment = {
        "body": (
            f"{pr_review.COMMENT_MARKER}\n## Agent PR Review\n\n"
            f"No actionable findings in this diff.\n\n_Reviewed commit `{SHA}`._"
        ),
        "user": {"login": "github-actions[bot]", "type": "Bot"},
    }

    def fake_github_json(url: str, _token: str):
        if url.endswith("/pulls/12"):
            return current
        if "/pulls/12/files?" in url:
            return [{"filename": ".github/workflows/tests.yml"}]
        if url.endswith("/issues/12/comments?per_page=100"):
            return [approved_comment]
        raise AssertionError(url)

    monkeypatch.setattr(pr_policy, "_github_json", fake_github_json)
    pr_policy.main()



def test_product_acceptance_works_with_both_heading_formats() -> None:
    """The policy must accept both the PR template heading and the old variant."""
    path = "gateway/kitty-chat/src/components/HomeState.tsx"
    old_heading = "## Product acceptance (required for user-facing changes)"
    fields = [
        "- User goal: understand the result",
        "- Starting state and dependent services: service running",
        "- Running-app steps and visible result: exercise the changed flow",
        "- Failure/recovery path tested: provider unavailable",
        "- Viewports tested: phone and desktop",
        "- Evidence: recording-123",
        "- Independent task-completion reviewer: reviewer-2",
        "- Remaining limitations or dead ends: none",
    ]
    checks = "\n".join(f"- [x] {check}" for check in pr_policy.ACCEPTANCE_CHECKS)
    body = old_heading + "\n" + "\n".join(fields) + "\n" + checks
    violations = pr_policy.evaluate_policy(
        _pr(body), [path], independent_review_approved=True
    )
    assert violations == []

    new_heading = "## Product acceptance (required only when `gateway/kitty-chat/src/` or `public/` changes)"
    body2 = new_heading + "\n" + "\n".join(fields) + "\n" + checks
    violations2 = pr_policy.evaluate_policy(
        _pr(body2), [path], independent_review_approved=True
    )
    assert violations2 == []



# --- refactor signature exemption (2026-09-17) ---

BASE_SHA = "b" * 40

_CHATS_BASE = """from fastapi import APIRouter

router = APIRouter(tags=["chats"])


@router.get("/chats")
def list_chats():
    return []


@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: str):
    return {"deleted": chat_id}


@router.post("/sessions/close")
def close_session():
    return {"status": "ok"}
"""

_CHATS_HEAD = """from fastapi import APIRouter

router = APIRouter(tags=["chats"])


@router.get("/chats")
def list_chats():
    return []


@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: str):
    return {"deleted": chat_id}
"""

_SESSION_CLOSE = """from fastapi import APIRouter

router = APIRouter(tags=["chats"])


@router.post("/sessions/close")
def close_session():
    return {"status": "ok"}
"""

_TWO_DELETES_BASE = """from fastapi import APIRouter

router = APIRouter()


@router.delete("/a/{item_id}")
def delete_a(item_id: str):
    return {"deleted": item_id}


@router.delete("/b/{item_id}")
def delete_b(item_id: str):
    return {"deleted": item_id}
"""

_TWO_DELETES_SWAPPED = """from fastapi import APIRouter

router = APIRouter()


@router.delete("/b/{item_id}")
def delete_a(item_id: str):
    return {"deleted": item_id}


@router.delete("/a/{item_id}")
def delete_b(item_id: str):
    return {"deleted": item_id}
"""


def _proof_fetch(files: dict[tuple[str, str], str], pr_files: list[dict], *, error: Exception | None = None):
    def fetch(url: str, token: str) -> object:
        if error is not None:
            raise error
        if re.search(r"/pulls/\d+/files\?", url):
            return pr_files
        match = re.search(r"/contents/([^?]+)\?ref=([0-9a-fA-F]{40})", url)
        assert match, url
        path, ref = unquote(match.group(1)), match.group(2)
        if (path, ref) not in files:
            raise HTTPError(url, 404, "Not Found", {}, None)  # type: ignore[arg-type]
        text = files[(path, ref)]
        return {
            "type": "file",
            "size": len(text),
            "content": base64.b64encode(text.encode()).decode(),
        }

    return fetch


def _waiver(
    changed: list[str],
    *,
    base: dict[str, str],
    head: dict[str, str],
    renames: dict[str, str] | None = None,
    fetch=None,
) -> tuple[bool, str]:
    pr = _pr()
    pr["number"] = 898
    pr["base"] = {"sha": BASE_SHA}
    files = {(path, BASE_SHA): text for path, text in base.items()}
    files.update({(path, SHA): text for path, text in head.items()})
    renames = renames or {}
    pr_files = [
        {"filename": path, "previous_filename": renames.get(path)} for path in changed
    ]
    return pr_policy.refactor_signature_waived(
        pr, changed, fetch=fetch or _proof_fetch(files, pr_files), owner="o", repo="r", token="t"
    )


def test_route_bindings_bind_decorators_to_handlers_and_the_router_line() -> None:
    bindings = pr_policy.route_bindings(_CHATS_BASE)
    assert bindings is not None
    assert bindings["list_chats"][1] == ("router.get('/chats')",)
    assert bindings["delete_chat"][1] == ("router.delete('/chats/{chat_id}')",)
    assert bindings["list_chats"][0] == "router = APIRouter(tags=['chats'])"

    prefixed = _CHATS_BASE.replace('APIRouter(tags=["chats"])', 'APIRouter(prefix="/v2")')
    assert pr_policy.route_bindings(prefixed) != bindings


def test_route_bindings_ignore_decorator_text_in_strings_and_reject_odd_forms() -> None:
    faked = (
        'fake = """@router.delete("/chats/{chat_id}")"""\n\n'
        'from fastapi import APIRouter\n\nrouter = APIRouter()\n\n'
        '@router.get("/chats")\ndef list_chats():\n    return []\n'
    )
    bindings = pr_policy.route_bindings(faked)
    assert bindings is not None
    assert set(bindings) == {"list_chats"}

    odd = "from fastapi import APIRouter\nrouter = APIRouter()\n\n@router.on_event(\"startup\")\ndef boot():\n    return None\n"
    assert pr_policy.route_bindings(odd) is None
    assert pr_policy.route_bindings("def broken(:\n") is None


def test_destructive_handlers_bind_decorators_and_normalize_source() -> None:
    handlers = pr_policy.destructive_handlers(_TWO_DELETES_BASE)
    assert handlers is not None
    assert set(handlers) == {"delete_a", "delete_b"}
    swapped = pr_policy.destructive_handlers(_TWO_DELETES_SWAPPED)
    assert swapped is not None
    assert swapped["delete_a"] != handlers["delete_a"]

    named = pr_policy.destructive_handlers("def delete_test_user(user_id):\n    return None\n")
    assert named is not None and set(named) == {"delete_test_user"}
    assert pr_policy.destructive_handlers("def broken(:\n") is None


def test_waiver_true_for_a_route_preserving_move() -> None:
    waived, reason = _waiver(
        ["gateway/routes/chats.py", "gateway/routes/session_close.py"],
        base={"gateway/routes/chats.py": _CHATS_BASE},
        head={
            "gateway/routes/chats.py": _CHATS_HEAD,
            "gateway/routes/session_close.py": _SESSION_CLOSE,
        },
    )
    assert waived, reason


def test_waiver_true_when_unrelated_files_change_alongside_the_move() -> None:
    moved_a, _ = _waiver(
        ["gateway/routes/chats.py", "gateway/routes/session_close.py", "README.md"],
        base={"gateway/routes/chats.py": _CHATS_BASE, "README.md": "old\n"},
        head={
            "gateway/routes/chats.py": _CHATS_HEAD,
            "gateway/routes/session_close.py": _SESSION_CLOSE,
            "README.md": "new\n",
        },
    )
    assert moved_a

    helper_changed = "def delete_test_user(user_id):\n    return {'deleted': user_id}\n"
    helper_original = "def delete_test_user(user_id):\n    return None\n"
    moved_b, reason = _waiver(
        ["gateway/routes/chats.py", "gateway/routes/session_close.py", "tests/test_chats.py"],
        base={
            "gateway/routes/chats.py": _CHATS_BASE,
            "tests/test_chats.py": helper_original,
        },
        head={
            "gateway/routes/chats.py": _CHATS_HEAD,
            "gateway/routes/session_close.py": _SESSION_CLOSE,
            "tests/test_chats.py": helper_changed,
        },
    )
    assert moved_b, reason


def test_waiver_true_for_a_rename_because_base_resolves_the_previous_name() -> None:
    waived, reason = _waiver(
        ["gateway/routes/chats.py"],
        base={"gateway/routes/chats_v1.py": _CHATS_HEAD},
        head={"gateway/routes/chats.py": _CHATS_HEAD},
        renames={"gateway/routes/chats.py": "gateway/routes/chats_v1.py"},
    )
    assert waived, reason


def test_waiver_false_when_a_route_is_added_removed_or_rebound() -> None:
    added = _CHATS_HEAD + '\n@router.get("/chats/{chat_id}/lifecycle")\ndef lifecycle():\n    return {}\n'
    waived, reason = _waiver(
        ["gateway/routes/chats.py"],
        base={"gateway/routes/chats.py": _CHATS_HEAD},
        head={"gateway/routes/chats.py": added},
    )
    assert not waived and "route surface changed" in reason

    dropped = _CHATS_HEAD.replace('@router.delete("/chats/{chat_id}")\n', "")
    waived, reason = _waiver(
        ["gateway/routes/projects.py"],
        base={"gateway/routes/projects.py": _CHATS_HEAD},
        head={"gateway/routes/projects.py": dropped},
    )
    assert not waived and "route surface changed" in reason

    waived, reason = _waiver(
        ["gateway/routes/chats.py"],
        base={"gateway/routes/chats.py": _TWO_DELETES_BASE},
        head={"gateway/routes/chats.py": _TWO_DELETES_SWAPPED},
    )
    assert not waived and "route surface changed" in reason


def test_waiver_false_when_the_router_construction_changes() -> None:
    prefixed = _CHATS_HEAD.replace('APIRouter(tags=["chats"])', 'APIRouter(prefix="/v2", tags=["chats"])')
    waived, reason = _waiver(
        ["gateway/routes/chats.py"],
        base={"gateway/routes/chats.py": _CHATS_HEAD},
        head={"gateway/routes/chats.py": prefixed},
    )
    assert not waived and "route surface changed" in reason


def test_waiver_false_when_a_destructive_handler_changes() -> None:
    edited = _CHATS_HEAD.replace('return {"deleted": chat_id}', 'return {"deleted": True}')
    waived, reason = _waiver(
        ["gateway/routes/chats.py"],
        base={"gateway/routes/chats.py": _CHATS_HEAD},
        head={"gateway/routes/chats.py": edited},
    )
    assert not waived and "destructive handler changed" in reason


def test_waiver_false_outside_the_waivable_set() -> None:
    waived, reason = _waiver(
        ["gateway/routes/chats.py", "scripts/pr_policy.py"],
        base={"gateway/routes/chats.py": _CHATS_HEAD, "scripts/pr_policy.py": "# gate\n"},
        head={"gateway/routes/chats.py": _CHATS_HEAD, "scripts/pr_policy.py": "# gate\n"},
    )
    assert not waived and "outside the refactor-waivable set" in reason


def test_waiver_fails_closed_when_surface_proof_is_unavailable() -> None:
    waived, reason = _waiver(
        ["gateway/routes/chats.py"],
        base={"gateway/routes/chats.py": _CHATS_HEAD},
        head={"gateway/routes/chats.py": _CHATS_HEAD},
        fetch=_proof_fetch({}, [], error=TimeoutError("api down")),
    )
    assert not waived and "surface proof unavailable" in reason


def test_evaluate_policy_waives_human_signature_only_when_flag_is_set() -> None:
    with_flag = pr_policy.evaluate_policy(
        _pr(), ["gateway/routes/chats.py"], independent_review_approved=True, human_signature_waived=True
    )
    assert with_flag == []

    without_flag = pr_policy.evaluate_policy(
        _pr(), ["gateway/routes/chats.py"], independent_review_approved=True
    )
    assert any("risk/approved" in item for item in without_flag)
    assert any("exact-head risk approval" in item.lower() for item in without_flag)


def test_refactor_waivable_paths_are_a_subset_of_the_irreversible_tier() -> None:
    for path in ("gateway/routes/chats.py", "gateway/routes/projects.py"):
        assert path in pr_scope.irreversible_files([path])
        assert any(pattern.search(path) for pattern in pr_scope.REFACTOR_WAIVABLE_PATTERNS)
