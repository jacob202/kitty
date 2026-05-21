"""Eval: does gateway inject memory and knowledge context into system prompt?"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from gateway.app import app
from gateway.domain_router import classify_domain


def test_memory_and_knowledge_injected_into_system_prompt() -> None:
    captured_payload: dict = {}

    async def _fake_non_stream_response(payload):
        captured_payload["value"] = payload
        return {
            "id": "ok",
            "choices": [{"message": {"role": "assistant", "content": "hi"}}],
        }

    # context_builder pulls base text via prompt_loader; context via memory_graph.
    with patch("gateway.prompt_loader.load_prompt", return_value="BASE SYSTEM"), patch(
        "gateway.context_builder.memory_graph.unified_context",
        new=AsyncMock(
            return_value="## Memory\n- Jacob lives in Regina\n\n## Knowledge\nRegina weather context"
        ),
    ), patch(
        "gateway.routes.completions._non_stream_response",
        new=AsyncMock(side_effect=_fake_non_stream_response),
    ):
        with TestClient(app) as client:
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
    assert "Knowledge" in system_prompt


def test_health_domain_routes_to_health() -> None:
    domain = classify_domain("my blood pressure has been high lately")
    assert domain == "health"
