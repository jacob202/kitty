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
    state_file.write_text(
        "# Session State\n\n## Branch\n- `feature/context`\n\n## Next\n- Run verification.\n\n## UI wiring fix pass\n- Verify the live UI.\n",
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
