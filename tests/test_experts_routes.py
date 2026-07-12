"""HTTP-layer contract tests for gateway/routes/experts.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from gateway.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# --- GET /experts/signals/unprocessed ---


def test_get_unprocessed_signals_filters_to_expert_source(client: TestClient) -> None:
    signals = [
        {"id": 1, "source": "expert.health", "kind": "insight", "payload": {}},
        {"id": 2, "source": "mail", "kind": "message.received", "payload": {}},
        {"id": 3, "source": "expert.automotive", "kind": "insight", "payload": {}},
    ]
    with patch("gateway.signal_store.list_unprocessed", return_value=signals) as mock_list:
        response = client.get("/experts/signals/unprocessed")

    assert response.status_code == 200
    body = response.json()
    assert [s["id"] for s in body["signals"]] == [1, 3]
    mock_list.assert_called_once_with(limit=100)


def test_get_unprocessed_signals_empty(client: TestClient) -> None:
    with patch("gateway.signal_store.list_unprocessed", return_value=[]):
        response = client.get("/experts/signals/unprocessed")

    assert response.status_code == 200
    assert response.json() == {"signals": []}


# --- POST /experts/{expert_id}/snooze ---


def test_snooze_expert_success(client: TestClient) -> None:
    with patch("gateway.expert_state.set_snooze", return_value=1234567890.0) as mock_snooze, \
            patch("gateway.sse.broadcaster.broadcast") as mock_broadcast:
        response = client.post("/experts/health/snooze", json={"duration_hours": 2.5})

    assert response.status_code == 200
    assert response.json() == {"expert_id": "health", "snoozed_until": 1234567890.0}
    mock_snooze.assert_called_once_with("health", 2.5 * 3600)
    mock_broadcast.assert_called_once_with("state_updated")


def test_snooze_expert_missing_duration_hours_returns_422(client: TestClient) -> None:
    response = client.post("/experts/health/snooze", json={})

    assert response.status_code == 422


def test_snooze_expert_invalid_duration_type_returns_422(client: TestClient) -> None:
    response = client.post("/experts/health/snooze", json={"duration_hours": "a while"})

    assert response.status_code == 422


# --- DELETE /experts/{expert_id}/snooze ---


def test_unsnooze_expert_success(client: TestClient) -> None:
    with patch("gateway.expert_state.clear_snooze") as mock_clear, \
            patch("gateway.sse.broadcaster.broadcast") as mock_broadcast:
        response = client.delete("/experts/health/snooze")

    assert response.status_code == 200
    assert response.json() == {"expert_id": "health", "snoozed": False}
    mock_clear.assert_called_once_with("health")
    mock_broadcast.assert_called_once_with("state_updated")


def test_unsnooze_expert_with_hyphenated_id(client: TestClient) -> None:
    with patch("gateway.expert_state.clear_snooze") as mock_clear, \
            patch("gateway.sse.broadcaster.broadcast"):
        response = client.delete("/experts/automotive-diagnostics/snooze")

    assert response.status_code == 200
    assert response.json()["expert_id"] == "automotive-diagnostics"
    mock_clear.assert_called_once_with("automotive-diagnostics")


# --- POST/DELETE /experts/pause-all ---


def test_pause_all_experts_success(client: TestClient) -> None:
    with patch("gateway.expert_state.set_global_pause") as mock_pause:
        response = client.post("/experts/pause-all")

    assert response.status_code == 200
    assert response.json() == {"pause_all": True}
    mock_pause.assert_called_once_with(True)


def test_resume_all_experts_success(client: TestClient) -> None:
    with patch("gateway.expert_state.set_global_pause") as mock_pause:
        response = client.delete("/experts/pause-all")

    assert response.status_code == 200
    assert response.json() == {"pause_all": False}
    mock_pause.assert_called_once_with(False)


def test_pause_all_path_rejects_get(client: TestClient) -> None:
    response = client.get("/experts/pause-all")

    assert response.status_code == 405


# --- POST /experts/signals/{signal_id}/dismiss ---


def test_dismiss_signal_success(client: TestClient) -> None:
    sig = {"source": "expert.health", "payload": {"topic_hash": "abc123"}}
    with patch("gateway.signal_store.get_signal", return_value=sig) as mock_get, \
            patch("gateway.expert_state.increment_dismissed_count", return_value=3) as mock_incr, \
            patch("gateway.signal_store.mark_processed") as mock_mark, \
            patch("gateway.sse.broadcaster.broadcast") as mock_broadcast:
        response = client.post("/experts/signals/7/dismiss")

    assert response.status_code == 200
    assert response.json() == {
        "expert_id": "health",
        "signal_id": 7,
        "topic_hash": "abc123",
        "dismissed_count": 3,
    }
    mock_get.assert_called_once_with(7)
    mock_incr.assert_called_once_with("health", "abc123")
    mock_mark.assert_called_once_with(7)
    mock_broadcast.assert_called_once_with("state_updated")


def test_dismiss_signal_not_found_returns_404(client: TestClient) -> None:
    with patch("gateway.signal_store.get_signal", return_value=None):
        response = client.post("/experts/signals/999/dismiss")

    assert response.status_code == 404


def test_dismiss_signal_non_expert_source_returns_400(client: TestClient) -> None:
    sig = {"source": "mail", "payload": {}}
    with patch("gateway.signal_store.get_signal", return_value=sig):
        response = client.post("/experts/signals/8/dismiss")

    assert response.status_code == 400


def test_dismiss_signal_missing_topic_hash_returns_400(client: TestClient) -> None:
    sig = {"source": "expert.health", "payload": {}}
    with patch("gateway.signal_store.get_signal", return_value=sig):
        response = client.post("/experts/signals/9/dismiss")

    assert response.status_code == 400


# --- DELETE /experts/signals/{signal_id} ---


def test_delete_signal_success(client: TestClient) -> None:
    with patch("gateway.signal_store.delete") as mock_delete:
        response = client.delete("/experts/signals/5")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "id": 5}
    mock_delete.assert_called_once_with(5)


def test_delete_signal_invalid_id_returns_422(client: TestClient) -> None:
    response = client.delete("/experts/signals/not-an-int")

    assert response.status_code == 422
