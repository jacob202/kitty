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

    def test_missing_backing_file_remains_visible_with_truthful_availability(self, client):
        artifact = client.get("/artifacts").json()["artifacts"][0]
        from pathlib import Path
        Path(artifact["storage_uri"]).unlink()

        response = client.get("/artifacts")

        assert response.status_code == 200
        rows = response.json()["artifacts"]
        assert len(rows) == 1
        assert rows[0]["id"] == artifact["id"]
        assert rows[0]["state"] == "ready"
        assert rows[0]["storage_available"] is False

    def test_archived_artifact_is_hidden_by_default_but_preserved_in_history(self, client):
        artifact = client.get("/artifacts").json()["artifacts"][0]

        archived = client.patch(f"/artifacts/{artifact['id']}/archive", json={"archived": True})

        assert archived.status_code == 200
        assert archived.json()["state"] == "archived"
        assert client.get("/artifacts").json()["artifacts"] == []
        history = client.get("/artifacts", params={"include_archived": "true"}).json()["artifacts"]
        assert len(history) == 1
        assert history[0]["id"] == artifact["id"]
        assert history[0]["state"] == "archived"

    def test_archive_restore_preserves_previous_failed_state(self, client):
        artifact = client.get("/artifacts").json()["artifacts"][0]
        with artifact_store.kitty_db.connect(artifact_store.ARTIFACTS_DB_FILE) as conn:
            conn.execute("UPDATE artifacts SET state = 'failed', error = 'index failed' WHERE id = ?", (artifact["id"],))
            conn.commit()

        assert client.patch(f"/artifacts/{artifact['id']}/archive", json={"archived": True}).status_code == 200
        restored = client.patch(f"/artifacts/{artifact['id']}/archive", json={"archived": False})

        assert restored.status_code == 200
        assert restored.json()["state"] == "failed"
        assert restored.json()["error"] == "index failed"
        assert restored.json()["metadata"].get("archived_from_state") is None

    def test_archive_requires_boolean_and_existing_artifact(self, client):
        artifact = client.get("/artifacts").json()["artifacts"][0]

        assert client.patch(f"/artifacts/{artifact['id']}/archive", json={"archived": "yes"}).status_code == 400
        assert client.patch("/artifacts/missing/archive", json={"archived": True}).status_code == 404


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


class TestArtifactContent:
    def test_serves_registered_ready_text_by_artifact_id(self, client):
        artifact_id = client.get("/artifacts").json()["artifacts"][0]["id"]

        response = client.get(f"/artifacts/{artifact_id}/content")

        assert response.status_code == 200
        assert response.text == "hello world"
        assert response.headers["content-type"].startswith("text/plain")

    def test_missing_backing_file_fails_closed(self, client):
        artifact = client.get("/artifacts").json()["artifacts"][0]
        from pathlib import Path
        Path(artifact["storage_uri"]).unlink()

        response = client.get(f"/artifacts/{artifact['id']}/content")

        assert response.status_code == 404
        assert "missing from disk" in response.json()["detail"].lower()

    def test_non_ready_artifact_is_not_served(self, client, monkeypatch):
        artifact = client.get("/artifacts").json()["artifacts"][0]
        original = artifact_store.get_artifact

        def get_artifact(artifact_id):
            value = original(artifact_id)
            if value is not None:
                value["state"] = "processing"
            return value

        monkeypatch.setattr(artifact_store, "get_artifact", get_artifact)

        response = client.get(f"/artifacts/{artifact['id']}/content")

        assert response.status_code == 409
        assert "not ready" in response.json()["detail"].lower()


    def test_content_route_round_trips_artifact_ids_with_slashes(self, client, tmp_path):
        source = tmp_path / "slash-id.txt"
        source.write_text("slash safe")
        artifact_store.register_file(
            source, kind="text", media_type="text/plain", project_id=None,
            created_by="test", artifact_id="folder/item",
        )

        response = client.get("/artifacts/folder%2Fitem/content")

        assert response.status_code == 200
        assert response.text == "slash safe"

    def test_changed_backing_file_fails_closed(self, client):
        artifact = client.get("/artifacts").json()["artifacts"][0]
        from pathlib import Path
        path = Path(artifact["storage_uri"])
        path.write_text("HELLO WORLD")

        response = client.get(f"/artifacts/{artifact['id']}/content")

        assert response.status_code == 409
        assert "changed on disk" in response.json()["detail"].lower()

    def test_oversized_text_preview_is_rejected_before_materializing(self, client, monkeypatch):
        artifact = client.get("/artifacts").json()["artifacts"][0]
        monkeypatch.setattr(artifacts_route, "MAX_TEXT_PREVIEW_BYTES", 4)

        response = client.get(f"/artifacts/{artifact['id']}/content")

        assert response.status_code == 413
        assert "too large to preview" in response.json()["detail"].lower()

    def test_active_html_content_is_not_previewable(self, client, monkeypatch):
        artifact = client.get("/artifacts").json()["artifacts"][0]
        original = artifact_store.get_artifact

        def get_artifact(artifact_id):
            value = original(artifact_id)
            if value is not None:
                value["media_type"] = "text/html"
            return value

        monkeypatch.setattr(artifact_store, "get_artifact", get_artifact)

        response = client.get(f"/artifacts/{artifact['id']}/content")

        assert response.status_code == 415
        assert "preview" in response.json()["detail"].lower()
