from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from gateway.app import app


def test_ask_returns_reply():
    with patch(
        "gateway.context_builder.build_user_context",
        new=AsyncMock(return_value=("SOUL", "CTX")),
    ), patch(
        "gateway.app._non_stream_response",
        new=AsyncMock(
            return_value={"choices": [{"message": {"role": "assistant", "content": "I am Kitty, your personal AI."}}]}
        ),
    ):
        client = TestClient(app)
        response = client.post("/ask", json={"message": "Who are you?"})
    assert response.status_code == 200
    assert response.json()["reply"] == "I am Kitty, your personal AI."


def test_ask_empty_message_returns_400():
    client = TestClient(app)
    response = client.post("/ask", json={"message": ""})
    assert response.status_code == 400


def test_ask_missing_message_returns_422():
    client = TestClient(app)
    response = client.post("/ask", json={})
    assert response.status_code == 422
