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
from typing import Any

import yaml

from gateway.paths import ROOT

LITELLM_CONFIG = ROOT / "gateway" / "litellm_config.yaml"

# litellm writes credentials as "os.environ/NAME"; that's the only form Kitty
# uses, and an inline literal key is a misconfiguration worth naming out loud.
_ENV_REF = re.compile(r"^os\.environ/(?P<name>[A-Z0-9_]+)$")


def _split_model(model: str) -> tuple[str, str]:
    """'openrouter/deepseek/deepseek-v4-pro' -> ('openrouter', 'deepseek/deepseek-v4-pro')."""
    provider, _, upstream = model.partition("/")
    if not upstream:
        return "unknown", model
    return provider, upstream


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
        provider, upstream = _split_model(str(params.get("model", "")))
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
