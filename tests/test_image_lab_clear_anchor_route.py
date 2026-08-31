from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import image_sessions, undo_journal
from gateway.routes import extended, image_studio_jobs


def test_delete_anchor_route_calls_durable_clear(monkeypatch):
    cleared = object()
    calls: list[str] = []

    def fake_clear_with_undo(session_id: str):
        calls.append(session_id)
        return "undo_anchor_1"

    monkeypatch.setattr(undo_journal, "clear_anchor_with_undo", fake_clear_with_undo)
    monkeypatch.setattr(image_sessions, "require_session", lambda session_id: cleared)
    monkeypatch.setattr(
        extended,
        "session_payload",
        lambda session: {"session_id": "imgses_1", "anchor_job_id": None},
    )

    app = FastAPI()
    app.include_router(extended.router)
    app.include_router(image_studio_jobs.router)
    response = TestClient(app).delete("/studio/sessions/imgses_1/anchor")

    assert response.status_code == 200
    assert response.json()["anchor_job_id"] is None
    assert response.json()["undo_journal_id"] == "undo_anchor_1"
    assert calls == ["imgses_1"]
