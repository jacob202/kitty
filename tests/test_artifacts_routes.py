"""Tests for the /artifacts routes — read-only artifact registry (P6)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import artifact_store
from gateway.routes import artifacts as artifacts_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(artifact_store, "ARTIFACTS_DB_FILE", db_file)
    artifact_store.init_db()

    # Register a test artifact so the list endpoint has data.
    test_file = tmp_path / "test_artifact.txt"
    test_file.write_text("hello world")
    artifact_store.register_file(
        test_file,
        kind="text",
        media_type="text/plain",
        project_id=1,
        created_by="test",
    )

    app = FastAPI()
    app.include_router(artifacts_route.router)
    return TestClient(app)


class TestGetArtifacts:
    def test_happy_path_returns_list(self, client):
        r = client.get("/artifacts")
        assert r.status_code == 200
        body = r.json()
        assert "artifacts" in body
        assert isinstance(body["artifacts"], list)
        assert len(body["artifacts"]) >= 1

    def test_filters_by_kind(self, client):
        r = client.get("/artifacts", params={"kind": "text"})
        assert r.status_code == 200
        for a in r.json()["artifacts"]:
            assert a["kind"] == "text"

    def test_empty_kind_returns_empty(self, client):
        r = client.get("/artifacts", params={"kind": "nonexistent"})
        assert r.status_code == 200
        assert r.json()["artifacts"] == []

    def test_filters_by_project_id(self, client):
        r = client.get("/artifacts", params={"project_id": 1})
        assert r.status_code == 200
        assert len(r.json()["artifacts"]) >= 1

    def test_filters_by_project_id_no_match(self, client):
        r = client.get("/artifacts", params={"project_id": 999})
        assert r.status_code == 200
        assert r.json()["artifacts"] == []

    def test_limit_param(self, client):
        r = client.get("/artifacts", params={"limit": 1})
        assert r.status_code == 200
        assert len(r.json()["artifacts"]) <= 1


class TestGetArtifact:
    def test_happy_path(self, client):
        list_resp = client.get("/artifacts")
        artifact_id = list_resp.json()["artifacts"][0]["id"]

        r = client.get(f"/artifacts/{artifact_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == artifact_id
        assert body["kind"] == "text"
        assert isinstance(body, dict)

    def test_not_found_returns_404(self, client):
        r = client.get("/artifacts/nonexistent-id")
        assert r.status_code == 404
        assert "does not exist" in r.json()["detail"]
