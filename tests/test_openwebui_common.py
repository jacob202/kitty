from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from openwebui_tool import common  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_sanitized_env_strips_pythonpath_and_pythonhome():
    source = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/Users/test",
        "PYTHONPATH": str(REPO_ROOT),
        "PYTHONHOME": "/somewhere/else",
        "PYTHONSTARTUP": str(REPO_ROOT / "sitecustomize.py"),
    }

    env = common.sanitized_env(source)

    assert "PYTHONPATH" not in env
    assert "PYTHONHOME" not in env
    assert "PYTHONSTARTUP" not in env
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["PATH"] == "/usr/bin:/bin"
    assert env["HOME"] == "/Users/test"


def test_sanitized_env_drops_all_non_allowlisted_keys():
    source = {
        "PYTHONPATH": "/dangerous/path",
        "PYTHONHOME": "/bad",
        "GATEWAY_SECRET": "leaked",
        "OPENROUTER_API_KEY": "leaked",
        "GITHUB_TOKEN": "leaked",
        "AWS_SECRET_ACCESS_KEY": "leaked",
        "OPENAI_API_KEY": "leaked",
        "VIRTUAL_ENV": "/some/venv",
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/test",
        "USER": "test",
    }

    env = common.sanitized_env(source)

    assert env["PATH"] == "/usr/bin:/bin"
    assert env["HOME"] == "/home/test"
    assert env["USER"] == "test"
    assert "PYTHONPATH" not in env
    assert "PYTHONHOME" not in env
    assert "GATEWAY_SECRET" not in env
    assert "OPENROUTER_API_KEY" not in env
    assert "GITHUB_TOKEN" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "OPENAI_API_KEY" not in env
    assert "VIRTUAL_ENV" not in env


def test_sanitized_env_treats_empty_string_keys_as_absent():
    source = {
        "PATH": "",
        "HOME": "",
        "USER": "",
        "PYTHONPATH": "/danger",
        "LANG": "",
    }

    env = common.sanitized_env(source)

    assert "PATH" in env
    assert "HOME" in env
    assert "PYTHONPATH" not in env
    assert "LANG" not in env


def test_sanitized_env_sets_fallback_values():
    env = common.sanitized_env({})

    assert env["PATH"] == os.defpath
    assert env["HOME"] == str(Path.home())
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["NO_PROXY"] == "127.0.0.1,localhost"
    assert env["no_proxy"] == "127.0.0.1,localhost"


def test_subprocess_poisoned_pythonpath_cannot_shadow_third_party_modules(tmp_path, monkeypatch):
    poisoned_dir = tmp_path / "poison"
    poisoned_dir.mkdir()
    (poisoned_dir / "json.py").write_text("raise SystemExit('PYTHONPATH shadow attack succeeded')")

    script = tmp_path / "test_child.py"
    script.write_text(
        "import json\n"
        "from pathlib import Path\n"
        "import os\n"
        "assert 'PYTHONPATH' not in os.environ, f'PYTHONPATH leaked: {os.environ.get(\"PYTHONPATH\")}'\n"
        "assert 'PYTHONHOME' not in os.environ, f'PYTHONHOME leaked: {os.environ.get(\"PYTHONHOME\")}'\n"
        'Path("' + str(tmp_path / "child_ok") + '").write_text("ok")\n'
    )

    source_env = dict(os.environ)
    source_env["PYTHONPATH"] = str(poisoned_dir)
    source_env["PYTHONHOME"] = str(poisoned_dir)

    safe_env = common.sanitized_env(source_env)

    result = subprocess.run(
        [sys.executable, str(script)],
        env=safe_env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"subprocess failed: stdout={result.stdout} stderr={result.stderr}"
    )
    assert (tmp_path / "child_ok").exists()


def test_subprocess_cannot_access_shadowed_mcp_module(tmp_path):
    poisoned_dir = tmp_path / "poison_mcp"
    poisoned_dir.mkdir()
    (poisoned_dir / "mcp.py").write_text("raise SystemExit('MCP shadow attack succeeded')")

    script = tmp_path / "test_mcp_child.py"
    script.write_text(
        "import os\n"
        "from pathlib import Path\n"
        "assert 'PYTHONPATH' not in os.environ\n"
        "try:\n"
        "    import mcp\n"
        "    assert mcp.__file__ is not None\n"
        '    print("mcp imported from: " + mcp.__file__)\n'
        "except ModuleNotFoundError:\n"
        '    print("mcp not available, which is fine — it was not shadowed")\n'
        'Path("' + str(tmp_path / "mcp_child_ok") + '").write_text("ok")\n'
    )

    source_env = dict(os.environ)
    source_env["PYTHONPATH"] = str(poisoned_dir)
    source_env["PYTHONHOME"] = str(poisoned_dir)

    safe_env = common.sanitized_env(source_env)

    result = subprocess.run(
        [sys.executable, str(script)],
        env=safe_env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"subprocess failed: stdout={result.stdout} stderr={result.stderr}"
    )
    assert (tmp_path / "mcp_child_ok").exists()
    assert "attack succeeded" not in result.stderr
    assert "attack succeeded" not in result.stdout
