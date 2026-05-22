from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


def test_ask_returns_reply_and_applies_voice_gate():
    """
    Intended function:
    1. Retrieve system prompt.
    2. Call LLM.
    3. Filter out corporate 'banned' phrases via Voice Gate.
    """
    # Mock a 'dirty' response that should be cleaned
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Certainly! I am Kitty, your personal AI. How can I assist you?",
                }
            }
        ],
        "usage": {"total_tokens": 10},
    }

    mock_payload = mock_resp.json.return_value
    mock_chat = AsyncMock(return_value=mock_payload)

    with patch(
        "gateway.context_builder.get_system_prompt",
        new=AsyncMock(return_value="FULL_SYSTEM"),
    ), patch("gateway.llm_client.chat_completions_non_stream", new=mock_chat), patch(
        "gateway.routes.ask.chat_completions_non_stream", new=mock_chat
    ):

        from gateway.app import app

        client = TestClient(app)
        response = client.post("/ask", json={"message": "Who are you?"})

    assert response.status_code == 200
    # 'Certainly!' and 'How can I assist you?' should be stripped by gateway/voice_gate.py
    reply = response.json()["reply"]
    assert "Certainly" not in reply
    assert "assist you" not in reply
    assert reply == "I am Kitty, your personal AI."


def test_ask_empty_message_returns_400():
    from gateway.app import app

    client = TestClient(app)
    response = client.post("/ask", json={"message": ""})
    assert response.status_code == 400


def test_ask_missing_message_returns_422():
    from gateway.app import app

    client = TestClient(app)
    response = client.post("/ask", json={})
    assert response.status_code == 422
