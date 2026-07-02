"""Tests for the /state routes (P1) — now, snapshot, changes."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import signal_store, state_composer
from gateway.routes import state as state_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Minimal app around the state router with isolated DB and stub sources."""
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(state_composer, "STATE_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(signal_store, "SIGNALS_DB_FILE", db_file, raising=False)
    counts = {"open": 1}
    monkeypatch.setattr(
        state_composer,
        "SOURCES",
        {"todos": lambda: {"open_count": counts["open"]}},
    )
    app = FastAPI()
    app.include_router(state_route.router)
    test_client = TestClient(app)
    test_client.counts = counts
    return test_client


def test_state_now_returns_sections(client):
    r = client.get("/state/now")

    assert r.status_code == 200
    body = r.json()
    assert body["sections"]["todos"] == {"ok": True, "open_count": 1}


def test_changes_before_any_snapshot_is_explicit(client):
    r = client.get("/state/changes")

    assert r.status_code == 200
    assert r.json()["baseline_ts"] is None
    assert "no snapshot yet" in r.json()["note"]


def test_snapshot_then_changes_round_trip(client):
    snap = client.post("/state/snapshot")
    assert snap.status_code == 200
    assert isinstance(snap.json()["id"], int)

    client.counts["open"] = 4
    r = client.get("/state/changes")

    assert r.status_code == 200
    body = r.json()
    assert body["baseline_ts"] == pytest.approx(snap.json()["ts"])
    assert body["changes"] == [
        {"section": "todos", "field": "open_count", "before": 1, "after": 4}
    ]
