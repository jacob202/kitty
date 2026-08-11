from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


# Matches an absolute path assigned directly to ROOT_DIR: ROOT_DIR=/...,
# ROOT_DIR="/...", or ROOT_DIR='/...'. The portable form is
# ROOT_DIR="$(cd ... && pwd)", where the char after the quote is "$", not "/",
# so this only fires on a hardcoded machine path — on any OS, not just macOS.
_HARDCODED_ROOT_DIR = re.compile(r"""ROOT_DIR=['"]?/""")


def test_no_shell_script_hardcodes_an_absolute_repo_path() -> None:
    """A2: launchers must resolve their own location, never hardcode a machine path.

    The repo has repeatedly regressed to ROOT_DIR="/Users/jacobbrizinski/..."
    which breaks any other clone. Shell scripts must derive ROOT_DIR from
    BASH_SOURCE instead, so a fresh clone works without editing. The pattern is
    anchored on ROOT_DIR= (rather than a substring like "/Users/") so it also
    catches a "/home/..." or "/opt/..." regression without false-positiving on
    legitimate absolute paths elsewhere in the scripts (e.g. PATH entries).
    """
    offenders = []
    for sh in sorted(ROOT.glob("gateway/*.sh")):
        text = sh.read_text(encoding="utf-8")
        if _HARDCODED_ROOT_DIR.search(text):
            offenders.append(sh.name)
    assert not offenders, f"hardcoded absolute ROOT_DIR in: {offenders}"


def test_gateway_launcher_scripts_use_live_gateway_paths() -> None:
    expected_snippets = {
        "gateway/start_gateway.sh": [
            'source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"',
            'export KITTY_ENV="${KITTY_ENV:-prod}"',
        ],
        "gateway/start_litellm.sh": [
            'source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"',
            'LITELLM_CONFIG="${LITELLM_CONFIG:-gateway/litellm_config.yaml}"',
            'LITELLM_REQUIREMENTS_FILE="${LITELLM_REQUIREMENTS_FILE:-gateway/requirements.litellm.txt}"',
        ],
    }

    for rel_path, snippets in expected_snippets.items():
        contents = _read_text(rel_path)
        for snippet in snippets:
            assert snippet in contents, f"{rel_path} is missing {snippet!r}"


def test_litellm_launcher_avoids_repo_package_shadowing(tmp_path: Path) -> None:
    fake_venv = tmp_path / "venv-litellm"
    fake_bin = fake_venv / "bin"
    fake_bin.mkdir(parents=True)
    capture_path = tmp_path / "litellm-launch.txt"

    (fake_bin / "activate").write_text(
        f'export PATH="{fake_bin}:$PATH"\n',
        encoding="utf-8",
    )
    for name, body in {
        "python": "#!/bin/bash\nexit 0\n",
        "litellm": (
            "#!/bin/bash\n"
            'printf "%s\\n" "$PWD" >"$LITELLM_CAPTURE"\n'
            'printf "PYTHONPATH=%s\\n" "${PYTHONPATH-}" >>"$LITELLM_CAPTURE"\n'
            'printf "%s\\n" "$@" >>"$LITELLM_CAPTURE"\n'
        ),
    }.items():
        executable = fake_bin / name
        executable.write_text(body, encoding="utf-8")
        executable.chmod(0o755)

    env = {
        **os.environ,
        "LITELLM_CAPTURE": str(capture_path),
        "LITELLM_VENV": str(fake_venv),
        "PYTHONPATH": str(ROOT),
    }
    result = subprocess.run(
        ["bash", str(ROOT / "gateway/start_litellm.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    launch = capture_path.read_text(encoding="utf-8").splitlines()
    assert launch[0] == str(fake_venv.resolve())
    assert launch[1] == "PYTHONPATH="
    config_index = launch.index("--config")
    assert launch[config_index + 1] == str(
        (ROOT / "gateway/litellm_config.yaml").resolve()
    )


def test_kitty_launcher_points_at_live_gateway_scripts() -> None:
    launcher = _read_text("kitty")
    assert 'bash "$KITTY_ROOT/gateway/start_litellm.sh"' in launcher
    assert 'bash "$KITTY_ROOT/gateway/start_gateway.sh"' in launcher
    assert "start_tool_servers.sh" not in launcher
    assert "start_all.sh" not in launcher
