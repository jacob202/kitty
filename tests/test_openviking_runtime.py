from __future__ import annotations

import json
import plistlib
from pathlib import Path

import pytest

from gateway import openviking_shadow as ovs
from scripts import openviking_runtime as runtime
from scripts import shadow_canary


def test_plists_match_proven_runtime_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "openviking"
    agents = tmp_path / "LaunchAgents"
    monkeypatch.setenv("KITTY_OPENVIKING_HOME", str(home))
    monkeypatch.setenv("KITTY_LAUNCH_AGENTS_DIR", str(agents))
    monkeypatch.setenv("KITTY_OPENVIKING_SERVER_BIN", "/repo/venv/bin/openviking-server")
    monkeypatch.setenv("OLLAMA_BIN", "/opt/homebrew/bin/ollama")
    server = runtime.build_server_plist(Path("/repo"))
    embed = runtime.build_embedding_plist(Path("/repo"))

    assert server["Label"] == "com.kitty.openviking-server"
    assert server["ProgramArguments"] == ["/repo/venv/bin/openviking-server", "--config", str(home / "ov.conf")]
    assert server["StandardOutPath"] == str(home / "server.log")
    assert embed["Label"] == "com.kitty.openviking-embedding"
    assert embed["ProgramArguments"] == ["/opt/homebrew/bin/ollama", "serve"]
    assert embed["EnvironmentVariables"] == {
        "OLLAMA_HOST": "127.0.0.1:11435",
        "OLLAMA_MODELS": str(Path("~/.ollama/models").expanduser()),
        "OLLAMA_KEEP_ALIVE": "-1",
        "OLLAMA_CONTEXT_LENGTH": "8192",
        "OLLAMA_NUM_PARALLEL": "1",
    }


def test_install_is_idempotent_and_preserves_config_and_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "openviking"
    agents = tmp_path / "LaunchAgents"
    workspace = home / "data-1024-preserved"
    workspace.mkdir(parents=True)
    config = home / "ov.conf"
    config.write_text(json.dumps({"storage": {"workspace": str(workspace)}}), encoding="utf-8")
    marker = workspace / "do-not-delete"
    marker.write_text("preserved", encoding="utf-8")
    monkeypatch.setenv("KITTY_OPENVIKING_HOME", str(home))
    monkeypatch.setenv("KITTY_LAUNCH_AGENTS_DIR", str(agents))

    first = runtime.install(tmp_path)
    second = runtime.install(tmp_path)

    assert first == second
    assert config.read_text(encoding="utf-8") == json.dumps({"storage": {"workspace": str(workspace)}})
    assert marker.read_text(encoding="utf-8") == "preserved"
    for path in first:
        assert plistlib.loads(path.read_bytes())["Label"] in {runtime.SERVER_LABEL, runtime.EMBED_LABEL}


def test_uninstall_removes_only_plists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "openviking"
    agents = tmp_path / "LaunchAgents"
    workspace = home / "data-768"
    workspace.mkdir(parents=True)
    config = home / "ov.conf"
    config.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("KITTY_OPENVIKING_HOME", str(home))
    monkeypatch.setenv("KITTY_LAUNCH_AGENTS_DIR", str(agents))
    monkeypatch.setattr(runtime.sys, "platform", "linux")
    runtime.install(tmp_path)

    assert runtime.uninstall() == 0
    assert config.exists()
    assert workspace.exists()
    assert list(agents.glob("com.kitty.openviking-*.plist")) == []


def test_embedding_probe_requires_nomic_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "_get_json", lambda _url: (True, {"models": [{"name": "nomic-embed-text:latest"}]}))
    assert runtime.probe_embedding().ok is True
    monkeypatch.setattr(runtime, "_get_json", lambda _url: (True, {"models": [{"name": "other:latest"}]}))
    assert runtime.probe_embedding().ok is False


@pytest.mark.asyncio
async def test_canary_exercises_shadow_context_once_and_never_injects(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    async def fake_retrieve(query: str, **_kwargs) -> ovs.RetrievalResult:
        calls.append(query)
        return ovs.RetrievalResult(
            hits=(ovs.Hit("viking://resources/kitty-kb/a.md", 0.91, "private context"),),
            latency_ms=12.5,
        )

    monkeypatch.setattr(ovs, "retrieve", fake_retrieve)
    monkeypatch.setenv("KITTY_OPENVIKING_MODE", "context")

    result = await shadow_canary.run_shadow_canary("collision truth")

    assert calls == ["collision truth"]
    assert result["ok"] is True
    assert result["mode"] == "shadow"
    assert result["injected"] is False
    assert result["retrievals"] == 1
    assert result["hits"] == 1
    assert "private context" not in json.dumps(result)
    assert __import__("os").environ["KITTY_OPENVIKING_MODE"] == "context"


@pytest.mark.asyncio
async def test_canary_fails_if_shadow_seam_injects(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unsafe_context(_query: str) -> str:
        return "should not be injected"

    monkeypatch.setattr(ovs, "context_block", unsafe_context)
    result = await shadow_canary.run_shadow_canary("test")
    assert result["ok"] is False
    assert result["injected"] is True
