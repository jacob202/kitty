"""Unified LLM client — one Kitty route, then provider fallbacks.

All backend LLM calls go through LiteLLM first for logging and proxy-level routing.
When LiteLLM fails, ``call_llm`` walks the ``PROVIDERS`` table in
``PROVIDER_FALLBACK_ORDER`` and calls ``_call_provider`` for each entry.
The dispatcher is generic: provider-specific behavior is data on
``ProviderConfig`` (``static_headers``, ``model_resolver``,
``request_mutator``, ``post_processor``). Adding a new provider is a
new entry in the table — no new top-level function.

Successful completions append one row to ``data/kitty_token_log.jsonl`` via
``gateway.token_usage_log`` when the API returns a ``usage`` object.
"""

from __future__ import annotations

import json
import os
import logging
import httpx
from dataclasses import dataclass, field
from typing import Any, Callable

from dotenv import load_dotenv

logger = logging.getLogger("kitty.llm_client")

from gateway.paths import LITELLM_BASE, LITELLM_KEY
from gateway.token_usage_log import log_llm_usage, normalize_usage_payload
from gateway.llm_utils import retry_with_backoff

# Optional tenacity retry on transient network and upstream server errors.
# 4xx errors (auth, bad model) return immediately so provider-specific handling
# or the fallback chain can take over.
try:
    from tenacity import (
        retry as _tenacity_retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type,
    )

    _retry_post = _tenacity_retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.3, min=0.3, max=1.5),
        retry=retry_if_exception_type(
            (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)
        ),
        reraise=True,
    )
except ImportError:  # pragma: no cover - optional dependency

    def _retry_post(fn):  # type: ignore[misc]
        return fn


@_retry_post
def _post(*args, **kwargs):
    """POST once via ``httpx``, retrying only transport failures and HTTP 5xx responses."""
    response = httpx.post(*args, **kwargs)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int) and 500 <= status_code <= 599:
        raise httpx.HTTPStatusError(
            f"Transient upstream server error: HTTP {status_code}",
            request=response.request,
            response=response,
        )
    return response


OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# LiteLLM virtual name (gateway/litellm_config.yaml) — valid toward localhost:8001 only.
_LITELLM_DEFAULT = "kitty-default"


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

    g_model = os.environ.get("AGENTROUTER_MODEL", "").strip() or "gpt-5.4-mini"
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

    usage = normalize_usage_payload(
        data.get("usage") if isinstance(data.get("usage"), dict) else None
    )
    meta: dict[str, Any] = {
        **(metadata or {}),
        "route": route,
        "completion_chars": len(text),
    }
    if request_model:
        meta["request_model"] = request_model
    log_llm_usage(provider, model_logged, operation, usage, meta)
    return text


# --- Provider dispatcher ------------------------------------------------------
#
# Each of the 5 LLM providers becomes one row in ``PROVIDERS``. The dispatcher
# is generic: API-key resolution, model resolution, header building, HTTP POST,
# and response extraction are all driven by the table. Provider-specific
# behavior (e.g. AgentRouter's alt-UA retry) is data on the row.


@dataclass(frozen=True)
class ProviderConfig:
    """One row in the ``PROVIDERS`` table.

    Adding a new provider is a new entry here, not new code in this file.
    For providers with special behavior, supply a ``request_mutator`` and/or
    ``post_processor``. Most providers need neither.
    """

    name: str
    route: str
    base_url: str
    api_key_env: tuple[str, ...] = ()
    model_default: str = ""
    model_env: str | None = None
    static_headers: dict[str, str] = field(default_factory=dict)
    # Optional overrides for providers whose key/model resolution needs special
    # handling (e.g. AgentRouter's multi-line .env guard). When None, the
    # generic resolver is used.
    key_resolver: Callable[[], str] | None = None
    model_resolver: Callable[[str | None], str] | None = None
    request_mutator: Callable[[dict, dict, str | None], tuple[dict, dict]] | None = None
    post_processor: Callable[[httpx.Response, dict], httpx.Response] | None = None


def _agentrouter_client_rejected(resp: httpx.Response | None) -> bool:
    if resp is None or resp.status_code != 401:
        return False
    body = (resp.text or "").lower()
    return "unauthorized client" in body


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


def _agentrouter_request_mutator(
    payload: dict, headers: dict, request_model: str | None
) -> tuple[dict, dict]:
    """Add AgentRouter-specific headers (User-Agent, Originator, Version, optional JSON extras)."""
    load_dotenv(override=True)
    ua = os.environ.get("KITTY_AGENTROUTER_USER_AGENT", "").strip()
    primary_ua = ua or _AGENTROUTER_DEFAULT_USER_AGENT

    extra = {
        "Accept": "application/json",
        "Originator": os.environ.get(
            "KITTY_AGENTROUTER_ORIGINATOR", _AGENTROUTER_DEFAULT_ORIGINATOR
        ).strip(),
        "Version": os.environ.get(
            "KITTY_AGENTROUTER_VERSION", _AGENTROUTER_DEFAULT_VERSION
        ).strip(),
    }
    extra = {k: v for k, v in extra.items() if v}

    raw_extras = os.environ.get("KITTY_AGENTROUTER_EXTRA_HEADERS_JSON", "").strip()
    if raw_extras:
        try:
            blob = json.loads(raw_extras)
            if isinstance(blob, dict):
                for k, v in blob.items():
                    if isinstance(k, str) and isinstance(v, str):
                        extra[str(k)] = str(v)
        except json.JSONDecodeError:
            logger.warning(
                "KITTY_AGENTROUTER_EXTRA_HEADERS_JSON must be JSON object — ignoring."
            )

    headers = {**headers, **extra, "User-Agent": primary_ua}
    return payload, headers


def _agentrouter_post_processor(resp: httpx.Response, ctx: dict) -> httpx.Response:
    """Retry once with alt User-Agent if AgentRouter rejects the primary client fingerprint."""
    if (
        not resp.ok
        and _agentrouter_client_rejected(resp)
        and os.environ.get("KITTY_AGENTROUTER_NO_ALT_UA_RETRY", "").strip().lower()
        not in ("1", "true", "yes")
    ):
        logger.warning(
            "AgentRouter rejected client fingerprint — retrying once with alternate User-Agent"
        )
        alt_headers = {**ctx["headers"], "User-Agent": _AGENTROUTER_ALT_USER_AGENT}
        return _post(
            ctx["url"],
            headers=alt_headers,
            json=ctx["payload"],
            timeout=ctx["timeout"],
        )
    return resp


def _resolve_provider_api_key(envs: tuple[str, ...]) -> str:
    """Read API key from the first matching env var in the table entry.

    The env var *name* lives in the table (read once at import); the *value*
    is read on each call. Callers are responsible for having loaded ``.env``
    (``_call_provider`` does this once up front) so changes take effect without
    a restart. Providers that need richer key handling (e.g. AgentRouter's
    multi-line guard) supply a ``key_resolver`` instead.
    """
    for env_name in envs:
        v = os.environ.get(env_name, "")
        if not isinstance(v, str):
            continue
        v = v.strip().strip('"').strip("'")
        if v:
            return v
    return ""


def _resolve_provider_model(
    provider: ProviderConfig, request_model: str | None
) -> str:
    """Pick the upstream model id. ``model_resolver`` wins over env/default."""
    if provider.model_resolver is not None:
        return provider.model_resolver(request_model)
    if provider.model_env:
        env_val = os.environ.get(provider.model_env, "").strip()
        if env_val:
            return env_val
    return provider.model_default


PROVIDERS: dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        name="openai",
        route="openai_direct",
        base_url="https://api.openai.com/v1",
        api_key_env=("OPENAI_API_KEY",),
        model_default="gpt-4o-mini",
        model_env="KITTY_OPENAI_FALLBACK_MODEL",
    ),
    "nvidia": ProviderConfig(
        name="nvidia",
        route="nvidia_direct",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key_env=("NVIDIA_API_KEY",),
        model_default="deepseek-ai/deepseek-v4-pro",
        model_env="NVIDIA_CHAT_MODEL",
    ),
    "agentrouter": ProviderConfig(
        name="agentrouter",
        route="agentrouter_direct",
        base_url=normalize_agentrouter_api_base(
            os.environ.get("AGENTROUTER_API_BASE", "https://agentrouter.org/v1")
        ),
        api_key_env=("AGENTROUTER_API_KEY", "AGENT_ROUTER_TOKEN"),
        model_default="gpt-5.4-mini",
        # AgentRouter .env values are prone to multi-line paste errors; the
        # dedicated resolver warns and takes the first line instead of silently
        # shipping a corrupt Bearer token.
        key_resolver=resolve_agentrouter_api_key,
        model_resolver=lambda request_model: agentrouter_model_for_request(request_model),
        request_mutator=_agentrouter_request_mutator,
        post_processor=_agentrouter_post_processor,
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        route="openrouter_direct",
        base_url=OPENROUTER_BASE,
        api_key_env=("OPENROUTER_API_KEY",),
        model_default="",
        model_resolver=lambda request_model: _openrouter_fallback_model(
            request_model or _LITELLM_DEFAULT
        ),
        static_headers={
            "HTTP-Referer": "https://github.com/jacobbrizinski/kitty",
            "X-Title": "Kitty Gateway",
        },
    ),
    "gemini": ProviderConfig(
        name="gemini",
        route="gemini_direct",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key_env=("GEMINI_API_KEY",),
        model_default="gemini-2.5-flash-image",
        model_env="KITTY_GEMINI_MODEL",
    ),
}

# Fallback order: OpenAI (known-good paid), NVIDIA, AgentRouter (opt-in),
# OpenRouter (cheap/free), Gemini. Matches the order used by the prior 5
# direct functions.
PROVIDER_FALLBACK_ORDER: tuple[str, ...] = (
    "openai",
    "nvidia",
    "agentrouter",
    "openrouter",
    "gemini",
)


def _is_agentrouter_disabled() -> bool:
    return (
        os.environ.get("KITTY_DISABLE_AGENTROUTER", "").strip().lower()
        in ("1", "true", "yes")
    )


@retry_with_backoff
def _call_provider(
    provider: ProviderConfig,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    timeout: int,
    response_format: dict | None = None,
    operation: str = "llm.call",
    metadata: dict[str, Any] | None = None,
    request_model: str | None = None,
) -> str:
    """Generic provider dispatch. The 5 prior direct functions collapse into this."""
    # Reload .env each call so key/model changes take effect without a restart,
    # matching the per-function ``load_dotenv()`` the old direct callers did.
    # ``load_dotenv()`` (no override) is right for the generic providers;
    # AgentRouter's ``key_resolver`` does its own ``load_dotenv(override=True)``.
    load_dotenv()

    if provider.key_resolver is not None:
        api_key = provider.key_resolver()
    else:
        api_key = _resolve_provider_api_key(provider.api_key_env)
    if not api_key:
        return ""

    model = _resolve_provider_model(provider, request_model)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **provider.static_headers,
    }

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format

    if provider.request_mutator is not None:
        payload, headers = provider.request_mutator(payload, headers, request_model)

    url = f"{provider.base_url}/chat/completions"

    try:
        resp = _post(url, headers=headers, json=payload, timeout=timeout)

        if provider.post_processor is not None:
            ctx = {
                "url": url,
                "payload": payload,
                "timeout": timeout,
                "headers": headers,
            }
            new_resp = provider.post_processor(resp, ctx)
            if new_resp is not None:
                resp = new_resp

        if not resp.ok:
            snippet = (resp.text or "")[:900]
            logger.error(
                "%s HTTP %s on POST %s (model=%r): %s",
                provider.name,
                resp.status_code,
                url,
                model,
                snippet,
            )
            return ""

        data = resp.json()
        mlog = data.get("model") or model
        return _finalize_openai_shape_response(
            data,
            provider=provider.name,
            model_logged=str(mlog),
            operation=operation,
            route=provider.route,
            request_model=request_model,
            metadata=metadata,
        )
    except Exception as e:
        logger.error("%s direct call failed: %s", provider.name, e)
        return ""


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
    Tries LiteLLM proxy first; on failure walks ``PROVIDER_FALLBACK_ORDER``.
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

        resp = _post(
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
        logger.warning(
            "LLM call failed via LiteLLM (%s), trying fallbacks: %s", model, e
        )

        for provider_name in PROVIDER_FALLBACK_ORDER:
            if provider_name == "agentrouter" and _is_agentrouter_disabled():
                continue
            out = _call_provider(
                PROVIDERS[provider_name],
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


def chat(
    model: str, messages: list[dict], max_tokens: int = 500, temperature: float = 0.7
) -> str:
    from gateway.observability import record_chat

    with record_chat(model, operation="llm.chat") as _call:
        return call_llm(
            messages, model=model, max_tokens=max_tokens, temperature=temperature
        )


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

_LITELLM_SONNET = "kitty-sonnet"


def route_model(message: str) -> str:
    """Route to Sonnet for reasoning/review requests; DeepSeek Flash for everything else."""
    lower = message.lower()
    if any(t in lower for t in _BEST_TRIGGERS):
        logger.debug("routing: best-trigger -> %s", _LITELLM_SONNET)
        return _LITELLM_SONNET
    if any(kw in lower for kw in _REASONING_KEYWORDS):
        logger.debug("routing: reasoning keyword -> %s", _LITELLM_SONNET)
        return _LITELLM_SONNET
    logger.debug("routing: default -> %s", _LITELLM_DEFAULT)
    return _LITELLM_DEFAULT


# --- Async HTTP chat (gateway /v1/chat/completions) ---


def extract_assistant_text(data: object) -> str:
    """Return the first assistant message content from a LiteLLM-style response."""
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices", [])
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    return content if isinstance(content, str) else ""


async def chat_completions_non_stream(payload: dict[str, Any]) -> dict[str, Any]:
    """Async chat completion — LiteLLM first, sync fallback chain on failure."""
    import asyncio

    from gateway.http_client import get_http_client

    try:
        client = await get_http_client()
        resp = await client.post(
            f"{LITELLM_BASE}/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
        )
        resp.raise_for_status()
        data = resp.json()
        usage = normalize_usage_payload(
            data.get("usage") if isinstance(data, dict) else None
        )
        if usage:
            log_llm_usage(
                "litellm",
                str(data.get("model") or payload.get("model") or "unknown"),
                "chat.completions.create",
                usage,
                {
                    "route": "gateway_chat_nonstream",
                    "request_model": payload.get("model"),
                },
            )
        return data
    except Exception as e:
        logger.warning("Async LiteLLM chat failed (%s), using sync fallback", e)

    messages = payload.get("messages") or []
    model = normalize_litellm_request_model(payload.get("model"))
    text = await asyncio.to_thread(
        call_llm,
        messages,
        model=model,
        max_tokens=int(payload.get("max_tokens") or 1500),
        temperature=float(payload.get("temperature") or 0.7),
        operation="chat.completions.create",
        metadata={
            "route": "gateway_chat_fallback",
            "request_model": payload.get("model"),
        },
    )
    resolved_model = model or _LITELLM_DEFAULT
    return {
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "model": resolved_model,
    }


async def iter_chat_completions_stream(payload: dict[str, Any]):
    """Stream SSE chunks from LiteLLM. Streaming does not use the fallback chain."""
    import json

    from gateway.http_client import get_http_client

    client = await get_http_client()
    async with client.stream(
        "POST",
        f"{LITELLM_BASE}/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {LITELLM_KEY}"},
    ) as resp:
        async for chunk in resp.aiter_lines():
            if not chunk or not chunk.startswith("data: "):
                continue
            raw_data = chunk[6:].strip()
            if raw_data == "[DONE]":
                yield chunk.encode("utf-8") + b"\n\n"
                break
            yield chunk.encode("utf-8") + b"\n\n"


def log_chat_trace(
    log_file,
    correlation_id: str,
    user_text: str,
    domain: str,
    model: str,
    t_start: float,
) -> None:
    import json
    import time

    log_file.parent.mkdir(parents=True, exist_ok=True)
    elapsed_ms = round((time.monotonic() - t_start) * 1000, 1)
    entry = {
        "correlation_id": correlation_id,
        "user_request": user_text[:120],
        "domain_classified": domain,
        "model_selected": model,
        "timestamp": time.time(),
        "elapsed_ms": elapsed_ms,
    }
    with log_file.open("a") as f:
        f.write(json.dumps(entry) + "\n")
