from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import image_sessions
from gateway.routes import extended, image_studio_jobs


def test_delete_anchor_route_calls_durable_clear(monkeypatch):
    cleared = object()
    calls: list[str] = []

    def fake_clear(session_id: str):
        calls.append(session_id)
        return cleared

    monkeypatch.setattr(image_sessions, "clear_anchor", fake_clear)
    monkeypatch.setattr(
        extended,
        "_session_payload",
        lambda session: {"session_id": "imgses_1", "anchor_job_id": None},
    )

    app = FastAPI()
    app.include_router(extended.router)
    app.include_router(image_studio_jobs.router)
    response = TestClient(app).delete("/studio/sessions/imgses_1/anchor")

    assert response.status_code == 200
    assert response.json()["anchor_job_id"] is None
    assert calls == ["imgses_1"]
