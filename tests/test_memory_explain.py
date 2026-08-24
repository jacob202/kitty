"""Tests for QoL Packet 04 — explainable memory projection + controls.

The explain surface is an id-addressable, read-only projection over the governed
explicit-memory store (#552); controls route through the existing lifecycle.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from gateway import explicit_memory
from gateway.errors import KittyError
from gateway.routes import memories as memories_route


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(explicit_memory, "DB_FILE", tmp_path / "kitty.db")
    return explicit_memory


@pytest.fixture
def client(store):
    app = FastAPI()

    @app.exception_handler(KittyError)
    def _handle_kitty_error(request, exc: KittyError):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(memories_route.router)
    return TestClient(app)


def _remember_pair(store, old_text="I prefer dark mode", new_text="Use light mode now"):
    old = store.remember(
        old_text,
        namespace="preferences",
        memory_key="ui.theme",
        source_kind="user_explicit",
        source_ref="conversation:c1",
    )
    new = store.remember(
        new_text,
        namespace="preferences",
        memory_key="ui.theme",
        supersedes_id=old["id"],
        source_kind="user_correction",
        source_ref="conversation:c2",
    )
    return old, new


class TestExplainProjection:
    def test_explicit_preference_is_explainable(self, store):
        from gateway.memory_explain import explain

        row = store.remember(
            "I prefer dark mode",
            namespace="preferences",
            memory_key="ui.theme",
            source_kind="user_explicit",
            source_ref="conversation:c1",
        )

        exp = explain(row["id"])
        assert exp["id"] == row["id"]
        assert exp["fact"] == "I prefer dark mode"
        assert exp["namespace"] == "preferences"
        assert exp["memory_key"] == "ui.theme"
        assert exp["source"]["kind"] == "user_explicit"
        assert exp["source"]["ref"] == "conversation:c1"
        assert exp["source"]["authority"] == "user"
        assert exp["source_type"] == "conversation"
        assert exp["truth"]["confidence"] == 1.0
        assert exp["truth"]["stable"] is True
        assert exp["current_state"] == "active"
        assert exp["sensitivity"] == "normal"
        assert exp["pinned"] is False
        assert exp["supersedes"] is None

    def test_automated_source_authority(self, store):
        from gateway.memory_explain import explain

        row = store.remember(
            "Insight loop observed Jacob works best in the morning",
            memory_key="rhythm.morning",
            source_kind="insight_loop",
            source_ref="insight:42",
        )

        exp = explain(row["id"])
        assert exp["source"]["authority"] == "automated"
        assert exp["source_type"] == "automated"

    def test_correction_supersession_chain_exposed(self, store):
        from gateway.memory_explain import explain

        old, new = _remember_pair(store)

        exp = explain(new["id"])
        assert exp["supersedes"]["id"] == old["id"]
        assert exp["supersedes"]["fact"] == "I prefer dark mode"
        assert exp["supersedes"]["source"]["kind"] == "user_explicit"

        superseded = store.get(old["id"], include_inactive=True)
        assert superseded["status"] == "superseded"
        assert superseded["superseded_by"] == new["id"]

        active = store.search("theme light mode", limit=5)
        assert [row["id"] for row in active] == [new["id"]]

    def test_forget_moves_state_but_keeps_explanation(self, store):
        from gateway.memory_explain import explain

        row = store.remember("My favorite editor is Zed", memory_key="editor")
        assert store.forget(row["id"]) is True

        exp = explain(row["id"])
        assert exp["current_state"] == "forgotten"
        assert exp["remembered_at"] is not None
        assert store.search("favorite editor Zed", limit=5) == []

    def test_stable_fact_does_not_decay_with_age(self, store):
        from gateway.memory_explain import explain

        old_time = datetime.now(timezone.utc) - timedelta(days=3650)
        row = store.remember(
            "My birthday is January 1, 1987",
            memory_key="profile.birthday",
            now=old_time,
        )

        exp = explain(row["id"])
        assert exp["truth"]["confidence"] == 1.0
        assert exp["truth"]["stable"] is True
        assert exp["remembered_at"].startswith(str(old_time.year))

    def test_sensitive_memory_isolation_preserved(self, store):
        from gateway.memory_explain import explain

        row = store.remember(
            "Private support preference unrelated to coding",
            memory_key="support.private",
            sensitivity="sensitive",
        )

        exp = explain(row["id"])
        assert exp["sensitivity"] == "sensitive"
        assert store.search("what is the Kitty build status", limit=5) == []

    def test_missing_memory_raises_not_found(self, store):
        from gateway.memory_explain import ExplicitMemoryNotFound, explain

        with pytest.raises(ExplicitMemoryNotFound):
            explain("exp_missing")


class TestPinToggle:
    def test_set_pinned_flips_and_persists(self, store):
        row = store.remember("Use light mode now", memory_key="ui.theme")

        assert store.set_pinned(row["id"], pinned=True) is True
        assert store.get(row["id"])["pinned"] is True

        assert store.set_pinned(row["id"], pinned=False) is True
        assert store.get(row["id"])["pinned"] is False

    def test_set_pinned_on_missing_returns_false(self, store):
        assert store.set_pinned("exp_missing", pinned=True) is False

    def test_pinned_surfaces_in_list_and_search_boost(self, store):
        row = store.remember("I prefer dark mode", namespace="preferences", memory_key="ui.theme")
        store.set_pinned(row["id"], pinned=True)

        listed = store.list_memories(namespace="preferences")
        assert listed[0]["pinned"] is True

        store.remember("Use light mode now", memory_key="ui.theme")
        pinned = store.get(row["id"], include_inactive=True)
        assert pinned["status"] == "superseded"


class TestRoutes:
    def test_explain_route(self, store, client):
        row = store.remember(
            "I prefer dark mode",
            namespace="preferences",
            memory_key="ui.theme",
            source_kind="user_explicit",
            source_ref="conversation:c1",
        )

        r = client.get(f"/memories/{row['id']}/explain")
        assert r.status_code == 200
        body = r.json()["memory"]
        assert body["fact"] == "I prefer dark mode"
        assert body["source"]["authority"] == "user"
        assert body["current_state"] == "active"

    def test_explain_route_missing_404(self, store, client):
        r = client.get("/memories/exp_missing/explain")
        assert r.status_code == 404
        assert "was not found" in r.json()["message"]

    def test_correct_route_creates_supersession(self, store, client):
        old = store.remember(
            "I prefer dark mode",
            namespace="preferences",
            memory_key="ui.theme",
            sensitivity="sensitive",
            source_ref="conversation:c1",
        )

        r = client.post(
            f"/memories/{old['id']}/correct",
            json={"text": "Use light mode now"},
        )
        assert r.status_code == 200
        new = r.json()["memory"]
        assert new["fact"] == "Use light mode now"
        assert new["source"]["kind"] == "user_correction"
        assert new["supersedes"]["id"] == old["id"]
        assert new["namespace"] == "preferences"
        assert new["sensitivity"] == "sensitive"
        assert new["memory_key"] == "ui.theme"

        superseded = store.get(old["id"], include_inactive=True)
        assert superseded["status"] == "superseded"

    def test_correct_route_on_forgotten_target_404(self, store, client):
        old = store.remember("I prefer dark mode", memory_key="ui.theme")
        store.forget(old["id"])

        r = client.post(
            f"/memories/{old['id']}/correct",
            json={"text": "Use light mode now"},
        )
        assert r.status_code == 404

    def test_pin_route(self, store, client):
        row = store.remember("I prefer dark mode", memory_key="ui.theme")

        r = client.post(f"/memories/{row['id']}/pin", json={"pinned": True})
        assert r.status_code == 200
        assert r.json()["pinned"] is True
        assert store.get(row["id"])["pinned"] is True

    def test_pin_route_missing_404(self, store, client):
        r = client.post("/memories/exp_missing/pin", json={"pinned": True})
        assert r.status_code == 404
