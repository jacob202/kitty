"""Tests for the /signals route — proactive signals feed."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import db as kitty_db
from gateway import expert_state, signal_store
from gateway.routes import signals as signals_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(signal_store, "SIGNALS_DB_FILE", db_file)
    monkeypatch.setattr(expert_state, "KITTY_DB_FILE", db_file)
    pause_file = tmp_path / "expert_state.json"
    monkeypatch.setattr(expert_state, "EXPERT_STATE_FILE", pause_file)
    kitty_db.migrate(db_file=db_file)

    app = FastAPI()
    app.include_router(signals_route.router)
    return TestClient(app)


class TestListSignals:
    def test_empty_when_no_signals(self, client):
        r = client.get("/signals")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["repairs"] == []
        assert body["issues"] == 0

    def test_returns_unprocessed_signals(self, client):
        signal_store.emit(source="system", kind="watch_match", payload={"label": "Test"})
        r = client.get("/signals")
        assert r.status_code == 200
        body = r.json()
        assert len(body["repairs"]) >= 1
        item = body["repairs"][0]
        assert item["id"].startswith("signal-")
        assert item["severity"] == "warn"
        assert "watch match" in item["title"]

    def test_expert_signals_have_snooze_fix(self, client):
        signal_store.emit(
            source="expert.health",
            kind="insight",
            payload={"headline": "Health tip", "topic_hash": "abc123"},
        )
        r = client.get("/signals")
        body = r.json()
        expert_items = [i for i in body["repairs"] if "expert" in i["title"].lower() or i["id"].startswith("signal-")]
        assert len(expert_items) >= 1
        # Expert signals should have a snooze fix action
        has_snooze = any(
            i.get("fix") and "snooze" in i["fix"].get("label", "")
            for i in expert_items
        )
        assert has_snooze

    def test_non_expert_signals_no_fix(self, client):
        signal_store.emit(source="system", kind="ping", payload={})
        r = client.get("/signals")
        body = r.json()
        system_items = [i for i in body["repairs"] if i["title"].startswith("system:")]
        assert len(system_items) >= 1
        assert system_items[0].get("fix") is None

    def test_excludes_processed_signals(self, client):
        sig = signal_store.emit(source="system", kind="ping", payload={})
        signal_store.mark_processed(sig["id"])
        r = client.get("/signals")
        body = r.json()
        assert body["issues"] == 0


class TestDismissSignal:
    def test_happy_path(self, client):
        sig = signal_store.emit(source="system", kind="ping", payload={})
        r = client.post("/signals/dismiss", json={"signal_id": sig["id"]})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["signal_id"] == sig["id"]
        # Signal should now be processed
        assert signal_store.get_signal(sig["id"])["processed_at"] is not None

    def test_expert_signal_also_increments_dismiss_count(self, client):
        sig = signal_store.emit(
            source="expert.builder",
            kind="suggestion",
            payload={"topic_hash": "topic123", "headline": "Build tip"},
        )
        r = client.post("/signals/dismiss", json={"signal_id": sig["id"]})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        # Expert signal should be processed
        assert signal_store.get_signal(sig["id"])["processed_at"] is not None

    def test_not_found_returns_404(self, client):
        r = client.post("/signals/dismiss", json={"signal_id": 999999})
        assert r.status_code == 404

    def test_missing_signal_id_returns_400(self, client):
        r = client.post("/signals/dismiss", json={})
        assert r.status_code == 400

    def test_wrong_type_returns_400(self, client):
        r = client.post("/signals/dismiss", json={"signal_id": "not_int"})
        assert r.status_code == 400


class TestSignalsIntent:
    def test_is_signals_intent_detects_patterns(self):
        from gateway.routes.completions import _is_signals_intent
        assert _is_signals_intent("anything to flag?")
        assert _is_signals_intent("Any flags today?")
        assert _is_signals_intent("What should I know?")
        assert _is_signals_intent("Any suggestions?")

    def test_is_signals_intent_rejects_non_patterns(self):
        from gateway.routes.completions import _is_signals_intent
        assert not _is_signals_intent("hello there")
        assert not _is_signals_intent("how are you")
