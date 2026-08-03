"""Runtime guards for OpenAI-compatible chat clients such as Open WebUI.

These guards sit at Kitty's HTTP boundary. They preserve the domain and modality
signals that generic OpenAI clients cannot express through a model id, and they
normalize LiteLLM-only provider prefixes before the direct fallback path uses
OpenRouter's native API.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from typing import Any

from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from gateway.domain_router import classify_domain
from gateway.model_routing import (
    AUTO_ROUTED_MODELS,
    LITELLM_SONNET,
    LITELLM_VISION,
    normalize_litellm_request_model,
)
from gateway.reasoning import classify_complexity

_CHAT_PATHS = frozenset({"/v1/chat/completions", "/api/chat/completions"})
_IMAGE_PART_TYPES = frozenset({"image", "image_url", "input_image"})


def _strip_openrouter_prefix(model: str) -> str:
    return model.removeprefix("openrouter/")


def normalize_direct_openrouter_models() -> None:
    """Make every direct OpenRouter resolver return native provider/model ids."""
    from gateway import llm_client

    for alias, model in tuple(llm_client._LITELLM_TO_OPENROUTER.items()):
        llm_client._LITELLM_TO_OPENROUTER[alias] = _strip_openrouter_prefix(model)

    provider = llm_client.PROVIDERS.get("openrouter")
    if provider is None or provider.model_resolver is None:
        return
    resolver = provider.model_resolver
    if getattr(resolver, "_kitty_native_openrouter_ids", False):
        return

    def native_resolver(request_model: str | None) -> str:
        return _strip_openrouter_prefix(resolver(request_model))

    native_resolver._kitty_native_openrouter_ids = True  # type: ignore[attr-defined]
    llm_client.PROVIDERS["openrouter"] = replace(
        provider,
        model_resolver=native_resolver,
    )


def _last_user_content(messages: object) -> object:
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            return message.get("content", "")
    return ""


def _text_from_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        part["text"]
        for part in content
        if isinstance(part, dict)
        and part.get("type") == "text"
        and isinstance(part.get("text"), str)
    )


def _contains_image(content: object) -> bool:
    if not isinstance(content, list):
        return False
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = str(part.get("type") or "").lower()
        if part_type in _IMAGE_PART_TYPES or part_type.startswith("image_"):
            return True
    return False


def auto_route_override(payload: dict[str, Any]) -> str | None:
    """Return an explicit route only when Auto would otherwise lose a signal."""
    requested = payload.get("model", "kitty-default")
    normalized = normalize_litellm_request_model(
        requested if isinstance(requested, str) else None
    )
    if normalized not in AUTO_ROUTED_MODELS:
        return None

    content = _last_user_content(payload.get("messages"))
    if _contains_image(content):
        return LITELLM_VISION

    user_text = _text_from_content(content)
    domain = classify_domain(user_text)
    domain_aware = classify_complexity(user_text, domain=domain)
    domain_blind = classify_complexity(user_text)
    if domain_aware.tier == "deep" and domain_blind.tier != "deep":
        return os.environ.get("KITTY_REASONING_MODEL", "").strip() or LITELLM_SONNET
    return None


class OpenWebUIRoutingMiddleware:
    """Rewrite only Auto requests whose domain or image signal would be lost."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") not in _CHAT_PATHS
        ):
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                await self.app(scope, _single_message_receive(message), send)
                return
            if message["type"] != "http.request":
                continue
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break

        raw_body = b"".join(chunks)
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            await self.app(scope, _body_receive(raw_body), send)
            return
        if not isinstance(payload, dict):
            await self.app(scope, _body_receive(raw_body), send)
            return

        override = auto_route_override(payload)
        if override is None:
            await self.app(scope, _body_receive(raw_body), send)
            return

        payload["model"] = override
        rewritten = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        rewritten_scope = dict(scope)
        headers = [
            (key, value)
            for key, value in scope.get("headers", [])
            if key.lower() != b"content-length"
        ]
        headers.append((b"content-length", str(len(rewritten)).encode("ascii")))
        rewritten_scope["headers"] = headers
        await self.app(rewritten_scope, _body_receive(rewritten), send)


def _body_receive(body: bytes) -> Receive:
    sent = False

    async def receive() -> Message:
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


def _single_message_receive(message: Message) -> Receive:
    sent = False

    async def receive() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return message
        return {"type": "http.disconnect"}

    return receive


def install_openwebui_routing_guards(app: FastAPI) -> None:
    normalize_direct_openrouter_models()
    app.add_middleware(OpenWebUIRoutingMiddleware)
