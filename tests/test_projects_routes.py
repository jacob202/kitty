"""Tests for the /projects routes (P6/P4, docs/packets/021 + 016)."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import next_step, project_store
from gateway.memory_graph import GraphResult
from gateway.routes import projects as projects_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(project_store, "PROJECTS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(next_step, "NEXT_STEP_DB_FILE", db_file, raising=False)
    monkeypatch.setattr("gateway.project_resume._run_memory_search", lambda q: GraphResult())
    monkeypatch.setattr("gateway.signal_store.list_recent", lambda limit=200: [])
    monkeypatch.setattr(
        next_step,
        "_default_llm",
        lambda prompt, privacy_tier, content_class: json.dumps(
            {"step": "stub step", "why": "stub why", "recent_win": "", "delegable": False}
        ),
    )
    monkeypatch.setattr(projects_route, "push_to_jacob", lambda *a, **k: True)
    app = FastAPI()
    app.include_router(projects_route.router)
    yield TestClient(app)


def test_get_projects_includes_the_seeded_kitty_project(client):
    r = client.get("/projects")

    assert r.status_code == 200
    projects = r.json()["projects"]
    assert any(p["name"] == "kitty" for p in projects)


def test_post_project_creates_and_returns_it(client):
    r = client.post("/projects", json={"name": "benefits paperwork", "kind": "admin"})

    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "benefits paperwork"
    assert body["kind"] == "admin"


def test_get_projects_filters_by_status(client):
    created = client.post("/projects", json={"name": "archived one", "kind": "admin"}).json()
    project_store.update_fields(created["id"], status="archived")

    r = client.get("/projects", params={"status": "archived"})

    assert r.status_code == 200
    names = [p["name"] for p in r.json()["projects"]]
    assert "archived one" in names


def test_refresh_returns_composed_sources_and_next_step(client):
    created = client.post("/projects", json={"name": "x", "kind": "admin"}).json()

    r = client.post(f"/projects/{created['id']}/refresh")

    assert r.status_code == 200
    body = r.json()
    assert "sources" in body
    assert body["sources"]["git"]["ok"] is True
    assert body["next_step"]["step"] == "stub step"
    assert body["next_step"]["changed"] is True


def test_refresh_missing_project_returns_404(client):
    r = client.post("/projects/999999/refresh")

    assert r.status_code == 404


def test_refresh_pushes_only_when_the_step_changes(client, monkeypatch):
    pushes = []
    monkeypatch.setattr(projects_route, "push_to_jacob", lambda *a, **k: pushes.append((a, k)) or True)
    created = client.post("/projects", json={"name": "x", "kind": "admin"}).json()

    client.post(f"/projects/{created['id']}/refresh")
    assert len(pushes) == 1

    client.post(f"/projects/{created['id']}/refresh")
    assert len(pushes) == 1  # same stubbed step both times — no repeat push


def test_get_next_returns_the_generated_step(client):
    created = client.post("/projects", json={"name": "x", "kind": "admin"}).json()
    client.post(f"/projects/{created['id']}/refresh")

    r = client.get(f"/projects/{created['id']}/next")

    assert r.status_code == 200
    assert r.json()["step"] == "stub step"


def test_get_next_404s_when_never_generated(client):
    created = client.post("/projects", json={"name": "x", "kind": "admin"}).json()

    r = client.get(f"/projects/{created['id']}/next")

    assert r.status_code == 404


def test_get_next_404s_for_missing_project(client):
    r = client.get("/projects/999999/next")

    assert r.status_code == 404


def test_resume_returns_rendered_packet(client):
    created = client.post("/projects", json={"name": "x", "kind": "admin"}).json()

    r = client.get(f"/projects/{created['id']}/resume")

    assert r.status_code == 200
    body = r.json()
    assert body["id"] == created["id"]
    assert "sources" not in body


def test_resume_missing_project_returns_404(client):
    r = client.get("/projects/999999/resume")

    assert r.status_code == 404
