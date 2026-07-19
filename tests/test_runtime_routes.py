"""Tests for the /runtime routes — capability manifest and project context."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import project_context
from gateway.routes import runtime as runtime_route

_MOCK_MANIFEST = {
    "schema_version": 1,
    "manifest_id": "runtime-test",
    "generated_at": "2026-07-17T00:00:00Z",
    "application": {"name": "Kitty", "version": None},
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    # Stub the manifest composer — it's async and heavy.
    # compose_manifest is imported at module level in runtime.py so we
    # patch the copy that is already bound in gateway.routes.runtime.
    async def _mock_compose(project_id=None):
        return {**_MOCK_MANIFEST}

    monkeypatch.setattr(
        "gateway.routes.runtime.compose_manifest",
        _mock_compose,
    )

    # Stub project context to avoid DB dependency.
    monkeypatch.setattr(
        project_context,
        "get_active_project",
        lambda: {"project_id": 1, "project": {"id": 1, "name": "kitty"}, "source": "test"},
    )
    monkeypatch.setattr(
        project_context,
        "set_active_project",
        lambda pid: {"project_id": pid, "project": {"id": pid, "name": "test"}, "source": "test"},
    )

    app = FastAPI()
    app.include_router(runtime_route.router)
    return TestClient(app)


class TestRuntimeManifest:
    def test_happy_path(self, client):
        r = client.get("/runtime/manifest")
        assert r.status_code == 200
        body = r.json()
        assert body["manifest_id"] == "runtime-test"
        assert body["schema_version"] == 1

    def test_with_project_id(self, client):
        r = client.get("/runtime/manifest", params={"project_id": 5})
        assert r.status_code == 200
        assert r.json()["manifest_id"] == "runtime-test"


class TestGetActiveProject:
    def test_happy_path(self, client):
        r = client.get("/context/project")
        assert r.status_code == 200
        body = r.json()
        assert body["project_id"] == 1
        assert "project" in body
        assert "source" in body

    def test_context_error_returns_409(self, client, monkeypatch):
        def _raise():
            raise project_context.ProjectContextError("stale active-project pointer")

        monkeypatch.setattr(project_context, "get_active_project", _raise)
        r = client.get("/context/project")
        assert r.status_code == 409
        assert "stale active-project pointer" in r.json()["detail"]


class TestPutActiveProject:
    def test_happy_path(self, client):
        r = client.put("/context/project", json={"project_id": 3})
        assert r.status_code == 200
        body = r.json()
        assert body["project_id"] == 3
        assert "project" in body

    def test_rejects_invalid_project_id_type(self, client):
        r = client.put("/context/project", json={"project_id": "abc"})
        assert r.status_code == 422  # Pydantic validation error

    def test_context_error_returns_400(self, client, monkeypatch):
        """StrictInt only enforces int-ness; domain validation (positive id,
        project exists) lives in set_active_project, and the route's contract
        is to map its ProjectContextError to HTTP 400."""

        def _raise(pid):
            raise project_context.ProjectContextError(
                f"project_id must be a positive integer, got {pid!r}"
            )

        monkeypatch.setattr(project_context, "set_active_project", _raise)
        r = client.put("/context/project", json={"project_id": -1})
        assert r.status_code == 400
        assert "positive integer" in r.json()["detail"]
