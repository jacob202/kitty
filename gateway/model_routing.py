"""Model routing truth — which provider each kitty-* alias actually calls.

The aliases in litellm_config.yaml (kitty-default, kitty-small, …) are an
indirection layer: app code names a *role*, the config names the provider. That
only pays off if the mapping is inspectable. Before this module it wasn't —
/api/models returned bare alias ids, so a dead OpenRouter balance looked
identical to a healthy one from anywhere in the UI.

Public API:
  describe_routing() -> dict
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import yaml

from gateway.paths import ROOT

LITELLM_CONFIG = ROOT / "gateway" / "litellm_config.yaml"

# LiteLLM virtual names (gateway/litellm_config.yaml). Keep the decision names
# here so callers can ask one Module which chat route they are on.
LITELLM_DEFAULT = "kitty-default"
LITELLM_SONNET = "kitty-sonnet"
LITELLM_SMALL = "kitty-small"

LEGACY_MODEL_ALIASES: dict[str, str] = {
    "kitty-agent": LITELLM_DEFAULT,
    "kitty-smart": LITELLM_DEFAULT,
    "kitty-parts": LITELLM_DEFAULT,
    "kitty-fallback-or": LITELLM_SMALL,
    "deepseek/deepseek-chat": LITELLM_DEFAULT,
    "deepseek/deepseek-v4-flash": LITELLM_DEFAULT,
    "google/gemini-2.0-flash-001": LITELLM_DEFAULT,
    "google/gemini-2.0-flash-exp:free": LITELLM_DEFAULT,
    "kitty-default-or": LITELLM_SMALL,
}


@dataclass(frozen=True)
class RouteDecision:
    """One inspectable model-routing decision for chat execution."""

    model: str
    requested_model: str | None
    source: str
    tier: str | None = None
    trigger: str | None = None
    selected_provider: str | None = None
    reason: str = ""

# litellm writes credentials as "os.environ/NAME"; that's the only form Kitty
# uses, and an inline literal key is a misconfiguration worth naming out loud.
_ENV_REF = re.compile(r"^os\.environ/(?P<name>[A-Z0-9_]+)$")


_LOCAL_HOSTS = ("127.0.0.1", "localhost", "0.0.0.0", "::1")


def _split_model(model: str, api_base: Any = None) -> tuple[str, str]:
    """'openrouter/deepseek/deepseek-v4-pro' -> ('openrouter', 'deepseek/deepseek-v4-pro').

    An OpenAI-compatible local server is still spelled ``openai/…`` in litellm,
    so the api_base decides: pointing at this machine means local, whatever the
    prefix claims.
    """
    provider, _, upstream = model.partition("/")
    if not upstream:
        return "unknown", model
    if _is_local_base(api_base):
        return "local", upstream
    return provider, upstream


def normalize_litellm_request_model(request_model: str | None) -> str | None:
    """Map legacy Kitty aliases onto supported LiteLLM virtual routes."""
    if request_model is None:
        return None
    model = request_model.strip()
    if not model:
        return model
    return LEGACY_MODEL_ALIASES.get(model, model)


def resolve_model_for_message(message: str) -> RouteDecision:
    """Classify a message into Kitty's virtual model route."""
    from dotenv import load_dotenv

    from gateway.reasoning import classify_complexity

    classification = classify_complexity(message)
    if classification.tier == "deep":
        load_dotenv()
        override = os.environ.get("KITTY_REASONING_MODEL", "").strip()
        if override:
            return RouteDecision(
                model=override,
                requested_model=None,
                source="complexity_classifier",
                tier=classification.tier,
                trigger=classification.trigger,
                reason="deep tier routed to KITTY_REASONING_MODEL",
            )
        return RouteDecision(
            model=LITELLM_SONNET,
            requested_model=None,
            source="complexity_classifier",
            tier=classification.tier,
            trigger=classification.trigger,
            reason="deep tier routed to kitty-sonnet",
        )
    if classification.tier == "trivial":
        return RouteDecision(
            model=LITELLM_SMALL,
            requested_model=None,
            source="complexity_classifier",
            tier=classification.tier,
            trigger=classification.trigger,
            reason="trivial tier routed to kitty-small",
        )
    return RouteDecision(
        model=LITELLM_DEFAULT,
        requested_model=None,
        source="complexity_classifier",
        tier=classification.tier,
        trigger=classification.trigger,
        reason="standard tier routed to kitty-default",
    )


def resolve_chat_route(
    requested_model: str | None,
    user_text: str,
    *,
    honor_requested_model: bool = True,
    reroute_virtual_models: bool = False,
    normalize_legacy_aliases: bool = True,
) -> RouteDecision:
    """Return the model/provider decision without executing the LLM call.

    ``reroute_virtual_models`` preserves the chat endpoint's existing behaviour:
    third-party explicit model ids are honored, while Kitty virtual ids let Kitty
    reclassify the turn by message complexity.
    """
    raw = requested_model.strip() if isinstance(requested_model, str) else None
    model = normalize_litellm_request_model(raw) if normalize_legacy_aliases else raw
    if model and honor_requested_model and not (reroute_virtual_models and model.startswith("kitty-")):
        return RouteDecision(
            model=model,
            requested_model=raw,
            source="request",
            selected_provider=_selected_provider_label(),
            reason="caller supplied an explicit model",
        )

    decision = resolve_model_for_message(user_text)
    return RouteDecision(
        model=decision.model,
        requested_model=raw,
        source=decision.source,
        tier=decision.tier,
        trigger=decision.trigger,
        selected_provider=_selected_provider_label(),
        reason=decision.reason,
    )


def _selected_provider_label() -> str | None:
    from gateway.provider_prefs import active_provider

    return active_provider()


def _is_local_base(api_base: Any) -> bool:
    if not isinstance(api_base, str) or not api_base:
        return False
    if api_base.startswith("os.environ/"):
        api_base = os.environ.get(api_base.split("/", 1)[1], "")
    return any(host in api_base for host in _LOCAL_HOSTS)


def _describe_key(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw:
        return {"env_var": None, "present": False, "note": "no api_key set in config"}
    match = _ENV_REF.match(raw)
    if not match:
        return {
            "env_var": None,
            "present": True,
            "note": "api_key is a literal in litellm_config.yaml, not an env var",
        }
    name = match.group("name")
    return {"env_var": name, "present": bool(os.environ.get(name)), "note": None}


def describe_routing() -> dict[str, Any]:
    """Alias → provider → upstream model, plus whether the key is even set.

    Never invents a mapping: if the config can't be read, that is the answer.
    """
    if not LITELLM_CONFIG.exists():
        return {
            "config_path": str(LITELLM_CONFIG),
            "readable": False,
            "error": f"litellm config not found at {LITELLM_CONFIG}",
            "routes": [],
            "providers": [],
            "warnings": [],
        }

    try:
        config = yaml.safe_load(LITELLM_CONFIG.read_text()) or {}
    except yaml.YAMLError as exc:
        return {
            "config_path": str(LITELLM_CONFIG),
            "readable": False,
            "error": f"litellm config is not valid YAML: {exc}",
            "routes": [],
            "providers": [],
            "warnings": [],
        }

    fallbacks: dict[str, list[str]] = {}
    for entry in config.get("litellm_settings", {}).get("fallbacks", []) or []:
        if isinstance(entry, dict):
            for alias, targets in entry.items():
                fallbacks[alias] = list(targets or [])

    routes: list[dict[str, Any]] = []
    for entry in config.get("model_list", []) or []:
        alias = entry.get("model_name")
        params = entry.get("litellm_params", {}) or {}
        provider, upstream = _split_model(
            str(params.get("model", "")), params.get("api_base")
        )
        routes.append(
            {
                "alias": alias,
                "provider": provider,
                "upstream_model": upstream,
                "key": _describe_key(params.get("api_key")),
                "fallbacks": fallbacks.get(alias, []),
            }
        )

    providers = sorted({r["provider"] for r in routes})
    warnings = _warnings(routes, providers)

    return {
        "config_path": str(LITELLM_CONFIG),
        "readable": True,
        "error": None,
        "routes": routes,
        "providers": providers,
        "warnings": warnings,
    }


def describe_providers() -> dict[str, Any]:
    """The direct-call fallback chain: order, key state, and what's turned off.

    This is the layer *below* the litellm aliases — where Kitty goes when the
    proxy fails. Switching providers means reordering this, which is why it has
    to be readable and writable from outside Python.
    """
    from gateway.llm_client import (
        PROVIDERS,
        effective_provider_order,
        provider_is_configured,
    )
    from gateway.provider_prefs import load_preferences

    prefs = load_preferences()
    disabled = set(prefs["disabled"])
    active = str(prefs.get("active", "auto"))
    order = effective_provider_order()

    providers = []
    for name, config in PROVIDERS.items():
        configured = provider_is_configured(config)
        providers.append(
            {
                "name": name,
                "base_url": config.base_url,
                "model": config.model_default or None,
                "model_env": config.model_env,
                "api_key_env": list(config.api_key_env),
                "requires_key": config.requires_key,
                "configured": configured,
                "disabled": name in disabled,
                "position": order.index(name) if name in order else None,
                "active": active == name,
                "kind": config.kind,
                "free_tier": config.free_tier,
            }
        )

    providers.sort(key=lambda p: (p["position"] is None, p["position"] or 0, p["name"]))

    usable = [p["name"] for p in providers if p["configured"] and not p["disabled"]]
    free_backups = [
        p["name"] for p in providers if p.get("free_tier") and not p["disabled"]
    ]
    warnings: list[str] = []
    if not usable:
        if free_backups:
            warnings.append(
                "no provider is configured — "
                f"enable a free tier ({', '.join(free_backups)}) to stay online "
                "with zero cost"
            )
        else:
            warnings.append(
                "no provider is both configured and enabled — every LLM call will fail"
            )
    elif usable[:1] != order[:1]:
        warnings.append(
            f"first choice '{order[0]}' has no key, so calls actually start at '{usable[0]}'"
        )

    if active != "auto":
        chosen = next((p for p in providers if p["name"] == active), None)
        if chosen is None or not chosen["configured"] or chosen["disabled"]:
            warnings.append(f"selected provider {active!r} is not ready; chat will fail loudly")

    return {
        "active": active,
        "order": order,
        "providers": providers,
        "warnings": warnings,
        "config_path": str(_prefs_path()),
    }


def _prefs_path():
    from gateway.provider_prefs import PROVIDER_PREFS_FILE

    return PROVIDER_PREFS_FILE


def _warnings(routes: list[dict[str, Any]], providers: list[str]) -> list[str]:
    warnings: list[str] = []

    missing = sorted(
        {r["key"]["env_var"] for r in routes if r["key"]["env_var"] and not r["key"]["present"]}
    )
    for env_var in missing:
        warnings.append(f"{env_var} is not set in the gateway environment — routes using it will fail")

    if len(providers) == 1 and routes:
        warnings.append(
            f"every model route points at '{providers[0]}' — if that account is out of "
            "credit or down, Kitty has nothing to fall back to"
        )

    for route in routes:
        same_provider = [
            f for f in route["fallbacks"]
            if any(o["alias"] == f and o["provider"] == route["provider"] for o in routes)
        ]
        if same_provider:
            warnings.append(
                f"{route['alias']} falls back to {', '.join(same_provider)} on the same "
                f"provider ('{route['provider']}') — a provider-level outage takes out both"
            )

    return warnings
