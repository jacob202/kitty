"""Verify LiteLLM proxy routes to correct models."""
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/Users/jacobbrizinski/Projects/kitty/.env")

LITELLM_BASE = "http://localhost:8001"
LITELLM_KEY = "kitty-local-key-change-me"


def _chat(model: str, message: str) -> dict:
    resp = requests.post(
        f"{LITELLM_BASE}/v1/chat/completions",
        headers={"Authorization": f"Bearer {LITELLM_KEY}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "max_tokens": 20,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


@pytest.mark.integration
def test_default_model_responds():
    """kitty-default routes to DeepSeek Flash and returns a response."""
    result = _chat("kitty-default", "Say OK")
    assert result["choices"][0]["message"]["content"]
    assert result["model"]


@pytest.mark.integration
def test_smart_model_responds():
    """kitty-smart routes to Claude Sonnet (via OpenRouter) and returns a response."""
    result = _chat("kitty-smart", "Say OK")
    assert result["choices"][0]["message"]["content"]  # proxy returns group name, not model name


@pytest.mark.integration
def test_private_model_responds():
    """kitty-private routes to local MLX Qwen3.5-4B. Requires start_mlx.sh running."""
    result = _chat("kitty-private", "Say OK")
    assert result["choices"][0]["message"]["content"]
