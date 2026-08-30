"""Active chat-provider inspection and switching.

The streaming chat path goes through LiteLLM only (no provider fallback
chain), so "which provider is Kitty using" is a property of
``gateway/litellm_config.yaml``. These routes read that file to report the
active upstream and rewrite it to switch upstreams, then restart the
launchd-managed LiteLLM service so the change takes effect.

Switching is deliberately all-or-nothing across the four kitty-* models —
a partial rewrite would leave the router in a state nobody designed for.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException

from gateway.paths import ROOT

_AGENTROUTER_DEFAULT_USER_AGENT = "kitty-gateway/1.0"
_AGENTROUTER_DEFAULT_ORIGINATOR = "kitty"
_AGENTROUTER_DEFAULT_VERSION = "1.0"

router = APIRouter(tags=["providers"])

CONFIG_PATH = ROOT / "gateway" / "litellm_config.yaml"
LITELLM_HEALTH_URL = "http://127.0.0.1:8001/health/liveliness"
LITELLM_LAUNCHD_LABEL = "com.kitty.litellm"

_KITTY_MODELS = ("kitty-default", "kitty-sonnet", "kitty-small", "kitty-vision")

# Upstream model per kitty alias per provider. Keep in sync with what each
# provider actually serves (AgentRouter live list verified 2026-07-27).
_UPSTREAMS: dict[str, dict[str, Any]] = {
    "agentrouter": {
        "api_key_env": "AGENTROUTER_API_KEY",
        "api_base": "https://agentrouter.org/v1",
        "extra_headers": {
            "User-Agent": _AGENTROUTER_DEFAULT_USER_AGENT,
            "Originator": _AGENTROUTER_DEFAULT_ORIGINATOR,
            "Version": _AGENTROUTER_DEFAULT_VERSION,
        },
        "models": {
            "kitty-default": "openai/gpt-5.5",
            "kitty-sonnet": "openai/claude-opus-4-8",
            "kitty-small": "openai/glm-5.2",
            "kitty-vision": "openai/glm-5.2",
        },
    },
    "openrouter": {
        "api_key_env": "OPENROUTER_API_KEY",
        "api_base": None,
        "extra_headers": None,
        "models": {
            "kitty-default": "openrouter/deepseek/deepseek-v4-pro",
            "kitty-sonnet": "openrouter/deepseek/deepseek-v4-pro",
            "kitty-small": "openrouter/deepseek/deepseek-v4-flash",
            "kitty-vision": "openrouter/mistral/mistral-small-latest",
        },
    },
}


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"LiteLLM config missing at {CONFIG_PATH}",
        )
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"LiteLLM config at {CONFIG_PATH} is not valid YAML: {exc}",
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("model_list"), list):
        raise HTTPException(
            status_code=500,
            detail=f"LiteLLM config at {CONFIG_PATH} has no model_list",
        )
    return data


def _classify_upstream(params: dict[str, Any]) -> str:
    api_base = str(params.get("api_base") or "")
    model = str(params.get("model") or "")
    if "agentrouter.org" in api_base:
        return "agentrouter"
    if model.startswith("openrouter/"):
        return "openrouter"
    return "other"


def _active_state() -> dict[str, Any]:
    config = _load_config()
    models: list[dict[str, str]] = []
    for entry in config["model_list"]:
        if not isinstance(entry, dict):
            continue
        name = entry.get("model_name")
        params = entry.get("litellm_params")
        if name not in _KITTY_MODELS or not isinstance(params, dict):
            continue
        models.append(
            {
                "name": name,
                "upstream": _classify_upstream(params),
                "model": str(params.get("model") or ""),
            }
        )
    upstreams = {m["upstream"] for m in models}
    if len(upstreams) == 1:
        active = upstreams.pop()
    elif not upstreams:
        active = "unknown"
    else:
        active = "mixed"
    return {"active": active, "models": models}


def _rewrite_config(target: str) -> None:
    upstream = _UPSTREAMS[target]
    config = _load_config()
    seen: set[str] = set()
    for entry in config["model_list"]:
        if not isinstance(entry, dict):
            continue
        name = entry.get("model_name")
        if name not in _KITTY_MODELS:
            continue
        params = entry.get("litellm_params")
        if not isinstance(params, dict):
            raise HTTPException(
                status_code=500,
                detail=f"model_list entry {name!r} has no litellm_params",
            )
        seen.add(name)
        params["model"] = upstream["models"][name]
        params["api_key"] = f"os.environ/{upstream['api_key_env']}"
        if upstream["api_base"]:
            params["api_base"] = upstream["api_base"]
        else:
            params.pop("api_base", None)
        if upstream["extra_headers"]:
            params["extra_headers"] = dict(upstream["extra_headers"])
        else:
            params.pop("extra_headers", None)
    missing = set(_KITTY_MODELS) - seen
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"LiteLLM config is missing kitty models: {sorted(missing)}",
        )

    header = (
        "# LiteLLM — Kitty model surface\n"
        "#\n"
        f"# Rewritten by POST /api/providers/switch at {time.strftime('%Y-%m-%d %H:%M:%S')} "
        f"— active upstream: {target}.\n"
        "# Edit by hand or via Settings → Providers in the UI.\n"
    )
    body = yaml.safe_dump(config, sort_keys=False, default_flow_style=False)
    try:
        CONFIG_PATH.write_text(header + body, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not write {CONFIG_PATH}: {exc}",
        ) from exc


def _restart_litellm() -> None:
    """Kick the launchd service and wait for liveliness. Fail loud on trouble."""
    domain = f"gui/{os.getuid()}/{LITELLM_LAUNCHD_LABEL}"
    try:
        proc = subprocess.run(
            ["launchctl", "kickstart", "-k", domain],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not restart LiteLLM via launchctl: {exc}",
        ) from exc
    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=(
                f"launchctl kickstart {domain} exited {proc.returncode}: "
                f"{proc.stderr.strip() or proc.stdout.strip()}"
            ),
        )

    import urllib.request

    deadline = time.monotonic() + 20
    last_error = "no attempt made"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(LITELLM_HEALTH_URL, timeout=3) as resp:
                if resp.status == 200:
                    return
            last_error = f"HTTP {resp.status}"
        except Exception as exc:  # noqa: BLE001 — surfaced verbatim below
            last_error = str(exc)
        time.sleep(1)
    raise HTTPException(
        status_code=500,
        detail=(
            "LiteLLM restarted but did not become healthy within 20s "
            f"(last error: {last_error}). Check logs/litellm.log."
        ),
    )


@router.get("/api/providers/active")
async def get_active_provider() -> dict[str, Any]:
    """Report which upstream each kitty-* model routes to."""
    return _active_state()


@router.post("/api/providers/switch")
async def switch_provider(payload: dict[str, Any]) -> dict[str, Any]:
    """Point all kitty-* models at one upstream and restart LiteLLM."""
    target = payload.get("target")
    if target not in _UPSTREAMS:
        raise HTTPException(
            status_code=400,
            detail=f"target must be one of {sorted(_UPSTREAMS)}, got {target!r}",
        )
    current = _active_state()
    if current["active"] == target:
        return {"switched": False, **current}
    _rewrite_config(target)
    _restart_litellm()
    return {"switched": True, **_active_state()}
