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
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx
from dotenv import load_dotenv

from gateway import model_routing
from gateway.paths import LITELLM_BASE, LITELLM_KEY
from gateway.settings import get_settings
from gateway.token_usage_log import log_llm_usage, normalize_usage_payload

logger = logging.getLogger("kitty.llm_client")


class ProviderChainExhausted(RuntimeError):
    """Raised when LiteLLM and every fallback provider fail to produce a completion.

    Replaces the previous silent ``return ""`` so callers see the failure instead
    of downstream code interpreting an empty string as a real answer.
    """

    code = "llm.chain_exhausted"

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        summary = "; ".join(errors) if errors else "no diagnostics"
        super().__init__(f"LLM provider chain exhausted: {summary}")


# Cap how long a single provider may spend establishing a connection, and bound
# the total wall-clock time the whole fallback chain may burn. Without these, six
# providers each hanging ~60s could stall a call for minutes.
_chain_settings = get_settings()
_PROVIDER_CONNECT_TIMEOUT = _chain_settings.KITTY_PROVIDER_CONNECT_TIMEOUT
_LLM_CHAIN_DEADLINE = _chain_settings.KITTY_LLM_CHAIN_DEADLINE

# Optional tenacity retry on transient network and upstream server errors.
# 4xx errors (auth, bad model) return immediately so provider-specific handling
# or the fallback chain can take over.
try:
    from tenacity import (
        retry as _tenacity_retry,
    )
    from tenacity import (
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
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

    def _retry_post(fn):
        return fn


@_retry_post
def _post(*args, **kwargs):
    """POST once via ``httpx``, retrying only transport failures and HTTP 5xx responses."""
    # Split a scalar timeout into (connect, read) so a dead host can't burn the
    # full read budget just connecting. httpx.Timeout accepts connect/read separately.
    timeout = kwargs.get("timeout")
    if isinstance(timeout, (int, float)):
        kwargs["timeout"] = httpx.Timeout(timeout, connect=min(_PROVIDER_CONNECT_TIMEOUT, timeout))
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
_LITELLM_SONNET = "kitty-sonnet"
_LITELLM_SMALL = "kitty-small"


def _env_slug(name: str, default: str) -> str:
    load_dotenv()
    v = os.environ.get(name, "").strip()
    return v if v else default

# Kept in step with gateway/litellm_config.yaml. The direct-provider chain runs
# when LiteLLM is unreachable; a route missing here would be sent to OpenRouter
# verbatim as "kitty-think", which is not a model id anywhere.
_LITELLM_TO_OPENROUTER: dict[str, str] = {
    _LITELLM_DEFAULT: "openrouter/deepseek/deepseek-v4-pro",
    "kitty-default-or": "openrouter/deepseek/deepseek-v4-flash",
    "kitty-sonnet": "openrouter/deepseek/deepseek-v4-pro",
    "kitty-small": "openrouter/deepseek/deepseek-v4-flash",
    "kitty-think": "openrouter/qwen/qwen3-235b-a22b-thinking-2507",
    "kitty-code": "openrouter/qwen/qwen3-coder",
    "kitty-vision": "openrouter/mistralai/mistral-small-3.2-24b-instruct",
}


def normalize_litellm_request_model(request_model: str | None) -> str | None:
    """Map legacy Kitty aliases onto supported LiteLLM virtual routes."""
    return model_routing.normalize_litellm_request_model(request_model)


def normalize_agentrouter_api_base(raw: str | None) -> str:
    """Return base URL with ``/v1`` suffix, no trailing slash (OpenAI-compatible)."""
    base = (raw or "https://agentrouter.org/v1").strip().rstrip("/")
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


def resolve_agentrouter_api_key() -> str:
    """Read API key from env; supports AgentRouter doc names. Strips quotes and first line only."""
    load_dotenv(override=True)
    for env_name in ("AGENT_ROUTER_TOKEN", "AGENTROUTER_API_KEY"):
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
    if rm and rm not in model_routing.LEGACY_MODEL_ALIASES and rm != _LITELLM_DEFAULT:
        return _sanitize_agentrouter_model_id(rm)

    g_model = os.environ.get("AGENTROUTER_MODEL", "").strip() or "gpt-5.5"
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
        content = data["choices"][0]["message"]["content"]
        text = content.strip() if isinstance(content, str) else ""
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
    # A local server has no key to check. Without this the generic dispatch
    # treats "no key" as "not configured" and skips it.
    requires_key: bool = True
    # How the user pays for this provider. Drives the Settings UI badge.
    kind: str = "api_credit"  # "local" | "api_credit" | "subscription"
    # Whether the provider has a usable free tier (e.g. OpenRouter free models,
    # Gemini flash, local MLX). Shown as a safety-net badge in Settings.
    free_tier: bool = False
    # Optional overrides for providers whose key/model resolution needs special
    # handling (e.g. AgentRouter's multi-line .env guard). When None, the
    # generic resolver is used.
    key_resolver: Callable[[], str] | None = None
    model_resolver: Callable[[str | None], str] | None = None
    request_mutator: Callable[[dict, dict, str | None], tuple[dict, dict]] | None = None
    post_processor: Callable[[httpx.Response, dict], httpx.Response] | None = None


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


def _resolve_provider_model(provider: ProviderConfig, request_model: str | None) -> str:
    """Pick the upstream model id. ``model_resolver`` wins over env/default."""
    if provider.model_resolver is not None:
        return provider.model_resolver(request_model)
    if provider.model_env:
        env_val = os.environ.get(provider.model_env, "").strip()
        if env_val:
            return env_val
    return provider.model_default


PROVIDERS: dict[str, ProviderConfig] = {
    # gateway/start_mlx.sh has always been able to serve a model on the Mac, but
    # nothing in the routing layer pointed at it — so every "hi" paid cloud
    # latency (and cloud credit) for work a 4-bit local model handles instantly.
    "local": ProviderConfig(
        name="local",
        route="local_mlx",
        base_url=os.environ.get("MLX_BASE_URL", "http://127.0.0.1:8010/v1"),
        model_default="mlx-community/Qwen3.5-4B-4bit",
        model_env="MLX_MODEL",
        requires_key=False,
        kind="local",
        free_tier=True,
    ),
    "openai": ProviderConfig(
        name="openai",
        route="openai_direct",
        base_url="https://api.openai.com/v1",
        api_key_env=("OPENAI_API_KEY",),
        model_default="gpt-4o-mini",
        model_env="KITTY_OPENAI_FALLBACK_MODEL",
        kind="subscription",
    ),
    "nvidia": ProviderConfig(
        name="nvidia",
        route="nvidia_direct",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key_env=("NVIDIA_API_KEY",),
        model_default="deepseek-ai/deepseek-v4-pro",
        model_env="NVIDIA_CHAT_MODEL",
        kind="api_credit",
        free_tier=True,
    ),
    "agentrouter": ProviderConfig(
        name="agentrouter",
        route="agentrouter_direct",
        base_url=normalize_agentrouter_api_base(
            os.environ.get("AGENTROUTER_API_BASE", "https://agentrouter.org/v1")
        ),
        api_key_env=("AGENT_ROUTER_TOKEN", "AGENTROUTER_API_KEY"),
        model_default="gpt-5.5",
        kind="api_credit",
        # Standard OpenAI-compatible Bearer authentication. AGENT_ROUTER_TOKEN
        # is canonical; AGENTROUTER_API_KEY remains a legacy Kitty alias.
        key_resolver=resolve_agentrouter_api_key,
        model_resolver=lambda request_model: agentrouter_model_for_request(request_model),
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        route="openrouter_direct",
        base_url=OPENROUTER_BASE,
        api_key_env=("OPENROUTER_API_KEY",),
        model_default="",
        kind="api_credit",
        free_tier=True,
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
        kind="api_credit",
        free_tier=True,
    ),
}

# Default order when Jacob hasn't set one: local first (free, no credit, no
# network), then OpenAI (known-good paid), NVIDIA, AgentRouter (opt-in),
# OpenRouter (cheap/free), Gemini.
PROVIDER_FALLBACK_ORDER: tuple[str, ...] = (
    "local",
    "openai",
    "nvidia",
    "agentrouter",
    "openrouter",
    "gemini",
)


def provider_is_configured(provider: ProviderConfig) -> bool:
    """Whether this provider has what it needs to be worth calling.

    Checked before dispatch so an unkeyed provider costs nothing instead of a
    connect timeout. With an empty OPENROUTER_API_KEY the chain used to burn its
    whole deadline discovering, one timeout at a time, that nobody was home.
    """
    if not provider.requires_key:
        return True
    if provider.key_resolver is not None:
        return bool(provider.key_resolver())
    return bool(_resolve_provider_api_key(provider.api_key_env))


def effective_provider_order() -> list[str]:
    """The try-order after applying Jacob's saved preference."""
    from gateway.provider_prefs import resolve_order

    return resolve_order(tuple(PROVIDERS.keys()), PROVIDER_FALLBACK_ORDER)


def _is_agentrouter_disabled() -> bool:
    return os.environ.get("KITTY_DISABLE_AGENTROUTER", "").strip().lower() in ("1", "true", "yes")


def retry_with_backoff(
    func, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 10.0
):
    """Retry on 429 rate-limit errors with exponential backoff. All other errors re-raise immediately."""

    def wrapper(*args, **kwargs):
        retries = 0
        while True:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                resp = getattr(e, "response", None)
                is_429 = (
                    resp is not None and getattr(resp, "status_code", None) == 429
                ) or "429" in str(e)
                if is_429 and retries < max_retries:
                    delay = min(base_delay * (2**retries), max_delay)
                    logger.warning(
                        "LLM rate limit (429). Retrying in %.1fs (attempt %d/%d)...",
                        delay,
                        retries + 1,
                        max_retries,
                    )
                    time.sleep(delay)
                    retries += 1
                else:
                    raise

    return wrapper


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
    if not api_key and provider.requires_key:
        return ""

    model = _resolve_provider_model(provider, request_model)

    headers = {
        "Content-Type": "application/json",
        **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
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

        if not resp.is_success:
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


def selected_provider_name() -> str | None:
    """Return Jacob's exact provider selection, or None for automatic routing."""
    from gateway.provider_prefs import active_provider, is_disabled

    name = active_provider()
    if name is None:
        return None
    if name not in PROVIDERS:
        raise ProviderChainExhausted([f"selected provider {name!r} is unknown"])
    if is_disabled(name):
        raise ProviderChainExhausted([f"selected provider {name!r} is disabled"])
    if name == "agentrouter" and _is_agentrouter_disabled():
        raise ProviderChainExhausted(["selected provider 'agentrouter' is disabled by environment"])
    if not provider_is_configured(PROVIDERS[name]):
        raise ProviderChainExhausted([f"selected provider {name!r} is not configured"])
    return name


def call_selected_provider(
    provider_name: str,
    messages: list[dict],
    *,
    request_model: str | None,
    max_tokens: int,
    temperature: float,
    timeout: int,
    response_format: dict[str, Any] | None = None,
    operation: str = "llm.call",
    metadata: dict[str, Any] | None = None,
) -> str:
    """Call exactly one provider. Explicit selection never silently falls elsewhere."""
    out = _call_provider(
        PROVIDERS[provider_name],
        messages,
        max_tokens,
        temperature,
        timeout,
        response_format,
        operation=operation,
        metadata=metadata,
        request_model=request_model,
    )
    if not out:
        raise ProviderChainExhausted([f"selected provider {provider_name!r} returned no response"])
    return out


def call_llm(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 1500,
    temperature: float = 0.7,
    timeout: int = 60,
    response_format: dict[str, Any] | None = None,
    operation: str = "llm.call",
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Centralized hub for all LLM calls.
    Tries LiteLLM proxy first; on failure walks ``effective_provider_order()``.

    Every call may reach a cloud provider. ADR 0022 retired the D10 local-only
    boundary; there is no content class that this function keeps on the Mac.
    """
    if model is None:
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break
        model = route_model(user_msg)

    model = normalize_litellm_request_model(model) or route_model("")

    selected = selected_provider_name()
    if selected is not None:
        return call_selected_provider(
            selected,
            messages,
            request_model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            response_format=response_format,
            operation=operation,
            metadata=metadata,
        )

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
        logger.warning("LLM call failed via LiteLLM (%s), trying fallbacks: %s", model, e)
        errors: list[str] = [f"litellm: {e}"]

        deadline = time.monotonic() + _LLM_CHAIN_DEADLINE

        def _budget_timeout() -> int | None:
            """Remaining budget clamped to the per-call timeout; None if exhausted."""
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            return min(int(remaining), timeout)

        for provider_name in effective_provider_order():
            if provider_name == "agentrouter" and _is_agentrouter_disabled():
                errors.append(f"{provider_name}: disabled")
                continue
            if not provider_is_configured(PROVIDERS[provider_name]):
                errors.append(f"{provider_name}: no api key configured")
                continue
            _at = _budget_timeout()
            if _at is None:
                logger.error(
                    "LLM fallback chain exceeded %.0fs deadline; giving up",
                    _LLM_CHAIN_DEADLINE,
                )
                errors.append(f"chain: deadline {_LLM_CHAIN_DEADLINE}s exceeded")
                raise ProviderChainExhausted(errors)
            out = _call_provider(
                PROVIDERS[provider_name],
                messages,
                max_tokens,
                temperature,
                _at,
                response_format,
                operation=operation,
                metadata=metadata,
                request_model=model,
            )
            if out:
                return out
            errors.append(f"{provider_name}: no response")

        raise ProviderChainExhausted(errors)


def chat(model: str, messages: list[dict], max_tokens: int = 500, temperature: float = 0.7) -> str:
    from gateway.observability import record_chat

    with record_chat(model, operation="llm.chat") as _call:
        return call_llm(messages, model=model, max_tokens=max_tokens, temperature=temperature)


def route_model(message: str) -> str:
    """Compatibility wrapper for callers that only need the selected model id."""
    decision = model_routing.resolve_model_for_message(message)
    logger.debug(
        "routing: %s -> %s (trigger: %s)",
        decision.tier or decision.source,
        decision.model,
        decision.trigger,
    )
    return decision.model


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
    """Async chat completion with exact-provider selection or automatic routing."""
    import asyncio

    selected = selected_provider_name()
    if selected is not None:
        messages = payload.get("messages") or []
        request_model = normalize_litellm_request_model(payload.get("model")) or route_model("")
        text = await asyncio.to_thread(
            call_selected_provider,
            selected,
            messages,
            request_model=request_model,
            max_tokens=int(payload.get("max_tokens") or 1500),
            temperature=float(payload.get("temperature") or 0.7),
            timeout=int(payload.get("timeout") or 60),
            response_format=payload.get("response_format"),
            operation="chat.completions.create",
            metadata={"route": "gateway_chat_selected_provider"},
        )
        return {
            "choices": [{"message": {"role": "assistant", "content": text}}],
            "model": selected,
        }

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
        usage = normalize_usage_payload(data.get("usage") if isinstance(data, dict) else None)
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
    model = normalize_litellm_request_model(payload.get("model")) or route_model("")
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


def _raise_upstream_status(resp, ChatErrorKind, ChatTurnError) -> None:
    """Turn a non-2xx LiteLLM stream response into a typed ChatTurnError.

    The message is kept as detail only (it often names providers/credits); the
    user-facing copy is chosen by the error kind so it never leaks API detail.
    """
    payload_detail = ""
    try:
        payload = resp.json()
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict):
                payload_detail = str(err.get("message") or err.get("type") or "")
            elif isinstance(payload.get("detail"), str):
                payload_detail = payload["detail"]
    except Exception:  # noqa: BLE001 — non-JSON upstream body; keep status only
        payload_detail = f"(non-JSON body, {len(resp.content or b'')} bytes)"
    status = int(getattr(resp, "status_code", 0) or 0)
    kind = ChatErrorKind.ROUTING if 400 <= status < 500 else ChatErrorKind.UPSTREAM
    detail = f"LiteLLM stream returned HTTP {status}"
    if payload_detail:
        detail += f": {payload_detail[:300]}"
    raise ChatTurnError(kind=kind, detail=detail)


async def iter_chat_completions_stream(payload: dict[str, Any]):
    """Stream from LiteLLM, or emit an exact selected-provider response as SSE.

    Any failure to get a provider-answer surfaces as a ``ChatTurnError`` so the
    route can emit a user-facing error event instead of an empty/half stream
    that the phone renders as opaque "stream closed without [DONE]" copy.
    """
    from gateway.chat_errors import ChatErrorKind, ChatTurnError

    selected = selected_provider_name()
    try:
        if selected is not None:
            import asyncio

            messages = payload.get("messages") or []
            request_model = normalize_litellm_request_model(payload.get("model")) or route_model("")
            try:
                text = await asyncio.to_thread(
                    call_selected_provider,
                    selected,
                    messages,
                    request_model=request_model,
                    max_tokens=int(payload.get("max_tokens") or 1500),
                    temperature=float(payload.get("temperature") or 0.7),
                    timeout=int(payload.get("timeout") or 60),
                    response_format=payload.get("response_format"),
                    operation="chat.completions.create",
                    metadata={"route": "gateway_chat_selected_provider"},
                )
            except ProviderChainExhausted as exc:
                raise ChatTurnError(
                    kind=ChatErrorKind.ROUTING,
                    detail=f"selected provider {selected!r} could not answer: {exc}",
                ) from exc
            direct_chunk = {
                "id": "chatcmpl-kitty-selected-provider",
                "object": "chat.completion.chunk",
                "model": selected,
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}],
            }
            yield b"data: " + json.dumps(direct_chunk).encode("utf-8") + b"\n\n"
            yield b"data: [DONE]\n\n"
            return

        from gateway.http_client import get_http_client

        client = await get_http_client()
        async with client.stream(
            "POST",
            f"{LITELLM_BASE}/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
        ) as resp:
            if not (200 <= resp.status_code < 300):
                _raise_upstream_status(resp, ChatErrorKind, ChatTurnError)
            async for chunk in resp.aiter_lines():
                if not chunk or not chunk.startswith("data: "):
                    continue
                raw_data = chunk[6:].strip()
                if raw_data == "[DONE]":
                    yield chunk.encode("utf-8") + b"\n\n"
                    break
                yield chunk.encode("utf-8") + b"\n\n"
    except ChatTurnError:
        raise
    except httpx.HTTPError as exc:
        raise ChatTurnError.from_exception(
            exc,
            kind=ChatErrorKind.UPSTREAM,
            detail=f"LiteLLM chat stream failed: {exc}",
        ) from exc
    except Exception as exc:  # noqa: BLE001 — surfaced verbatim to the route
        raise ChatTurnError.from_exception(
            exc,
            kind=ChatErrorKind.UPSTREAM,
            detail=f"chat stream failed: {exc}",
        ) from exc


def log_chat_trace(
    log_file,
    correlation_id: str,
    user_text: str,
    domain: str,
    model: str,
    t_start: float,
    *,
    runtime_revision: str | None = None,
    model_resolved: str | None = None,
    tier: str | None = None,
    trigger: str | None = None,
    cap_hit: bool | None = None,
    escalation: bool | None = None,
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
    if runtime_revision:
        entry["runtime_manifest_revision"] = runtime_revision
    if model_resolved:
        entry["model_resolved"] = model_resolved
    if tier is not None:
        entry["tier"] = tier
    if trigger is not None:
        entry["trigger"] = trigger
    if cap_hit is not None:
        entry["cap_hit"] = cap_hit
    if escalation is not None:
        entry["escalation"] = escalation
    with log_file.open("a") as f:
        f.write(json.dumps(entry) + "\n")
