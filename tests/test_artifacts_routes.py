"""HTTP-layer contract tests for gateway/routes/artifacts.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from gateway import artifact_store
from gateway.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


FAKE_ARTIFACT = {
    "id": "artifact_abc123",
    "project_id": 1,
    "kind": "screenshot",
    "media_type": "image/png",
    "display_name": "shot.png",
    "state": "ready",
    "storage_uri": "/data/artifacts/shot.png",
    "content_hash": "deadbeef",
    "size_bytes": 1024,
    "created_at": 1752000000.0,
    "created_by": "kitty",
    "source_ref": None,
    "conversation_id": "conv-1",
    "work_item_id": None,
    "run_id": None,
    "metadata": {},
    "error": None,
}


# --- GET /artifacts ---


def test_list_artifacts_happy_path(client: TestClient) -> None:
    with patch("gateway.artifact_store.list_artifacts", return_value=[FAKE_ARTIFACT]) as mock_list:
        resp = client.get("/artifacts")

    assert resp.status_code == 200
    assert resp.json() == {"artifacts": [FAKE_ARTIFACT]}
    mock_list.assert_called_once_with(project_id=None, conversation_id=None, kind=None, limit=100)


def test_list_artifacts_passes_query_params_through(client: TestClient) -> None:
    with patch("gateway.artifact_store.list_artifacts", return_value=[]) as mock_list:
        resp = client.get(
            "/artifacts",
            params={"project_id": 2, "conversation_id": "conv-9", "kind": "note", "limit": 5},
        )

    assert resp.status_code == 200
    mock_list.assert_called_once_with(project_id=2, conversation_id="conv-9", kind="note", limit=5)


def test_list_artifacts_limit_out_of_range_is_422(client: TestClient) -> None:
    resp = client.get("/artifacts", params={"limit": 501})

    assert resp.status_code == 422


def test_list_artifacts_store_error_is_400(client: TestClient) -> None:
    with patch(
        "gateway.artifact_store.list_artifacts",
        side_effect=artifact_store.ArtifactError("project_id must be positive, got -1"),
    ):
        resp = client.get("/artifacts", params={"project_id": -1})

    assert resp.status_code == 400
    assert "project_id must be positive" in resp.json()["detail"]


# --- GET /artifacts/{artifact_id} ---


def test_get_artifact_happy_path(client: TestClient) -> None:
    with patch("gateway.artifact_store.get_artifact", return_value=FAKE_ARTIFACT) as mock_get:
        resp = client.get("/artifacts/artifact_abc123")

    assert resp.status_code == 200
    assert resp.json() == FAKE_ARTIFACT
    mock_get.assert_called_once_with("artifact_abc123")


def test_get_artifact_not_found_is_404(client: TestClient) -> None:
    with patch("gateway.artifact_store.get_artifact", return_value=None):
        resp = client.get("/artifacts/does-not-exist")

    assert resp.status_code == 404
