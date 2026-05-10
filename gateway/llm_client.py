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

_DEFAULT_MODEL = "qwen/qwen3-235b-a22b-2507"
_REASONING_MODEL = "deepseek/deepseek-r1-0528"
_BEST_MODEL = "claude-sonnet-4-6"
_LOCAL_MODEL = "mlx-local"


import time
import threading

_offline_cache: tuple[bool, float] | None = None
_offline_lock = threading.Lock()

def _check_connectivity() -> bool:
    import socket
    try:
        with socket.create_connection(("openrouter.ai", 443), timeout=2):
            return False
    except OSError:
        return True

def _is_offline() -> bool:
    """Return True when OpenRouter is unreachable."""
    global _offline_cache
    with _offline_lock:
        now = time.monotonic()
        if _offline_cache and now - _offline_cache[1] < 30:
            return _offline_cache[0]
        result = _check_connectivity()
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
