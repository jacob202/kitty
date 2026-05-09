"""Integration tests for Kitty Gateway. Requires gateway + LiteLLM running."""
import pytest
import requests

GATEWAY_BASE = "http://localhost:8000"


@pytest.mark.integration
def test_health_endpoint():
    resp = requests.get(f"{GATEWAY_BASE}/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.integration
def test_chat_returns_stream():
    resp = requests.post(
        f"{GATEWAY_BASE}/v1/chat/completions",
        json={
            "model": "kitty-default",
            "messages": [{"role": "user", "content": "Say OK in one word"}],
            "stream": True,
        },
        stream=True,
        timeout=30,
    )
    assert resp.status_code == 200
    # Read first chunk — should be SSE data
    first = next(resp.iter_lines())
    assert first  # not empty


@pytest.mark.integration
def test_domain_injection_soul():
    """Non-domain message goes through soul prompt."""
    resp = requests.post(
        f"{GATEWAY_BASE}/v1/chat/completions",
        json={
            "model": "kitty-default",
            "messages": [{"role": "user", "content": "who are you?"}],
            "stream": False,
        },
        timeout=30,
    )
    assert resp.status_code == 200
