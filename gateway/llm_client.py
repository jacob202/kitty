"""Unified LLM client — all LLM calls go through LiteLLM for cost tracking and fallbacks.

ROUTING OWNERSHIP: This module owns model routing for the Python backend (API calls
from gateway workers, brief generation, specialists, etc.). It uses a 3-decision router:
  offline → mlx-local
  reasoning keywords → kitty-agent (LiteLLM virtual)
  "best"/"claude" trigger → kitty-smart
  default → kitty-default

OpenRouter direct fallbacks map kitty-* → real provider IDs (see _LITELLM_TO_OPENROUTER).

After LiteLLM, fallbacks are: OpenRouter direct (cheap/free slugs) → Gemini → AgentRouter →
NVIDIA NIM (when the corresponding env keys are set). OpenRouter is tried first so local ingest
works when the proxy is down but OPENROUTER_API_KEY is set.

Successful completions append one row to data/kitty_token_log.jsonl via gateway.token_usage_log
when the API returns a ``usage`` object (OpenAI-compatible).

Open WebUI routing is owned separately by kitty_gateway/litellm_config.yaml — it uses
named virtual models (kitty-default, kitty-agent, kitty-smart). Both layers must reference
the same canonical model IDs to stay consistent.
"""
from __future__ import annotations

import os
import logging
import threading
import time
import requests
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger("kitty.llm_client")

from gateway.paths import LITELLM_BASE, LITELLM_KEY
from gateway.token_usage_log import log_llm_usage, normalize_usage_payload
from gateway.llm_utils import retry_with_backoff

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# LiteLLM virtual names (kitty_gateway/litellm_config.yaml) — valid toward localhost:8001 only.
_LITELLM_DEFAULT = "kitty-default"
_LITELLM_AGENT = "kitty-agent"
_LITELLM_SMART = "kitty-smart"

# OpenRouter-direct slugs when LiteLLM returns errors (must be valid OpenRouter model IDs).


def _env_slug(name: str, default: str) -> str:
    load_dotenv()
    v = os.environ.get(name, "").strip()
    return v if v else default


_OPENROUTER_DEFAULT = _env_slug("KITTY_OPENROUTER_CHEAP", "deepseek/deepseek-v4-flash")
_OPENROUTER_REASONING = _env_slug("KITTY_OPENROUTER_REASONING", "deepseek/deepseek-v4-flash")
_OPENROUTER_BEST = _env_slug("KITTY_OPENROUTER_BEST", "claude-sonnet-4-6")

# route_model() picks LiteLLM names first so a healthy proxy gets virtual models + fallbacks config.
_DEFAULT_MODEL = _LITELLM_DEFAULT
_REASONING_MODEL = _LITELLM_AGENT
_BEST_MODEL = _LITELLM_SMART
_LOCAL_MODEL = "mlx-local"

_LITELLM_TO_OPENROUTER: dict[str, str] = {
    _LITELLM_DEFAULT: _OPENROUTER_DEFAULT,
    _LITELLM_AGENT: _OPENROUTER_REASONING,
    _LITELLM_SMART: _OPENROUTER_BEST,
    "kitty-parts": _OPENROUTER_DEFAULT,
    "kitty-fallback-or": "qwen/qwen3-235b-a22b:free",
    _LOCAL_MODEL: "qwen/qwen3-235b-a22b:free",
}


def _openrouter_fallback_model(litellm_model: str) -> str:
    """Map LiteLLM-only model ids to OpenRouter-compatible ids."""
    direct = os.environ.get("KITTY_OPENROUTER_DIRECT_MODEL", "").strip()
    if direct:
        return direct
    return _LITELLM_TO_OPENROUTER.get(litellm_model, litellm_model)


def _agentrouter_model_id() -> str:
    """OpenAI-style id for AgentRouter direct calls (not OpenRouter-style slugs)."""
    return (
        os.environ.get("KITTY_AGENTROUTER_CHAT_MODEL")
        or os.environ.get("AGENTROUTER_MODEL")
        or "gpt-4o-mini"
    )


def _finalize_openai_shape_response(
    data: dict[str, Any],
    *,
    provider: str,
    model_logged: str,
    operation: str,
    route: str,
    request_model: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    """Extract assistant text, normalize usage, append JSONL row, return text."""
    try:
        text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        logger.error("Malformed response from %s: %s", provider, data)
        return ""

    usage = normalize_usage_payload(data.get("usage") if isinstance(data.get("usage"), dict) else None)
    meta: dict[str, Any] = {**(metadata or {}), "route": route, "completion_chars": len(text)}
    if request_model:
        meta["request_model"] = request_model
    log_llm_usage(provider, model_logged, operation, usage, meta)
    return text


def call_llm(
    messages: list[dict],
    model: str = None,
    max_tokens: int = 1500,
    temperature: float = 0.7,
    timeout: int = 60,
    response_format: dict = None,
    operation: str = "llm.call",
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Centralized hub for all LLM calls.
    Tries LiteLLM proxy first, then OpenRouter direct (cheap/free), then AgentRouter, then NVIDIA.
    """
    if model is None:
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break
        model = route_model(user_msg)

    try:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        resp = requests.post(
            f"{LITELLM_BASE}/v1/chat/completions",
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        mlog = data.get("model") or model
        return _finalize_openai_shape_response(
            data,
            provider="litellm",
            model_logged=str(mlog),
            operation=operation,
            route="litellm_proxy",
            request_model=model,
            metadata=metadata,
        )
    except Exception as e:
        logger.warning("LLM call failed via LiteLLM (%s), trying fallbacks: %s", model, e)

        # 1. Try OpenRouter direct before higher-friction fallbacks.
        or_model = _openrouter_fallback_model(model)
        out = _call_openrouter_direct(
            messages,
            or_model,
            max_tokens,
            temperature,
            timeout,
            response_format,
            operation=operation,
            metadata=metadata,
            request_model=model,
        )
        if out:
            return out

        # 2. Try Gemini (cheap and reliable when present).
        out = _call_gemini_direct(
            messages,
            max_tokens,
            temperature,
            timeout,
            response_format,
            operation=operation,
            metadata=metadata,
            request_model=model,
        )
        if out:
            return out

        # 3. Try AgentRouter.
        out = _call_agentrouter_direct(
            messages,
            max_tokens,
            temperature,
            timeout,
            response_format,
            operation=operation,
            metadata=metadata,
            request_model=model,
        )
        if out:
            return out

        # 4. Try NVIDIA NIM.
        out = _call_nvidia_direct(
            messages,
            max_tokens,
            temperature,
            timeout,
            response_format,
            operation=operation,
            metadata=metadata,
            request_model=model,
        )
        if out:
            return out

        return ""


@retry_with_backoff
def _call_gemini_direct(
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    timeout: int,
    response_format: dict = None,
    operation: str = "llm.call",
    metadata: dict[str, Any] | None = None,
    request_model: str | None = None,
) -> str:
    """Direct call to Google Gemini 1.5 Flash."""
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return ""

    model = "gemini-1.5-flash-latest"
    base = "https://generativelanguage.googleapis.com/v1beta/openai"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format

    try:
        resp = requests.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=timeout)
        if resp.status_code != 200:
            logger.error("Gemini call failed (%d): %s", resp.status_code, resp.text[:500])
            return ""
        data = resp.json()
        mlog = data.get("model") or model
        return _finalize_openai_shape_response(
            data,
            provider="gemini",
            model_logged=str(mlog),
            operation=operation,
            route="gemini_direct",
            request_model=request_model,
            metadata=metadata,
        )
    except Exception as e:
        logger.error("Gemini call failed: %s", e)
        return ""


@retry_with_backoff
def _call_openrouter_direct(
    messages: list[dict],
    model: str,
    max_tokens: int,
    temperature: float,
    timeout: int,
    response_format: dict = None,
    operation: str = "llm.call",
    metadata: dict[str, Any] | None = None,
    request_model: str | None = None,
) -> str:
    """Direct call to OpenRouter with explicit env loading."""
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("No OPENROUTER_API_KEY found for direct call.")
        return ""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/jacobbrizinski/kitty",
        "X-Title": "Kitty Gateway",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format

    try:
        resp = requests.post(f"{OPENROUTER_BASE}/chat/completions", headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        mlog = data.get("model") or model
        return _finalize_openai_shape_response(
            data,
            provider="openrouter",
            model_logged=str(mlog),
            operation=operation,
            route="openrouter_direct",
            request_model=request_model,
            metadata=metadata,
        )
    except Exception as e:
        logger.error("OpenRouter direct call failed: %s", e)
        return ""

@retry_with_backoff
def _call_agentrouter_direct(
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    timeout: int,
    response_format: dict = None,
    operation: str = "llm.call",
    metadata: dict[str, Any] | None = None,
    request_model: str | None = None,
) -> str:
    load_dotenv(override=True)
    api_key = os.environ.get("AGENTROUTER_API_KEY")
    base = os.environ.get("AGENTROUTER_API_BASE", "https://agentrouter.org/v1").rstrip("/")
    
    # If request_model is provided and isn't a LiteLLM virtual name, use it. Otherwise use env fallback.
    if request_model and request_model not in ("kitty-default", "kitty-agent", "kitty-smart", "kitty-parts", "mlx-local"):
        ar_model = request_model
    else:
        ar_model = _agentrouter_model_id()
        
    if not api_key:
        logger.debug("AgentRouter skipped: AGENTROUTER_API_KEY not set")
        return ""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": ar_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format

    try:
        resp = requests.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        mlog = data.get("model") or ar_model
        return _finalize_openai_shape_response(
            data,
            provider="agentrouter",
            model_logged=str(mlog),
            operation=operation,
            route="agentrouter_direct",
            request_model=request_model,
            metadata=metadata,
        )
    except Exception as e:
        logger.error("AgentRouter direct call failed: %s", e)
        return ""

@retry_with_backoff
def _call_nvidia_direct(
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    timeout: int,
    response_format: dict = None,
    operation: str = "llm.call",
    metadata: dict[str, Any] | None = None,
    request_model: str | None = None,
) -> str:
    load_dotenv()
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        return ""

    base = os.environ.get("NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1").rstrip("/")
    nv_model = os.environ.get("NVIDIA_CHAT_MODEL", "deepseek-ai/deepseek-v4-pro")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": nv_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format

    try:
        resp = requests.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        mlog = data.get("model") or nv_model
        return _finalize_openai_shape_response(
            data,
            provider="nvidia",
            model_logged=str(mlog),
            operation=operation,
            route="nvidia_direct",
            request_model=request_model,
            metadata=metadata,
        )
    except Exception as e:
        logger.error("NVIDIA direct call failed: %s", e)
        return ""


def chat(model: str, messages: list[dict], max_tokens: int = 500, temperature: float = 0.7) -> str:
    return call_llm(messages, model=model, max_tokens=max_tokens, temperature=temperature)


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
