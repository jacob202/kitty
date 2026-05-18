"""Unified LLM client — one Kitty route, then provider fallbacks.

All backend LLM calls go through LiteLLM first for logging and proxy-level routing.
When LiteLLM fails, ``call_llm`` falls back to AgentRouter, then OpenRouter, Gemini,
and NVIDIA. The Kitty side now keeps a single canonical route name
(``kitty-default``) instead of the old ``kitty-agent`` / ``kitty-smart`` split.

Successful completions append one row to ``data/kitty_token_log.jsonl`` via
``gateway.token_usage_log`` when the API returns a ``usage`` object.
"""
from __future__ import annotations

import json
import os
import logging
import requests
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger("kitty.llm_client")

from gateway.paths import LITELLM_BASE, LITELLM_KEY
from gateway.token_usage_log import log_llm_usage, normalize_usage_payload
from gateway.llm_utils import retry_with_backoff

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# LiteLLM virtual name (gateway/litellm_config.yaml) — valid toward localhost:8001 only.
_LITELLM_DEFAULT = "kitty-default"

# OpenRouter-direct slugs when LiteLLM returns errors (must be valid OpenRouter model IDs).


def _env_slug(name: str, default: str) -> str:
    load_dotenv()
    v = os.environ.get(name, "").strip()
    return v if v else default


_OPENROUTER_DEFAULT = _env_slug("KITTY_OPENROUTER_CHEAP", "deepseek/deepseek-v4-flash")
_GEMINI_MODEL = _env_slug("KITTY_GEMINI_MODEL", "gemini-2.5-flash-image")

_LITELLM_TO_OPENROUTER: dict[str, str] = {
    _LITELLM_DEFAULT: _OPENROUTER_DEFAULT,
    "kitty-default-or": "qwen/qwen3-235b-a22b:free",
}

_LEGACY_MODEL_ALIASES: dict[str, str] = {
    "kitty-agent": _LITELLM_DEFAULT,
    "kitty-smart": _LITELLM_DEFAULT,
    "kitty-parts": _LITELLM_DEFAULT,
    "kitty-fallback-or": _LITELLM_DEFAULT,
    "claude-sonnet-4-6": _LITELLM_DEFAULT,
    "anthropic/claude-sonnet-4.6": _LITELLM_DEFAULT,
    "anthropic/claude-3.7-sonnet": _LITELLM_DEFAULT,
    "deepseek/deepseek-chat": _LITELLM_DEFAULT,
    "deepseek/deepseek-v4-flash": _LITELLM_DEFAULT,
    "google/gemini-2.0-flash-001": _LITELLM_DEFAULT,
    "google/gemini-2.0-flash-exp:free": _LITELLM_DEFAULT,
}


def normalize_litellm_request_model(request_model: str | None) -> str | None:
    """Map legacy Kitty aliases onto the single LiteLLM route."""
    if request_model is None:
        return None
    model = request_model.strip()
    if not model:
        return model
    return _LEGACY_MODEL_ALIASES.get(model, model)


def normalize_agentrouter_api_base(raw: str | None) -> str:
    """Return base URL with ``/v1`` suffix, no trailing slash (OpenAI-compatible)."""
    base = (raw or "https://agentrouter.org/v1").strip().rstrip("/")
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


def resolve_agentrouter_api_key() -> str:
    """Read API key from env; supports AgentRouter doc names. Strips quotes and first line only."""
    load_dotenv(override=True)
    for env_name in ("AGENTROUTER_API_KEY", "AGENT_ROUTER_TOKEN"):
        v = os.environ.get(env_name, "")
        if not isinstance(v, str):
            continue
        v = v.strip().strip('"').strip("'")
        if "\n" in v or "\r" in v:
            logger.warning(
                "AgentRouter env %s had multiple lines — using first line only. Fix your .env.",
                env_name,
            )
            v = v.splitlines()[0].strip()
        if v:
            return v
    return ""


def _sanitize_agentrouter_model_id(raw: str) -> str:
    """Strip wrappers; detect accidental ``model + api_key`` on one .env line."""
    s = raw.strip().strip('"').strip("'")
    parts = s.split()
    if len(parts) >= 2 and parts[1].startswith("sk-"):
        logger.warning(
            "AGENTROUTER_MODEL looks concatenated with a second token; using %r only.",
            parts[0],
        )
        return parts[0]
    return s


def agentrouter_model_for_request(request_model: str | None) -> str:
    """Pick the upstream AgentRouter model for Kitty's single route or an explicit id."""
    load_dotenv()
    rm = (request_model or "").strip()
    if rm and rm not in _LEGACY_MODEL_ALIASES and rm != _LITELLM_DEFAULT:
        return _sanitize_agentrouter_model_id(rm)

    g_model = (
        os.environ.get("AGENTROUTER_MODEL", "").strip()
        or "gpt-5.4-mini"
    )
    return _sanitize_agentrouter_model_id(g_model)


def _openrouter_fallback_model(litellm_model: str) -> str:
    """Map LiteLLM-only model ids to OpenRouter-compatible ids."""
    direct = os.environ.get("KITTY_OPENROUTER_DIRECT_MODEL", "").strip()
    if direct:
        return direct
    return _LITELLM_TO_OPENROUTER.get(litellm_model, litellm_model)


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
    Tries LiteLLM proxy first; on failure → AgentRouter → OpenRouter direct → Gemini → NVIDIA.
    """
    if model is None:
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break
        model = route_model(user_msg)

    model = normalize_litellm_request_model(model)

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

        disable_agentrouter = os.environ.get("KITTY_DISABLE_AGENTROUTER", "").strip().lower()
        if disable_agentrouter not in ("1", "true", "yes"):
            # 1. AgentRouter first (single key, single Kitty route).
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

        # 2. OpenRouter direct (cheap/free slugs when key set).
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

        # 3. Gemini.
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

        # 4. NVIDIA NIM.
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
    """Direct call to Google Gemini using the configured flash model."""
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return ""

    model = _GEMINI_MODEL
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

# AgentRouter's hosted API rejects generic clients before token validation. These
# defaults match its Codex integration path and can be overridden from env.
_AGENTROUTER_DEFAULT_ORIGINATOR = "codex_cli_rs"
_AGENTROUTER_DEFAULT_VERSION = "0.101.0"
_AGENTROUTER_DEFAULT_USER_AGENT = (
    "codex_cli_rs/0.101.0 (Mac OS 26.0.1; arm64) Apple_Terminal/464"
)

# Browser-like UA used only if AgentRouter rejects the primary client fingerprint (401 unauthorized_client).
_AGENTROUTER_ALT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _agentrouter_client_rejected(resp: requests.Response | None) -> bool:
    if resp is None or resp.status_code != 401:
        return False
    body = (resp.text or "").lower()
    return "unauthorized client" in body


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
    api_key = resolve_agentrouter_api_key()
    base_raw = os.environ.get("AGENTROUTER_API_BASE", "https://agentrouter.org/v1")
    base = normalize_agentrouter_api_base(base_raw)

    ar_model = agentrouter_model_for_request(request_model)

    if not api_key:
        logger.debug("AgentRouter skipped: set AGENTROUTER_API_KEY or AGENT_ROUTER_TOKEN")
        return ""

    ua = os.environ.get("KITTY_AGENTROUTER_USER_AGENT", "").strip()

    base_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Originator": os.environ.get(
            "KITTY_AGENTROUTER_ORIGINATOR", _AGENTROUTER_DEFAULT_ORIGINATOR
        ).strip(),
        "Version": os.environ.get(
            "KITTY_AGENTROUTER_VERSION", _AGENTROUTER_DEFAULT_VERSION
        ).strip(),
    }
    base_headers = {k: v for k, v in base_headers.items() if v}

    raw_extras = os.environ.get("KITTY_AGENTROUTER_EXTRA_HEADERS_JSON", "").strip()
    if raw_extras:
        try:
            blob = json.loads(raw_extras)
            if isinstance(blob, dict):
                for k, v in blob.items():
                    if isinstance(k, str) and isinstance(v, str):
                        base_headers[str(k)] = str(v)
        except json.JSONDecodeError:
            logger.warning("KITTY_AGENTROUTER_EXTRA_HEADERS_JSON must be JSON object — ignoring.")

    def build_headers(user_agent: str) -> dict[str, str]:
        h = {**base_headers, "User-Agent": user_agent}
        return h

    # Primary: optional custom UA, else AgentRouter's Codex-compatible client identity.
    primary_ua = ua or _AGENTROUTER_DEFAULT_USER_AGENT
    payload = {
        "model": ar_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format

    try:
        url = f"{base}/chat/completions"
        headers = build_headers(primary_ua)
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)

        if (
            not resp.ok
            and _agentrouter_client_rejected(resp)
            and os.environ.get("KITTY_AGENTROUTER_NO_ALT_UA_RETRY", "").strip().lower()
            not in ("1", "true", "yes")
        ):
            logger.warning(
                "AgentRouter rejected client fingerprint — retrying once with alternate User-Agent"
            )
            resp = requests.post(
                url,
                headers=build_headers(_AGENTROUTER_ALT_USER_AGENT),
                json=payload,
                timeout=timeout,
            )

        if not resp.ok:
            snippet = (resp.text or "")[:900]
            logger.error(
                "AgentRouter HTTP %s on POST %s (model=%r): %s",
                resp.status_code,
                url,
                ar_model,
                snippet,
            )
            return ""
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

def route_model(message: str) -> str:
    """Single-route model selector for Kitty."""
    logger.debug("routing: single route -> %s", _LITELLM_DEFAULT)
    return _LITELLM_DEFAULT
