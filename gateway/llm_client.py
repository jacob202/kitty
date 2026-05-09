"""Unified LLM client — all LLM calls go through LiteLLM for cost tracking and fallbacks."""
import os
import logging
import requests

logger = logging.getLogger("kitty.llm_client")

LITELLM_BASE = "http://localhost:8001"
LITELLM_KEY = "kitty-local-key-change-me"


def chat(model: str, messages: list[dict], max_tokens: int = 500, temperature: float = 0.7) -> str:
    """Send a chat request through LiteLLM proxy. Returns response text."""
    try:
        resp = requests.post(
            f"{LITELLM_BASE}/v1/chat/completions",
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning("LLM call failed via LiteLLM (%s), falling back to OpenRouter: %s", model, e)
        return _fallback_openrouter(model, messages, max_tokens, temperature)


def _fallback_openrouter(model: str, messages: list[dict], max_tokens: int, temperature: float) -> str:
    """Fallback: call OpenRouter directly if LiteLLM is down."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("No OPENROUTER_API_KEY and LiteLLM is down")
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/jacobbrizinski/kitty",
            "X-Title": "Kitty Gateway",
        },
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()
