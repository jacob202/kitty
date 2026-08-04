from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from openwebui_tool import acceptance  # noqa: E402
from openwebui_tool.common import Failure  # noqa: E402


def test_model_and_operation_id_extractors():
    assert acceptance._model_ids(
        {"data": [{"id": "kitty-auto"}, {"id": "kitty-fast"}, {"no": "id"}]}
    ) == {"kitty-auto", "kitty-fast"}
    assert acceptance._operation_ids(
        {
            "paths": {
                "/one": {"get": {"operationId": "one"}},
                "/two": {"post": {"operationId": "two"}},
            }
        }
    ) == {"one", "two"}


def test_runtime_settings_check_accepts_the_hardened_configuration(monkeypatch):
    monkeypatch.setattr(
        acceptance,
        "runtime_env",
        lambda: {
            "WEBUI_AUTH": "False",
            "ENABLE_OLLAMA_API": "False",
            "ENABLE_OPENAI_API": "True",
            "ENABLE_PERSISTENT_CONFIG": "False",
            "DEFAULT_MODELS": acceptance.DEFAULT_AGENT,
            "SAFE_MODE": "True",
            "OPENAI_API_BASE_URL": "http://gateway/v1",
            "OPENAI_API_KEY": "secret",
        },
    )
    monkeypatch.setattr(
        acceptance, "gateway_config", lambda: ("http://gateway", "secret")
    )

    assert acceptance._check_runtime_settings() == []


def test_agent_check_verifies_base_tools_and_vision(monkeypatch):
    agent_by_id = {str(agent["id"]): agent for agent in acceptance.AGENTS}

    def fake_request(url, *, auth="", timeout=0):
        if url.endswith("/api/models"):
            return {"data": [{"id": agent_id} for agent_id in agent_by_id]}
        agent_id = url.rsplit("=", 1)[-1]
        agent = agent_by_id[agent_id]
        meta = {
            "capabilities": {"vision": bool(agent.get("vision", False))},
        }
        if agent["tools"]:
            meta["toolIds"] = ["server:kitty"]
        return {
            "id": agent_id,
            "base_model_id": agent["base"],
            "meta": meta,
        }

    monkeypatch.setattr(acceptance, "request_json", fake_request)

    assert acceptance._check_agents("token") == []


def test_tool_surface_probes_every_read_only_feature(monkeypatch):
    seen: list[str] = []

    def fake_request(url, *, auth="", timeout=0):
        seen.append(url)
        if url.endswith("/openapi.json"):
            return {
                "paths": {
                    f"/{operation}": {"get": {"operationId": operation}}
                    for operation in acceptance.EXPECTED_TOOL_OPERATIONS
                }
            }
        if url.endswith("/projects"):
            return {"projects": [{"id": 1}]}
        if url.endswith("/calendar/today"):
            return {"available": True, "events": []}
        return {}

    monkeypatch.setattr(acceptance, "request_json", fake_request)

    failures, warnings = acceptance._probe_tool_surface("http://gateway", "secret")

    assert failures == []
    assert warnings == []
    assert any("memory/search" in url for url in seen)
    assert any("notes/search" in url for url in seen)
    assert any("calendar/today" in url for url in seen)
    assert any("builder/status" in url for url in seen)


def test_verify_features_is_read_only_without_charge_acceptance(monkeypatch):
    monkeypatch.setattr(acceptance, "_check_runtime_settings", lambda: [])
    monkeypatch.setattr(
        acceptance, "gateway_config", lambda: ("http://gateway", "secret")
    )
    monkeypatch.setattr(
        acceptance,
        "request_json",
        lambda url, **kwargs: (
            {"data": [{"id": model} for model in acceptance.USER_FACING_MODEL_IDS]}
            if url.endswith("/v1/models")
            else {}
        ),
    )
    monkeypatch.setattr(acceptance, "_probe_tool_surface", lambda *args: ([], []))
    monkeypatch.setattr(acceptance, "claim_system_admin", lambda: "token")
    monkeypatch.setattr(acceptance, "_check_agents", lambda token: [])
    monkeypatch.setattr(
        acceptance,
        "_smoke_model_routes",
        lambda *args: pytest.fail("paid model smoke must not run"),
    )
    monkeypatch.setattr(
        acceptance,
        "_smoke_daily_agent",
        lambda *args: pytest.fail("paid agent smoke must not run"),
    )

    result = acceptance.verify_features(accept_charges=False)

    assert result["passed"] is True
    assert result["warnings"]


def test_verify_features_runs_all_paid_smokes_when_authorized(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(acceptance, "_check_runtime_settings", lambda: [])
    monkeypatch.setattr(
        acceptance, "gateway_config", lambda: ("http://gateway", "secret")
    )
    monkeypatch.setattr(
        acceptance,
        "request_json",
        lambda url, **kwargs: (
            {"data": [{"id": model} for model in acceptance.USER_FACING_MODEL_IDS]}
            if url.endswith("/v1/models")
            else {}
        ),
    )
    monkeypatch.setattr(acceptance, "_probe_tool_surface", lambda *args: ([], []))
    monkeypatch.setattr(acceptance, "claim_system_admin", lambda: "token")
    monkeypatch.setattr(acceptance, "_check_agents", lambda token: [])
    monkeypatch.setattr(
        acceptance,
        "_smoke_model_routes",
        lambda *args: calls.append("models") or [],
    )
    monkeypatch.setattr(
        acceptance,
        "_smoke_daily_agent",
        lambda *args: calls.append("agent") or [],
    )

    result = acceptance.verify_features(accept_charges=True)

    assert result["passed"] is True
    assert calls == ["models", "agent"]


def test_verify_features_fails_loudly_on_missing_model_menu(monkeypatch):
    monkeypatch.setattr(acceptance, "_check_runtime_settings", lambda: [])
    monkeypatch.setattr(
        acceptance, "gateway_config", lambda: ("http://gateway", "secret")
    )
    monkeypatch.setattr(acceptance, "request_json", lambda *args, **kwargs: {"data": []})
    monkeypatch.setattr(acceptance, "_probe_tool_surface", lambda *args: ([], []))
    monkeypatch.setattr(acceptance, "claim_system_admin", lambda: "token")
    monkeypatch.setattr(acceptance, "_check_agents", lambda token: [])

    with pytest.raises(Failure) as excinfo:
        acceptance.verify_features(accept_charges=False)

    assert "feature acceptance" in str(excinfo.value)
