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

    @pytest.mark.xfail(
        reason=(
            "route question: StrictInt accepts -1 as valid (it is a valid int), "
            "so the route passes it through to set_active_project which may reject "
            "it via ProjectContextError → HTTP 400. The real project_context does "
            "reject non-positive IDs."
        ),
    )
    def test_rejects_negative_project_id(self, client):
        """StrictInt accepts -1; the real set_active_project would reject it."""
        r = client.put("/context/project", json={"project_id": -1})
        assert r.status_code == 400

    @pytest.mark.xfail(
        reason=(
            "route question: set_active_project raises ProjectContextError for "
            "non-existent projects, but the route catches it as HTTP 400. The "
            "stub never raises, so this test only works when the monkeypatch "
            "is removed and a real DB is used."
        ),
    )
    def test_nonexistent_project_returns_400(self, client):
        # This would require a real project_context.set_active_project with a
        # real DB that has no project with id 999.
        r = client.put("/context/project", json={"project_id": 999})
        assert r.status_code == 400
