from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import kitty_production as prod


def _env(tmp_path: Path, *, commit: str = "abc123") -> dict[str, str]:
    return {
        "KITTY_ENV": "production",
        "KITTY_EXPECTED_COMMIT": commit,
        "KITTY_RUNTIME_ROOT": str(tmp_path / "runtime"),
        "GATEWAY_SECRET": "gateway-secret",
        "KITTY_ACTIVE_PROVIDER": "local",
        "MLX_BASE_URL": "http://127.0.0.1:11434/v1",
        "MLX_MODEL": "llama3.2:3b",
    }


def test_production_env_derives_mutable_roots_and_disables_dotenv(tmp_path: Path) -> None:
    env = prod.production_env(_env(tmp_path))
    runtime = tmp_path / "runtime"
    assert env["KITTY_ENV"] == "production"
    assert env["PYTHON_DOTENV_DISABLED"] == "1"
    assert env["KITTY_DATA_DIR"] == str(runtime / "data")
    assert env["KITTY_LOGS_DIR"] == str(runtime / "logs")
    assert env["KITTY_CONFIG_DIR"] == str(runtime / "config")
    assert env["KITTY_PERSONALITY_DIR"] == str(runtime / "personality")
    assert env["KITTY_BUILDER_DATA_DIR"] == str(runtime / "data" / "kittybuilder")
    assert env["GATEWAY_HOST"] == "127.0.0.1"
    assert env["KITTY_UI_HOST"] == "127.0.0.1"


def test_preflight_fails_when_required_production_values_missing(tmp_path: Path) -> None:
    with pytest.raises(prod.ProductionError, match="GATEWAY_SECRET"):
        prod.preflight({"KITTY_ENV": "production", "KITTY_RUNTIME_ROOT": str(tmp_path)})


def test_preflight_rejects_runtime_root_inside_release_checkout(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "release"
    root.mkdir()
    monkeypatch.setattr(prod, "ROOT", root)
    env = _env(tmp_path, commit="abc123")
    env["KITTY_RUNTIME_ROOT"] = str(root / "runtime")
    monkeypatch.setattr(prod, "git_head", lambda: "abc123")
    monkeypatch.setattr(prod, "git_dirty", lambda: False)
    with pytest.raises(prod.ProductionError, match="outside the release checkout"):
        prod.preflight(env)


def test_preflight_requires_exact_clean_release_sha(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(prod, "ROOT", tmp_path / "release")
    prod.ROOT.mkdir()
    env = _env(tmp_path, commit="expected")
    monkeypatch.setattr(prod, "git_head", lambda: "actual")
    monkeypatch.setattr(prod, "git_dirty", lambda: False)
    with pytest.raises(prod.ProductionError, match="expected"):
        prod.preflight(env)
    monkeypatch.setattr(prod, "git_head", lambda: "expected")
    monkeypatch.setattr(prod, "git_dirty", lambda: True)
    with pytest.raises(prod.ProductionError, match="dirty"):
        prod.preflight(env)


def test_seed_preserves_existing_user_config_and_pins_requested_provider(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "release"
    (root / "config").mkdir(parents=True)
    (root / "personality").mkdir()
    (root / "config" / "providers.json").write_text(
        json.dumps({"order": ["openrouter", "local"], "disabled": [], "active": "auto"})
    )
    (root / "config" / "PREFERENCES.md").write_text("release defaults\n")
    (root / "personality" / "identity.md").write_text("release identity\n")
    monkeypatch.setattr(prod, "ROOT", root)
    env = _env(tmp_path)
    runtime = tmp_path / "runtime"
    (runtime / "config").mkdir(parents=True)
    (runtime / "config" / "PREFERENCES.md").write_text("my preferences\n")

    result = prod.seed_runtime(env)

    assert (runtime / "config" / "PREFERENCES.md").read_text() == "my preferences\n"
    providers = json.loads((runtime / "config" / "providers.json").read_text())
    assert providers["active"] == "local"
    assert (runtime / "personality" / "identity.md").read_text() == "release identity\n"
    assert result["active_provider"] == "local"


def test_commands_use_production_server_and_loopback(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "release"
    monkeypatch.setattr(prod, "ROOT", root)
    gateway, ui = prod.service_commands(_env(tmp_path))
    assert gateway[:3] == [str(root / "venv" / "bin" / "python"), "-m", "uvicorn"]
    assert "--host" in gateway and gateway[gateway.index("--host") + 1] == "127.0.0.1"
    assert "next" in " ".join(ui)
    assert "start" in ui
    assert "dev" not in ui
    assert "127.0.0.1" in ui
