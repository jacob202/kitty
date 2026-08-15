from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _probe(env: dict[str, str]) -> dict[str, str]:
    code = """
import json
from gateway import paths
print(json.dumps({
  'data': str(paths.DATA_DIR),
  'logs': str(paths.LOGS_DIR),
  'config': str(paths.CONFIG_DIR),
  'personality': str(paths.PERSONALITY_DIR),
  'kitty_db': str(paths.KITTY_DB_FILE),
  'builder': str(paths.BUILDER_QUEUE_DB),
  'user': str(paths.USER_DIR),
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_runtime_roots_can_live_outside_release_checkout(tmp_path: Path) -> None:
    data = tmp_path / "data"
    logs = tmp_path / "logs"
    config = tmp_path / "config"
    personality = tmp_path / "personality"
    env = {
        **os.environ,
        "KITTY_DATA_DIR": str(data),
        "KITTY_LOGS_DIR": str(logs),
        "KITTY_CONFIG_DIR": str(config),
        "KITTY_PERSONALITY_DIR": str(personality),
    }
    observed = _probe(env)
    assert observed["data"] == str(data)
    assert observed["logs"] == str(logs)
    assert observed["config"] == str(config)
    assert observed["personality"] == str(personality)
    assert observed["kitty_db"] == str(data / "kitty" / "kitty.db")
    assert observed["builder"] == str(data / "kittybuilder" / "builder_queue.db")
    assert observed["user"] == str(config / "USER")


def test_default_paths_remain_repo_local_when_overrides_absent() -> None:
    env = dict(os.environ)
    for key in ("KITTY_DATA_DIR", "KITTY_LOGS_DIR", "KITTY_CONFIG_DIR", "KITTY_PERSONALITY_DIR", "KITTY_BUILDER_DATA_DIR"):
        env.pop(key, None)
    observed = _probe(env)
    root = Path(__file__).resolve().parents[1]
    assert observed["data"] == str(root / "data")
    assert observed["logs"] == str(root / "logs")
    assert observed["config"] == str(root / "config")
    assert observed["personality"] == str(root / "personality")
