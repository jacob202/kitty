"""Eval: does gateway inject memory and knowledge context into system prompt?"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from gateway.domain_router import classify_domain


def test_memory_and_knowledge_injected_into_system_prompt() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "hi"}}],
        "usage": {"total_tokens": 10},
        "model": "kitty-default",
    }

    # Patch at the boundary (HTTP and Prompt Loading)
    with (
        patch("gateway.prompts.load_prompt", return_value="BASE SYSTEM"),
        patch(
            "gateway.context_assembler.assemble_context",
            new=AsyncMock(
                return_value=__import__(
                    "gateway.context_assembler", fromlist=["ContextBundle"]
                ).ContextBundle(
                    system="BASE SYSTEM\n\n## Memory\n- Jacob lives in Regina\n\n## Knowledge\nRegina weather context"
                )
            ),
        ),
        patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)) as mock_post,
    ):
        from gateway.app import app

        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "Where do I live?"}],
                    "stream": False,
                },
            )

    assert response.status_code == 200
    # Check that the system prompt passed to HTTP call contains the context
    payload = mock_post.call_args.kwargs["json"]
    system_prompt = payload["messages"][0]["content"]
    assert "BASE SYSTEM" in system_prompt
    assert "Jacob lives in Regina" in system_prompt
    assert "Knowledge" in system_prompt


def test_health_domain_routes_to_health() -> None:
    domain = classify_domain("my blood pressure has been high lately")
    assert domain == "health"
