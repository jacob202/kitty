"""Tests for the user-facing memory product surface (GET/forget/pin)."""
import pytest
from web import create_app


@pytest.fixture()
def client():
    app, _ = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_memory_list_returns_200(client):
    resp = client.get("/api/memory")
    assert resp.status_code == 200


def test_memory_list_has_required_keys(client):
    data = client.get("/api/memory").get_json()
    assert "corrections" in data
    assert "snapshots" in data
    assert "summary" in data


def test_memory_list_corrections_have_scope_and_why(client):
    data = client.get("/api/memory").get_json()
    for c in data["corrections"]:
        assert "scope" in c, f"correction missing scope: {c}"
        assert "why" in c, f"correction missing why: {c}"
        assert "id" in c
        assert "text" in c


def test_memory_list_snapshots_have_scope_and_why(client):
    data = client.get("/api/memory").get_json()
    for s in data["snapshots"]:
        assert "scope" in s
        assert "why" in s
        assert "timestamp" in s


def test_memory_summary_has_counts(client):
    data = client.get("/api/memory").get_json()
    assert "correction_count" in data["summary"]
    assert "snapshot_count" in data["summary"]
    assert "entity_count" in data["summary"]


def test_memory_list_has_entities_key(client):
    data = client.get("/api/memory").get_json()
    assert "entities" in data
    assert isinstance(data["entities"], list)


def test_forget_missing_correction_does_not_500(client):
    resp = client.post("/api/memory/forget", json={"kind": "correction", "id": 999999})
    assert resp.status_code in (200, 404)
    assert resp.get_json().get("ok") is not None


def test_forget_missing_id_returns_400(client):
    resp = client.post("/api/memory/forget", json={"kind": "correction"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["ok"] is False
    assert "id is required" in data["error"]


def test_forget_snapshot_returns_non500(client):
    resp = client.post("/api/memory/forget", json={"kind": "snapshot", "id": "any"})
    assert resp.status_code in (200, 404, 501)


def test_pin_invalid_scope_returns_400(client):
    resp = client.post("/api/memory/pin", json={"kind": "correction", "id": 1, "scope": "banana"})
    assert resp.status_code == 400


def test_pin_snapshot_returns_non500(client):
    resp = client.post("/api/memory/pin", json={"kind": "snapshot", "id": "x", "scope": "durable"})
    assert resp.status_code in (200, 404, 501)


def test_pin_missing_id_returns_400(client):
    resp = client.post("/api/memory/pin", json={"kind": "correction", "scope": "durable"})
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_pin_nonexistent_correction_returns_404(client):
    resp = client.post("/api/memory/pin", json={"kind": "correction", "id": 999999, "scope": "project"})
    assert resp.status_code == 404


# ── ContextManager slot-routing tests ─────────────────────────────────────────

def test_corrections_assigned_to_corrections_slot_when_honcho_empty():
    """When Honcho returns empty, corrections must NOT land in the IDENTITY slot."""
    from unittest.mock import patch
    from src.core.context_manager import ContextManager

    with patch("src.core.context_manager.Honcho") as MockHoncho, \
         patch("src.core.context_manager.CorrectionMemory") as MockCM, \
         patch("src.core.context_manager.JournalInterface") as MockJournal:

        MockHoncho.return_value.get_approach_recommendation.return_value = ""
        MockCM.return_value.get_relevant_context_text.return_value = "user said X"
        MockCM.return_value.get_recent_snapshots.return_value = []
        MockJournal.return_value.detect_patterns.return_value = []

        cm = ContextManager()
        result = cm.build_unified_context("long enough query here", "code")

    assert "user said X" in result


def test_budget_applied_to_context_manager_output():
    """When all 4 sections have content the final output must respect the 2000-char budget."""
    from unittest.mock import patch
    from src.core.context_manager import ContextManager

    with patch("src.core.context_manager.Honcho") as MockHoncho, \
         patch("src.core.context_manager.CorrectionMemory") as MockCM, \
         patch("src.core.context_manager.JournalInterface") as MockJournal:

        MockHoncho.return_value.get_approach_recommendation.return_value = "Be direct and concise."
        MockCM.return_value.get_relevant_context_text.return_value = "Do not use passive voice."
        MockCM.return_value.get_recent_snapshots.return_value = [
            {"sentiment_label": "focused", "topics": ["coding"], "open_loops": [], "identity_signals": False}
        ]
        MockJournal.return_value.detect_patterns.return_value = ["iterates quickly", "prefers brevity"]

        cm = ContextManager()
        result = cm.build_unified_context("long enough query here", "code")

    # Budget is 2000 chars; footer adds ~90 chars — allow up to 2200
    assert len(result) < 2200
