"""Unified LLM client — all LLM calls go through LiteLLM for cost tracking and fallbacks.

ROUTING OWNERSHIP: This module owns model routing for the Python backend (API calls
from gateway workers, brief generation, specialists, etc.). It uses a 3-decision router:
  offline → mlx-local
  reasoning keywords → deepseek-r1
  "best"/"claude" trigger → claude-sonnet
  default → qwen3-235b-a22b:free

Open WebUI routing is owned separately by kitty_gateway/litellm_config.yaml — it uses
named virtual models (kitty-default, kitty-agent, kitty-smart). Both layers must reference
the same canonical model IDs to stay consistent.
"""
import os
import logging
import threading
import time
import requests

logger = logging.getLogger("kitty.llm_client")

from gateway.paths import LITELLM_BASE, LITELLM_KEY


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


_REASONING_KEYWORDS = frozenset(
    {
        "explain",
        "why",
        "analyze",
        "analyse",
        "reason",
        "think through",
        "break down",
        "compare",
        "pros and cons",
        "pros cons",
        "step by step",
        "walk me through",
        "how does",
        "what causes",
    }
)

_BEST_TRIGGERS = frozenset(
    {
        "best model",
        "use claude",
        "use sonnet",
        "use your best",
        "most capable",
        "smartest model",
    }
)

# This ID routes through OpenRouter directly (Python backend).
# litellm_config.yaml uses openrouter/qwen/qwen3-235b-a22b:free for the same model
# via the LiteLLM proxy — different prefix format, same underlying model.
_DEFAULT_MODEL = "qwen/qwen3-235b-a22b:free"
_REASONING_MODEL = "deepseek/deepseek-r1-0528"
_BEST_MODEL = "claude-sonnet-4-6"
_LOCAL_MODEL = "mlx-local"


_offline_cache: tuple[bool, float] | None = None
_offline_lock = threading.Lock()
_OFFLINE_CACHE_TTL = 30.0


def _is_offline() -> bool:
    """Return True when OpenRouter is unreachable. Result cached for 30s."""
    import socket

    global _offline_cache
    with _offline_lock:
        now = time.monotonic()
        if _offline_cache is not None and now - _offline_cache[1] < _OFFLINE_CACHE_TTL:
            return _offline_cache[0]
        try:
            with socket.create_connection(("openrouter.ai", 443), timeout=2):
                result = False
        except OSError:
            result = True
        _offline_cache = (result, now)
        return result


def route_model(message: str) -> str:
    """3-decision router for non-health model selection."""
    if _is_offline():
        logger.debug("routing: offline -> %s", _LOCAL_MODEL)
        return _LOCAL_MODEL

    msg_lower = message.lower()

    if any(trigger in msg_lower for trigger in _BEST_TRIGGERS):
        logger.debug("routing: best trigger -> %s", _BEST_MODEL)
        return _BEST_MODEL

    if any(keyword in msg_lower for keyword in _REASONING_KEYWORDS):
        logger.debug("routing: reasoning keyword -> %s", _REASONING_MODEL)
        return _REASONING_MODEL

    logger.debug("routing: default -> %s", _DEFAULT_MODEL)
    return _DEFAULT_MODEL
