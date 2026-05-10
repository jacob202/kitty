"""Eval: does gateway inject memory and knowledge context into system prompt?"""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from gateway.app import app
from gateway.domain_router import classify_domain


def test_memory_and_knowledge_injected_into_system_prompt():
    captured_payload = {}

    async def _fake_non_stream_response(payload):
        captured_payload["value"] = payload
        return {"id": "ok", "choices": [{"message": {"role": "assistant", "content": "hi"}}]}

    with patch("gateway.app.load_prompt", return_value="BASE SYSTEM"), patch(
        "gateway.memory.get_context_block",
        return_value="## What Kitty knows about Jacob:\n- Jacob lives in Regina",
    ), patch(
        "gateway.knowledge.get_knowledge_block",
        return_value="## Relevant knowledge from Kitty's knowledge base:\nRegina weather context",
    ), patch(
        "gateway.app._non_stream_response",
        new=AsyncMock(side_effect=_fake_non_stream_response),
    ):
        client = TestClient(app)
        response = client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "Where do I live?"}],
                "stream": False,
            },
        )

    assert response.status_code == 200
    system_prompt = captured_payload["value"]["messages"][0]["content"]
    assert "BASE SYSTEM" in system_prompt
    assert "Jacob lives in Regina" in system_prompt
    assert "Relevant knowledge" in system_prompt


def test_health_domain_routes_to_health():
    domain = classify_domain("my blood pressure has been high lately")
    assert domain == "health"
