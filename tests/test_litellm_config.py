"""Smoke test: verify litellm_config.yaml structure and fallback chains."""
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[1] / "gateway" / "litellm_config.yaml"


def _load():
    return yaml.safe_load(CONFIG_PATH.read_text())


def test_config_loads():
    cfg = _load()
    assert isinstance(cfg, dict)


def test_required_model_routes_exist():
    cfg = _load()
    names = {m["model_name"] for m in cfg["model_list"]}
    assert "kitty-default" in names
    assert "kitty-sonnet" in names


def test_kitty_sonnet_routes_to_deepseek():
    """Jacob repointed the main routes off Anthropic onto DeepSeek for cost
    (confirmed 2026-07-24). The route name is historical; the provider is not."""
    cfg = _load()
    sonnet = next(m for m in cfg["model_list"] if m["model_name"] == "kitty-sonnet")
    assert "deepseek" in sonnet["litellm_params"]["model"]


def test_kitty_default_has_fallback_chain():
    cfg = _load()
    fallbacks: list = cfg.get("litellm_settings", {}).get("fallbacks", [])
    default_fb = next((f.get("kitty-default") for f in fallbacks if "kitty-default" in f), None)
    assert default_fb is not None and len(default_fb) >= 1


def test_master_key_uses_env_var():
    """Jacob 2026-07-24: no max_budget on purpose. Spend is capped upstream by the
    OpenRouter account balance, not by the proxy config, so asserting one here was
    testing a policy that doesn't exist. master_key must still come from the env."""
    cfg = _load()
    gs = cfg.get("general_settings", {})
    assert str(gs.get("master_key", "")).startswith("os.environ")
