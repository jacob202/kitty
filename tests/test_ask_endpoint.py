from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

def test_ask_returns_reply():
    # Mock the HTTP response from LiteLLM
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "I am Kitty, your personal AI.",
                }
            }
        ],
        "usage": {"total_tokens": 10}
    }
    
    # Patch the AsyncClient.post directly
    with patch("gateway.context_builder.get_system_prompt", new=AsyncMock(return_value="FULL_SYSTEM")), \
         patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        
        from gateway.app import app
        client = TestClient(app)
        response = client.post("/ask", json={"message": "Who are you?"})
        
    assert response.status_code == 200
    assert response.json()["reply"] == "I am Kitty, your personal AI."


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
