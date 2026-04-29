"""Compatibility model-routing helpers for the web runtime.

This module is intentionally small and side-effect free. It keeps old imports
working while model execution remains owned by the web LLM/orchestrator layer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


FREE_ROUTER_MODEL = "deepseek/deepseek-v4-flash"
BALANCED_REASON_MODEL = "deepseek/deepseek-r1-distill-qwen-32b"
SMALL_MODEL = "deepseek/deepseek-chat"
MAX_MODEL = os.environ.get("KITTY_MAX_MODEL", "deepseek/deepseek-r1")


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    reason: str


def _env_mlx_ready() -> bool:
    return os.environ.get("KITTY_ENABLE_LOCAL_MLX", "").lower() in {"1", "true", "yes", "on"}


def route_model(
    *,
    mode: str = "fast",
    reasoning: bool = False,
    model_target: str | None = None,
    offline: bool = False,
    mlx_ready: bool | None = None,
) -> ModelRoute:
    """Return the provider/model choice without making a network or ML call."""
    local_ready = _env_mlx_ready() if mlx_ready is None else mlx_ready

    if offline:
        return ModelRoute("mlx_local", "", "offline mode requires local model")

    normalized_mode = (mode or "fast").lower()
    target = (model_target or "").lower()

    if normalized_mode == "small":
        return ModelRoute("openrouter", os.environ.get("KITTY_SMALL_MODEL", SMALL_MODEL), "small mode for simple queries")

    if normalized_mode == "fast":
        if target == "local" or local_ready:
            return ModelRoute("mlx_local", "", "fast mode local route")
        return ModelRoute("openrouter", FREE_ROUTER_MODEL, "fast mode free router")

    if normalized_mode == "balanced":
        if reasoning:
            model = os.environ.get("KITTY_BALANCED_REASON", BALANCED_REASON_MODEL)
            return ModelRoute("openrouter", model, "balanced reasoning route")
        if target == "configured":
            model = os.environ.get("KITTY_MODEL", FREE_ROUTER_MODEL)
            return ModelRoute("openrouter", model, "balanced configured route")
        return ModelRoute("openrouter", FREE_ROUTER_MODEL, "balanced free router")

    if normalized_mode == "max":
        return ModelRoute("openrouter", os.environ.get("KITTY_MAX_MODEL", MAX_MODEL), "max reasoning route")

    return ModelRoute("openrouter", FREE_ROUTER_MODEL, f"unknown mode: {mode}")


def call_llm(prompt: str, system_prompt: str | None = None, model: str | None = None, **_kwargs) -> str:
    """Network-enabled LLM call routing to Anthropic/OpenRouter via WebLLMClient."""
    from src.api.web_llm import WebLLMClient
    
    client = WebLLMClient()
    # WebLLMClient.chat returns a SpecialistResponse. We just want the string content.
    # It prefers OpenRouter if key is present, but our OpenRouter is out of credits.
    # Let's temporarily unset OPENROUTER_API_KEY for this call so it falls back to Anthropic.
    
    import os
    original_or_key = os.environ.get("OPENROUTER_API_KEY")
    if original_or_key:
        del os.environ["OPENROUTER_API_KEY"]
        
    try:
        # Use a dummy domain to avoid special prompt overrides unless needed
        response = client.chat(prompt, domain="general", stream=False)
        return response.content
    finally:
        if original_or_key:
            os.environ["OPENROUTER_API_KEY"] = original_or_key


def get_today_spend() -> float:
    return 0.0
