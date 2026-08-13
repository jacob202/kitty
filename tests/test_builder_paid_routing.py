from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway import builder_paid_routing as bpr


def _policy(*, enabled: bool = True, cheap_cap: float = 0.10, frontier_cap: float = 0.50) -> dict:
    return {
        "schema_version": 1,
        "paid_openrouter_enabled": enabled,
        "routes": {
            "cheap": {
                "provider": "openrouter",
                "worker_model": "openrouter/deepseek/deepseek-v4-flash",
                "reviewer_model": "openrouter/qwen/qwen3.7-plus",
                "governor_route": "cheap",
                "max_projected_cad_per_attempt": cheap_cap,
            },
            "frontier": {
                "provider": "openrouter",
                "worker_model": "openrouter/deepseek/deepseek-v4-pro",
                "reviewer_model": "openrouter/qwen/qwen3.7-max",
                "governor_route": "frontier",
                "max_projected_cad_per_attempt": frontier_cap,
            },
        },
    }

def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "paid-routes.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_resolve_cheap_route_is_value_default(tmp_path: Path):
    route = bpr.resolve_paid_route("cheap", config_path=_write(tmp_path, _policy()))

    assert route.tier == "cheap"
    assert route.provider == "openrouter"
    assert route.worker_model == "openrouter/deepseek/deepseek-v4-flash"
    assert route.reviewer_model == "openrouter/qwen/qwen3.7-plus"
    assert route.governor_route == "cheap"
    assert 0 < route.projected_cost_cad <= route.max_projected_cost_cad == 0.10


def test_resolve_frontier_route_is_explicit_escalation(tmp_path: Path):
    route = bpr.resolve_paid_route("frontier", config_path=_write(tmp_path, _policy()))

    assert route.tier == "frontier"
    assert route.worker_model == "openrouter/deepseek/deepseek-v4-pro"
    assert route.reviewer_model == "openrouter/qwen/qwen3.7-max"
    assert route.governor_route == "frontier"
    assert 0 < route.projected_cost_cad <= route.max_projected_cost_cad == 0.50
    assert route.worker_model != route.reviewer_model

def test_paid_routes_can_be_disabled_without_fallback(tmp_path: Path):
    with pytest.raises(bpr.PaidRoutingError, match="disabled"):
        bpr.resolve_paid_route(
            "cheap", config_path=_write(tmp_path, _policy(enabled=False))
        )


def test_unknown_paid_tier_fails_loud(tmp_path: Path):
    with pytest.raises(bpr.PaidRoutingError, match="unknown paid tier"):
        bpr.resolve_paid_route("turbo", config_path=_write(tmp_path, _policy()))


def test_projected_attempt_cost_must_fit_route_ceiling(tmp_path: Path):
    path = _write(tmp_path, _policy(cheap_cap=0.0001))

    with pytest.raises(bpr.PaidRoutingError, match="projects CAD"):
        bpr.resolve_paid_route("cheap", config_path=path)


def test_paid_reviewer_must_be_independent_model(tmp_path: Path):
    payload = _policy()
    payload["routes"]["cheap"]["reviewer_model"] = payload["routes"]["cheap"]["worker_model"]

    with pytest.raises(bpr.PaidRoutingError, match="reviewer model"):
        bpr.resolve_paid_route("cheap", config_path=_write(tmp_path, payload))


def test_opencode_config_has_separate_free_and_paid_agents():
    config = json.loads((Path(__file__).resolve().parents[1] / "opencode.jsonc").read_text())
    agents = config["agent"]

    assert agents["free-builder"]["model"].endswith("-free")
    assert agents["free-reviewer"]["model"].endswith("-free")
    assert agents["paid-builder"]["model"] == (
        "openrouter/deepseek/deepseek-v4-flash"
    )
    assert agents["paid-reviewer"]["model"] == "openrouter/qwen/qwen3.7-plus"
    assert agents["paid-reviewer"]["permission"]["edit"] == "deny"
