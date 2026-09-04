from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes import session_context


def test_session_context_returns_last_topic_and_next_actions(tmp_path, monkeypatch):
    monkeypatch.delenv("KITTY_DATA_ROOT", raising=False)
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
    monkeypatch.setattr(session_context, "_live_branch", lambda: "feature/context")

    app = FastAPI()
    app.include_router(session_context.router)
    client = TestClient(app)

    response = client.get("/session/context")

    assert response.status_code == 200
    assert response.json() == {
        "current_branch": "feature/context",
        "last_session_topic": "UI wiring fix pass",
        "open_threads": ["Finish the queue."],
        "next_actions": ["Finish the queue.", "Run verification."],
    }


def test_isolated_data_root_does_not_expose_repo_agent_handoff(tmp_path, monkeypatch):
    handoff_file = tmp_path / "HANDOFF.md"
    state_file = tmp_path / "STATE.md"
    handoff_file.write_text("# Handoff\n\n## Resume here\n- Secret developer next step.\n", encoding="utf-8")
    state_file.write_text("# Private developer session\n\n## Next\n- More developer state.\n", encoding="utf-8")
    monkeypatch.setattr(session_context, "HANDOFF_FILE", handoff_file)
    monkeypatch.setattr(session_context, "STATE_FILE", state_file)
    monkeypatch.setattr(session_context, "_live_branch", lambda: "feature/private-agent-work")
    monkeypatch.setenv("KITTY_DATA_ROOT", str(tmp_path / "acceptance-data"))

    app = FastAPI()
    app.include_router(session_context.router)
    response = TestClient(app).get("/session/context")

    assert response.status_code == 200
    assert response.json() == {
        "current_branch": None,
        "last_session_topic": None,
        "open_threads": [],
        "next_actions": [],
    }
