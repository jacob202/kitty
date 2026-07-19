"""Tests for the /experts routes — proactive expert feedback and state management."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import db as kitty_db
from gateway import expert_state, signal_store
from gateway.routes import experts as experts_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    # Point all DB consumers at the isolated path.
    monkeypatch.setattr(signal_store, "SIGNALS_DB_FILE", db_file)
    monkeypatch.setattr(expert_state, "KITTY_DB_FILE", db_file)
    # Isolate the global-pause file too.
    pause_file = tmp_path / "expert_state.json"
    monkeypatch.setattr(expert_state, "EXPERT_STATE_FILE", pause_file)
    # Apply migrations to the test DB so all tables exist.
    kitty_db.migrate(db_file=db_file)

    app = FastAPI()
    app.include_router(experts_route.router)
    return TestClient(app)


@pytest.fixture
def with_expert_signal(client):
    """Emit a signal with source=expert.* and a topic_hash in the payload."""
    signal_store.emit(
        source="expert.health",
        kind="insight",
        payload={"topic_hash": "abc123", "message": "test insight"},
    )
    return client


class TestUnprocessedSignals:
    def test_happy_path(self, with_expert_signal):
        r = with_expert_signal.get("/experts/signals/unprocessed")
        assert r.status_code == 200
        body = r.json()
        assert "signals" in body
        assert len(body["signals"]) >= 1
        for s in body["signals"]:
            assert s["source"].startswith("expert.")

    def test_filters_non_expert_signals(self, client):
        signal_store.emit(source="system", kind="ping")
        r = client.get("/experts/signals/unprocessed")
        assert r.status_code == 200
        # Only non-expert signals exist.
        assert r.json()["signals"] == []


class TestSnooze:
    def test_happy_path(self, client):
        r = client.post("/experts/test_expert/snooze", json={"duration_hours": 1})
        assert r.status_code == 200
        body = r.json()
        assert body["expert_id"] == "test_expert"
        assert isinstance(body["snoozed_until"], float)

    def test_unsnooze(self, client):
        client.post("/experts/test_expert/snooze", json={"duration_hours": 1})
        r = client.delete("/experts/test_expert/snooze")
        assert r.status_code == 200
        body = r.json()
        assert body["expert_id"] == "test_expert"
        assert body["snoozed"] is False


class TestGlobalPause:
    def test_pause_all(self, client):
        r = client.post("/experts/pause-all")
        assert r.status_code == 200
        assert r.json()["pause_all"] is True

    def test_resume_all(self, client):
        client.post("/experts/pause-all")
        r = client.delete("/experts/pause-all")
        assert r.status_code == 200
        assert r.json()["pause_all"] is False


class TestDismissSignal:
    def test_happy_path(self, with_expert_signal):
        sig = signal_store.list_unprocessed(limit=1)[0]
        r = with_expert_signal.post(f"/experts/signals/{sig['id']}/dismiss")
        assert r.status_code == 200
        body = r.json()
        assert body["signal_id"] == sig["id"]
        assert body["topic_hash"] == "abc123"
        assert isinstance(body["dismissed_count"], int)

    def test_not_found_returns_404(self, client):
        r = client.post("/experts/signals/999999/dismiss")
        assert r.status_code == 404
        assert "Signal not found" in r.json()["detail"]

    def test_non_expert_signal_returns_400(self, client):
        signal_store.emit(source="system", kind="ping", payload={"topic_hash": "x"})
        sig = signal_store.list_unprocessed(limit=1)[0]
        r = client.post(f"/experts/signals/{sig['id']}/dismiss")
        assert r.status_code == 400
        assert "Not an expert signal" in r.json()["detail"]

    def test_missing_topic_hash_returns_400(self, client):
        signal_store.emit(source="expert.test", kind="insight", payload={})
        sig = signal_store.list_unprocessed(limit=1)[0]
        r = client.post(f"/experts/signals/{sig['id']}/dismiss")
        assert r.status_code == 400
        assert "missing topic hash" in r.json()["detail"]


class TestDeleteSignal:
    def test_happy_path(self, with_expert_signal):
        sig = signal_store.list_unprocessed(limit=1)[0]
        r = with_expert_signal.delete(f"/experts/signals/{sig['id']}")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "deleted"
        assert body["id"] == sig["id"]

    def test_delete_missing_signal_succeeds(self, client):
        """The route doesn't check existence — it always returns success."""
        r = client.delete("/experts/signals/999999")
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"
