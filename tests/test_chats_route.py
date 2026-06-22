"""Tests for the /chats route after migration to chats_store (Phase C C3)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import chats_store
from gateway.routes import chats as chats_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Build a minimal FastAPI app around the chats router and isolate its DB."""
    db_file = tmp_path / "kitty" / "kitty.db"
    legacy_json = tmp_path / "kitty" / "chats.json"
    monkeypatch.setattr(chats_store, "CHATS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(chats_store, "LEGACY_CHATS_FILE", legacy_json, raising=False)
    app = FastAPI()
    app.include_router(chats_route.router)
    return TestClient(app)


def test_post_then_get_round_trip(client):
    payload = {"id": "abc", "title": "Hello"}

    post = client.post("/chats", json=payload)
    get = client.get("/chats")

    assert post.status_code == 200
    assert post.json() == {"ok": True}
    assert get.json() == {"chats": [payload]}


def test_post_rejects_missing_id(client):
    r = client.post("/chats", json={"title": "no id"})

    assert r.status_code == 400
    assert "id" in r.json()["detail"].lower()


def test_post_upsert_replaces(client):
    client.post("/chats", json={"id": "abc", "title": "v1"})
    post = client.post("/chats", json={"id": "abc", "title": "v2"})
    listed = client.get("/chats").json()["chats"]

    assert post.status_code == 200
    assert len(listed) == 1
    assert listed[0]["title"] == "v2"


def test_delete_removes(client):
    client.post("/chats", json={"id": "abc", "title": "x"})

    delete = client.delete("/chats/abc")
    listed = client.get("/chats")

    assert delete.status_code == 200
    assert listed.json() == {"chats": []}


def test_delete_missing_is_ok(client):
    r = client.delete("/chats/never-existed")

    assert r.status_code == 200
    assert r.json() == {"ok": True}
