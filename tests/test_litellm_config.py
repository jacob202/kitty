"""Smoke test: verify litellm_config.yaml structure and fallback chains."""
import yaml
from pathlib import Path

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


def test_kitty_sonnet_uses_anthropic():
    cfg = _load()
    sonnet = next(m for m in cfg["model_list"] if m["model_name"] == "kitty-sonnet")
    assert "anthropic" in sonnet["litellm_params"]["model"]


def test_kitty_default_has_fallback_chain():
    cfg = _load()
    fallbacks: list = cfg.get("litellm_settings", {}).get("fallbacks", [])
    default_fb = next((f.get("kitty-default") for f in fallbacks if "kitty-default" in f), None)
    assert default_fb is not None and len(default_fb) >= 1


def test_kitty_sonnet_has_fallback_chain():
    cfg = _load()
    fallbacks: list = cfg.get("litellm_settings", {}).get("fallbacks", [])
    sonnet_fb = next((f.get("kitty-sonnet") for f in fallbacks if "kitty-sonnet" in f), None)
    assert sonnet_fb is not None and len(sonnet_fb) >= 1


def test_budget_and_master_key_use_env_vars():
    cfg = _load()
    gs = cfg.get("general_settings", {})
    assert str(gs.get("max_budget", "")).startswith("os.environ")
    assert str(gs.get("master_key", "")).startswith("os.environ")
