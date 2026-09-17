import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes import session_context


def test_session_context_returns_last_topic_and_next_actions(tmp_path, monkeypatch):
    handoff_file = tmp_path / "HANDOFF.md"
    state_file = tmp_path / "STATE.md"
    handoff_file.write_text(
        "# Handoff\n\n## Context\nPrevious context.\n\n## Resume here\n- Finish the queue.\n",
        encoding="utf-8",
    )
    # The topic comes from the H1 title, which is how real STATE.md files carry it
    # ("# Session State — Architecture Audit + Frontend Restructuring"). The old
    # fixture had a bare "# Session State" H1 and hid the topic in a trailing
    # section, which no real checkpoint file does.
    state_file.write_text(
        "# UI wiring fix pass\n\n## Branch\n- `feature/context`\n\n## Next\n- Run verification.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(session_context, "HANDOFF_FILE", handoff_file)
    monkeypatch.setattr(session_context, "STATE_FILE", state_file)
    monkeypatch.setattr(session_context, "_live_branch", lambda: ("feature/context", None))

    app = FastAPI()
    app.include_router(session_context.router)
    client = TestClient(app)

    response = client.get("/session/context")

    assert response.status_code == 200
    assert response.json() == {
        "current_branch": "feature/context",
        "current_branch_error": None,
        "last_session_topic": "UI wiring fix pass",
        "open_threads": ["Finish the queue."],
        "next_actions": ["Finish the queue.", "Run verification."],
    }


def test_live_branch_degrades_instead_of_raising_when_git_is_unavailable(monkeypatch):
    # Reproduces: _live_branch() used check=True with no exception handling, so
    # this read-only GET endpoint 500d whenever cwd wasn't a canonical git
    # checkout (a container, a detached worktree, git missing entirely).
    import subprocess

    def explode(*_args, **_kwargs):
        raise FileNotFoundError("git binary not found")

    monkeypatch.setattr(subprocess, "run", explode)
    branch, error = session_context._live_branch()
    assert branch is None
    assert error is not None and "FileNotFoundError" in error

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=2)

    monkeypatch.setattr(subprocess, "run", timeout)
    branch, error = session_context._live_branch()
    assert branch is None
    assert error is not None and "TimeoutExpired" in error

    def not_a_repo(*_args, **_kwargs):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(subprocess, "run", not_a_repo)
    branch, error = session_context._live_branch()
    assert branch is None
    assert error is not None and "CalledProcessError" in error


def test_live_branch_failure_is_distinguishable_from_an_absent_branch(monkeypatch, caplog):
    # Reproduces the review finding: a git failure came back as a bare None that
    # was identical to a repo whose HEAD names no branch, and nothing was logged,
    # so "git never answered" and "there is no branch" were the same observation.
    import subprocess

    def no_branch(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", no_branch)
    assert session_context._live_branch() == (None, None)

    def explode(*_args, **_kwargs):
        raise FileNotFoundError("git binary not found")

    monkeypatch.setattr(subprocess, "run", explode)
    with caplog.at_level(logging.WARNING, logger="kitty.routes.session_context"):
        branch, error = session_context._live_branch()

    assert branch is None
    assert error is not None, "a git failure must not look like a repo with no branch"
    assert "FileNotFoundError" in error
    assert "FileNotFoundError" in caplog.text
    assert "git rev-parse --abbrev-ref HEAD" in caplog.text


def test_session_context_endpoint_survives_a_missing_git_binary(tmp_path, monkeypatch):
    handoff_file = tmp_path / "HANDOFF.md"
    state_file = tmp_path / "STATE.md"
    handoff_file.write_text("# Handoff\n\n## Resume here\n- Finish the queue.\n", encoding="utf-8")
    state_file.write_text("# UI wiring fix pass\n\n## Next\n- Run verification.\n", encoding="utf-8")
    monkeypatch.setattr(session_context, "HANDOFF_FILE", handoff_file)
    monkeypatch.setattr(session_context, "STATE_FILE", state_file)

    import subprocess

    def explode(*_args, **_kwargs):
        raise FileNotFoundError("git binary not found")

    monkeypatch.setattr(subprocess, "run", explode)

    app = FastAPI()
    app.include_router(session_context.router)
    client = TestClient(app)

    response = client.get("/session/context")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_branch"] is None
    assert payload["current_branch_error"] is not None
    assert "FileNotFoundError" in payload["current_branch_error"]
