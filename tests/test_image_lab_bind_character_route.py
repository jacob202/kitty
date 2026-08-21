from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import image_sessions
from gateway.routes import extended, image_studio_jobs


def test_patch_session_route_binds_character(monkeypatch):
    seen: dict[str, object] = {}

    def fake_update(session_id, **kwargs):
        seen["session_id"] = session_id
        seen["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(image_sessions, "update_session", fake_update)
    monkeypatch.setattr(
        extended,
        "_session_payload",
        lambda session: {"session_id": "imgses_1", "character_id": "char_1"},
    )

    app = FastAPI()
    app.include_router(extended.router)
    app.include_router(image_studio_jobs.router)
    response = TestClient(app).patch(
        "/studio/sessions/imgses_1",
        json={"character_id": "char_1"},
    )

    assert response.status_code == 200
    assert response.json()["character_id"] == "char_1"
    assert seen["session_id"] == "imgses_1"
    assert seen["kwargs"]["character_id"] == "char_1"
    assert seen["kwargs"]["clear_character"] is False


def test_patch_session_route_clears_character(monkeypatch):
    seen: dict[str, object] = {}

    def fake_update(session_id, **kwargs):
        seen["session_id"] = session_id
        seen["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(image_sessions, "update_session", fake_update)
    monkeypatch.setattr(
        extended,
        "_session_payload",
        lambda session: {"session_id": "imgses_1", "character_id": None},
    )

    app = FastAPI()
    app.include_router(extended.router)
    app.include_router(image_studio_jobs.router)
    response = TestClient(app).patch(
        "/studio/sessions/imgses_1",
        json={"clear_character": True},
    )

    assert response.status_code == 200
    assert response.json()["character_id"] is None
    assert seen["kwargs"]["clear_character"] is True
    assert seen["kwargs"]["character_id"] is None
