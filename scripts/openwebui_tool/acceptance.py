from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .common import (
    DEFAULT_AGENT,
    Failure,
    HOST,
    PINNED_AGENTS,
    PORT,
    gateway_config,
    open_local,
    request_json,
    runtime_env,
)
from .service import AGENTS, claim_system_admin

USER_FACING_MODEL_IDS = (
    "kitty-auto",
    "kitty-fast",
    "kitty-think",
    "kitty-code",
    "kitty-vision",
)
EXPECTED_TOOL_OPERATIONS = frozenset(
    {
        "search_memory",
        "remember",
        "search_notes",
        "list_projects",
        "project_next_step",
        "calendar_today",
        "ask_tutor",
        "builder_status",
    }
)


def _model_ids(payload: object) -> set[str]:
    rows: object = payload
    if isinstance(payload, dict):
        rows = payload.get("data", payload.get("models", []))
    if not isinstance(rows, list):
        return set()
    return {
        str(row.get("id"))
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }


def _operation_ids(spec: object) -> set[str]:
    if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
        return set()
    found: set[str] = set()
    for methods in spec["paths"].values():
        if not isinstance(methods, dict):
            continue
        for operation in methods.values():
            if isinstance(operation, dict) and isinstance(operation.get("operationId"), str):
                found.add(operation["operationId"])
    return found


def _post_json(url: str, *, auth: str, body: dict[str, Any], timeout: float) -> dict:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with open_local(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise Failure(f"{url} returned HTTP {exc.code}: {detail[:500]}") from exc
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise Failure(f"cannot call {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise Failure(f"{url} returned a non-object JSON response")
    return payload


def _assistant_text(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""
    return content.strip() if isinstance(content, str) else ""


def _agent_payload(token: str, agent_id: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"id": agent_id})
    payload = request_json(
        f"http://{HOST}:{PORT}/api/v1/models/model?{query}",
        auth=token,
        timeout=10,
    )
    if isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


def _check_runtime_settings() -> list[str]:
    env = runtime_env()
    failures: list[str] = []
    expected = {
        "WEBUI_AUTH": "False",
        "ENABLE_OLLAMA_API": "False",
        "ENABLE_OPENAI_API": "True",
        "ENABLE_PERSISTENT_CONFIG": "False",
        "DEFAULT_MODELS": DEFAULT_AGENT,
        "SAFE_MODE": "True",
    }
    for key, value in expected.items():
        if env.get(key) != value:
            failures.append(f"runtime setting {key} is {env.get(key)!r}, expected {value!r}")

    pinned = {item.strip() for item in PINNED_AGENTS.split(",") if item.strip()}
    expected_agents = {str(agent["id"]) for agent in AGENTS}
    missing_pins = expected_agents - pinned
    if missing_pins:
        failures.append(f"default pinned agents are missing {sorted(missing_pins)}")

    gateway_base, gateway_secret = gateway_config()
    if env.get("OPENAI_API_BASE_URL") != f"{gateway_base}/v1":
        failures.append("Open WebUI is not pointed exclusively at Kitty Gateway")
    if env.get("OPENAI_API_KEY") != gateway_secret:
        failures.append("Open WebUI Gateway credential does not match Kitty's configured secret")
    return failures


def _check_agents(token: str) -> list[str]:
    failures: list[str] = []
    visible = _model_ids(
        request_json(f"http://{HOST}:{PORT}/api/models", auth=token, timeout=10)
    )
    expected_ids = {str(agent["id"]) for agent in AGENTS}
    missing = expected_ids - visible
    if missing:
        failures.append(f"Open WebUI is missing configured agents {sorted(missing)}")

    for agent in AGENTS:
        agent_id = str(agent["id"])
        try:
            payload = _agent_payload(token, agent_id)
        except Failure as exc:
            failures.append(f"agent {agent_id}: {exc}")
            continue
        if payload.get("base_model_id") != agent["base"]:
            failures.append(
                f"agent {agent_id} points at {payload.get('base_model_id')!r}, "
                f"expected {agent['base']!r}"
            )
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        tool_ids = meta.get("toolIds") if isinstance(meta, dict) else None
        has_kitty_tools = isinstance(tool_ids, list) and "server:kitty" in tool_ids
        if bool(agent["tools"]) != has_kitty_tools:
            failures.append(
                f"agent {agent_id} Kitty-tool attachment is {has_kitty_tools}, "
                f"expected {bool(agent['tools'])}"
            )
        capabilities = meta.get("capabilities") if isinstance(meta, dict) else {}
        vision = capabilities.get("vision") if isinstance(capabilities, dict) else None
        if bool(agent.get("vision", False)) != bool(vision):
            failures.append(
                f"agent {agent_id} vision capability is {bool(vision)}, "
                f"expected {bool(agent.get('vision', False))}"
            )
    return failures


def _probe_tool_surface(base: str, secret: str) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    spec = request_json(f"{base}/tools/v1/openapi.json", auth=secret, timeout=10)
    operations = _operation_ids(spec)
    missing = EXPECTED_TOOL_OPERATIONS - operations
    if missing:
        failures.append(f"Kitty tool server is missing operations {sorted(missing)}")

    probes = (
        (
            "memory search",
            "/tools/v1/memory/search?query=__kitty_acceptance_probe__&limit=1",
        ),
        (
            "notes search",
            "/tools/v1/notes/search?query=__kitty_acceptance_probe__&limit=1",
        ),
        ("projects", "/tools/v1/projects"),
        ("calendar", "/tools/v1/calendar/today"),
        ("builder", "/tools/v1/builder/status"),
    )
    payloads: dict[str, dict] = {}
    for label, path in probes:
        try:
            payloads[label] = request_json(f"{base}{path}", auth=secret, timeout=20)
        except Failure as exc:
            failures.append(f"{label} probe failed: {exc}")

    calendar = payloads.get("calendar", {})
    if calendar and calendar.get("available") is False:
        warnings.append("calendar endpoint is healthy but no calendar connection is available")
    projects = payloads.get("projects", {}).get("projects")
    if isinstance(projects, list) and not projects:
        warnings.append("project endpoint is healthy but contains no projects")
    return failures, warnings


def _smoke_model_routes(base: str, secret: str) -> list[str]:
    failures: list[str] = []
    for model_id in USER_FACING_MODEL_IDS:
        try:
            payload = _post_json(
                f"{base}/v1/chat/completions",
                auth=secret,
                timeout=90,
                body={
                    "model": model_id,
                    "messages": [
                        {"role": "user", "content": "Reply with one word: ready"}
                    ],
                    "stream": False,
                    "temperature": 0,
                    "max_tokens": 32,
                },
            )
        except Failure as exc:
            failures.append(f"model route {model_id}: {exc}")
            continue
        if not _assistant_text(payload):
            failures.append(f"model route {model_id} returned no assistant text")
    return failures


def _smoke_daily_agent(token: str) -> list[str]:
    try:
        payload = _post_json(
            f"http://{HOST}:{PORT}/api/chat/completions",
            auth=token,
            timeout=90,
            body={
                "model": DEFAULT_AGENT,
                "messages": [
                    {"role": "user", "content": "Reply with one word: ready"}
                ],
                "stream": False,
                "temperature": 0,
                "max_tokens": 32,
            },
        )
    except Failure as exc:
        return [f"Open WebUI daily-agent turn failed: {exc}"]
    if not _assistant_text(payload):
        return ["Open WebUI daily-agent turn returned no assistant text"]
    return []


def verify_features(*, accept_charges: bool = False) -> dict[str, object]:
    """Verify the configured daily-driver surface, then optionally prove paid routes.

    The default pass is read-only and does not invoke an LLM. With
    ``accept_charges=True`` it also performs one tiny completion through each
    user-facing model route and one end-to-end turn through Daily Kitty.
    """
    failures = _check_runtime_settings()
    warnings: list[str] = []

    base, secret = gateway_config()
    if not secret:
        failures.append("Kitty Gateway secret is not configured")
    else:
        try:
            model_ids = _model_ids(request_json(f"{base}/v1/models", auth=secret, timeout=10))
            missing_models = set(USER_FACING_MODEL_IDS) - model_ids
            if missing_models:
                failures.append(f"Gateway model menu is missing {sorted(missing_models)}")
        except Failure as exc:
            failures.append(f"Gateway model discovery failed: {exc}")

        try:
            tool_failures, tool_warnings = _probe_tool_surface(base, secret)
            failures.extend(tool_failures)
            warnings.extend(tool_warnings)
        except Failure as exc:
            failures.append(f"Kitty tool discovery failed: {exc}")

    token = ""
    try:
        request_json(f"http://{HOST}:{PORT}/health", timeout=5)
        token = claim_system_admin()
        failures.extend(_check_agents(token))
    except Failure as exc:
        failures.append(f"Open WebUI configuration check failed: {exc}")

    if accept_charges and secret:
        failures.extend(_smoke_model_routes(base, secret))
        if token:
            failures.extend(_smoke_daily_agent(token))
    elif not accept_charges:
        warnings.append(
            "live model and end-to-end Daily Kitty turns were skipped; rerun verify "
            "with --accept-charges before calling the setup fully proven"
        )

    for warning in warnings:
        print(f"WARN: {warning}")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        raise Failure(f"{len(failures)} feature acceptance check(s) failed")

    mode = "including live paid routes" if accept_charges else "read-only configuration"
    print(f"All Kitty daily-driver feature checks passed ({mode})")
    return {"passed": True, "mode": mode, "warnings": warnings}
