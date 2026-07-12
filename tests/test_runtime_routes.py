"""HTTP-layer contract tests for gateway/routes/runtime.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway import project_context
from gateway.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# --- GET /runtime/manifest ---
# NOTE: compose_manifest is imported by name into gateway.routes.runtime
# (`from gateway.runtime_manifest import compose_manifest`), so it must be
# patched at the point of use, not at gateway.runtime_manifest.


def test_get_runtime_manifest_happy_path(client: TestClient) -> None:
    fake_manifest = {"revision": 1, "facts": [], "observed_at": "2026-07-12T00:00:00Z"}
    with patch(
        "gateway.routes.runtime.compose_manifest", new=AsyncMock(return_value=fake_manifest)
    ) as mock_compose:
        resp = client.get("/runtime/manifest")

    assert resp.status_code == 200
    assert resp.json() == fake_manifest
    mock_compose.assert_awaited_once_with(project_id=None)


def test_get_runtime_manifest_passes_project_id_through(client: TestClient) -> None:
    with patch(
        "gateway.routes.runtime.compose_manifest", new=AsyncMock(return_value={})
    ) as mock_compose:
        resp = client.get("/runtime/manifest", params={"project_id": 7})

    assert resp.status_code == 200
    mock_compose.assert_awaited_once_with(project_id=7)


def test_get_runtime_manifest_invalid_project_id_is_422(client: TestClient) -> None:
    resp = client.get("/runtime/manifest", params={"project_id": "not-an-int"})

    assert resp.status_code == 422


# --- GET /context/project ---


def test_get_active_project_happy_path(client: TestClient) -> None:
    fake = {"project_id": 3, "project": {"id": 3, "name": "kitty"}, "source": "persisted"}
    with patch("gateway.project_context.get_active_project", return_value=fake):
        resp = client.get("/context/project")

    assert resp.status_code == 200
    assert resp.json() == fake


def test_get_active_project_error_is_409(client: TestClient) -> None:
    with patch(
        "gateway.project_context.get_active_project",
        side_effect=project_context.ProjectContextError("cannot establish an active project: no projects exist"),
    ):
        resp = client.get("/context/project")

    assert resp.status_code == 409
    assert "no projects exist" in resp.json()["detail"]


# --- PUT /context/project ---


def test_put_active_project_happy_path(client: TestClient) -> None:
    fake = {"project_id": 5, "project": {"id": 5, "name": "benefits"}, "source": "persisted"}
    with patch("gateway.project_context.set_active_project", return_value=fake) as mock_set:
        resp = client.put("/context/project", json={"project_id": 5})

    assert resp.status_code == 200
    assert resp.json() == fake
    mock_set.assert_called_once_with(5)


def test_put_active_project_missing_project_is_400(client: TestClient) -> None:
    with patch(
        "gateway.project_context.set_active_project",
        side_effect=project_context.ProjectContextError(
            "cannot activate project 999: project does not exist"
        ),
    ):
        resp = client.put("/context/project", json={"project_id": 999})

    assert resp.status_code == 400
    assert "does not exist" in resp.json()["detail"]


def test_put_active_project_non_integer_is_422(client: TestClient) -> None:
    resp = client.put("/context/project", json={"project_id": "not-an-int"})

    assert resp.status_code == 422


def test_put_active_project_missing_field_is_422(client: TestClient) -> None:
    resp = client.put("/context/project", json={})

    assert resp.status_code == 422
