"""Tests for route_model() — pure routing decisions, no network or ML calls."""

import pytest


# ── Import helper ────────────────────────────────────────────────────────────
# route_model() is a pure function; tests pass mlx_ready explicitly so the
# result is deterministic regardless of KITTY_ENABLE_LOCAL_MLX in the env.

from src.space_kitty.llm_client import route_model, ModelRoute


# ── Offline behaviour ─────────────────────────────────────────────────────────

def test_offline_routes_to_mlx():
    r = route_model(offline=True)
    assert r.provider == "mlx_local"
    assert r.model == ""
    assert "offline" in r.reason


def test_offline_overrides_all_modes():
    for mode in ("fast", "balanced", "max"):
        r = route_model(mode=mode, offline=True)
        assert r.provider == "mlx_local", f"offline should always be mlx_local (mode={mode})"


def test_offline_overrides_reasoning():
    r = route_model(offline=True, reasoning=True)
    assert r.provider == "mlx_local"


# ── Fast mode ─────────────────────────────────────────────────────────────────

def test_fast_with_mlx_ready_routes_to_mlx():
    r = route_model(mode="fast", mlx_ready=True)
    assert r.provider == "mlx_local"
    assert r.model == ""


def test_fast_without_mlx_routes_to_free_router():
    r = route_model(mode="fast", mlx_ready=False)
    assert r.provider == "openrouter"
    assert r.model == "openrouter/free"


def test_fast_local_target_routes_to_mlx_even_without_mlx_ready():
    # Explicit model_target="local" overrides mlx_ready flag in fast mode
    r = route_model(mode="fast", model_target="local", mlx_ready=False)
    assert r.provider == "mlx_local"


def test_fast_mlx_ready_takes_priority_over_free_target():
    r = route_model(mode="fast", model_target="free", mlx_ready=True)
    assert r.provider == "mlx_local"


# ── Balanced mode ─────────────────────────────────────────────────────────────

def test_balanced_no_reasoning_uses_free_router():
    r = route_model(mode="balanced", reasoning=False)
    assert r.provider == "openrouter"
    assert r.model == "openrouter/free"


def test_balanced_reasoning_routes_to_distill_model():
    r = route_model(mode="balanced", reasoning=True)
    assert r.provider == "openrouter"
    # Should be the reasoning/distill model, not the free router
    assert r.model != "openrouter/free"
    assert "deepseek" in r.model.lower() or "r1" in r.model.lower()


def test_balanced_configured_uses_env_model(monkeypatch):
    monkeypatch.setenv("KITTY_MODEL", "mistralai/mistral-7b-instruct")
    r = route_model(mode="balanced", model_target="configured")
    assert r.provider == "openrouter"
    assert r.model == "mistralai/mistral-7b-instruct"


def test_balanced_configured_falls_back_to_free_when_env_unset(monkeypatch):
    monkeypatch.delenv("KITTY_MODEL", raising=False)
    r = route_model(mode="balanced", model_target="configured")
    assert r.provider == "openrouter"
    assert r.model == "openrouter/free"


def test_balanced_local_target_uses_free_router():
    # "local" in balanced mode has no special meaning — uses free router
    r = route_model(mode="balanced", model_target="local")
    assert r.provider == "openrouter"


# ── Max mode ──────────────────────────────────────────────────────────────────

def test_max_routes_to_deepseek_r1():
    r = route_model(mode="max")
    assert r.provider == "openrouter"
    assert "deepseek" in r.model.lower() or "r1" in r.model.lower()


def test_max_uses_env_override(monkeypatch):
    monkeypatch.setenv("KITTY_MAX_MODEL", "anthropic/claude-opus-4")
    # Reimport to pick up new env value
    import importlib
    import src.space_kitty.llm_client as mod
    importlib.reload(mod)
    r = mod.route_model(mode="max")
    assert r.model == "anthropic/claude-opus-4"
    # Restore
    importlib.reload(mod)


# ── Unknown mode ──────────────────────────────────────────────────────────────

def test_unknown_mode_falls_back_to_free():
    r = route_model(mode="turbo_ultra_premium")
    assert r.provider == "openrouter"
    assert r.model == "openrouter/free"
    assert "unknown" in r.reason.lower()


# ── ModelRoute is immutable ───────────────────────────────────────────────────

def test_model_route_is_frozen():
    r = route_model(mode="max")
    with pytest.raises((AttributeError, TypeError)):
        r.provider = "mlx_local"  # type: ignore[misc]


# ── mlx_ready override beats env var ─────────────────────────────────────────

def test_mlx_ready_false_overrides_env(monkeypatch):
    monkeypatch.setenv("KITTY_ENABLE_LOCAL_MLX", "1")
    # Even if env says local is enabled, explicit mlx_ready=False should go remote
    r = route_model(mode="fast", mlx_ready=False)
    assert r.provider == "openrouter"


def test_mlx_ready_true_overrides_env(monkeypatch):
    monkeypatch.setenv("KITTY_ENABLE_LOCAL_MLX", "0")
    r = route_model(mode="fast", mlx_ready=True)
    assert r.provider == "mlx_local"


# ── web_orchestrator _model_for_target fix ───────────────────────────────────

def test_web_orchestrator_local_target_uses_free_router():
    """'local' model_target in the balanced path should use free router, not configured."""
    from src.api.web_orchestrator import _model_for_target, _FREE_ROUTER
    assert _model_for_target("local") == _FREE_ROUTER


def test_web_orchestrator_free_target_uses_free_router():
    from src.api.web_orchestrator import _model_for_target, _FREE_ROUTER
    assert _model_for_target("free") == _FREE_ROUTER


def test_web_orchestrator_configured_target_uses_or_bal():
    from src.api.web_orchestrator import _model_for_target, _OR_BAL
    assert _model_for_target("configured") == _OR_BAL
