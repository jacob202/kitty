import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from gateway.app import app
from gateway.constants import MAX_BODY_BYTES


def _client():
    return TestClient(app, raise_server_exceptions=False)


def test_learn_rejects_oversized_topic():
    with patch.dict(os.environ, {"KITTY_ENV": "test", "GATEWAY_SECRET": ""}):
        client = _client()
        response = client.post("/learn", json={"topic": "x" * 1001})
    assert response.status_code == 422


def test_troubleshoot_rejects_empty_fields():
    with patch.dict(os.environ, {"KITTY_ENV": "test", "GATEWAY_SECRET": ""}):
        client = _client()
        response = client.post("/troubleshoot", json={"device": "", "symptom": ""})
    assert response.status_code == 422


def test_troubleshoot_accepts_valid_payload():
    with patch.dict(os.environ, {"KITTY_ENV": "test", "GATEWAY_SECRET": ""}), patch(
        "gateway.troubleshooter.initiate_troubleshooting", return_value="step 1"
    ):
        client = _client()
        response = client.post(
            "/troubleshoot", json={"device": "sansui", "symptom": "hiss"}
        )
    assert response.status_code == 200
    assert response.json()["response"] == "step 1"


def test_tasks_sync_accepts_valid_payload():
    with patch.dict(os.environ, {"KITTY_ENV": "test", "GATEWAY_SECRET": ""}), patch(
        "gateway.tasks.sync_next_action", return_value=True
    ):
        client = _client()
        response = client.post("/tasks/sync", json={"action": "ship docs cleanup"})
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_global_body_size_guard_blocks_large_requests():
    """Test that the body_size_guard middleware rejects oversized payloads.

    We bypass TestClient's content-length auto-computation by setting
    a huge header *after* the JSON body is serialized.
    """
    import json

    with patch.dict(os.environ, {"KITTY_ENV": "test", "GATEWAY_SECRET": ""}):
        client = _client()
        # Send a valid JSON body but lie about content-length via raw transport
        body = json.dumps({"topic": "ok"}).encode("utf-8")
        response = client.post(
            "/learn",
            content=body,
            headers={
                "content-type": "application/json",
                "content-length": str(MAX_BODY_BYTES + 1),
            },
        )
    assert response.status_code == 413
