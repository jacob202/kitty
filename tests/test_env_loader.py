import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_safe_env_loader_ignores_stray_commands_and_expands_env_vars(tmp_path):
    """
    Verifies that load_env_assignments ignores stray non-assignment lines and expands `$HOME` inside quoted values.
    
    Creates a temporary `.env` containing two valid assignments, one stray command line, and a quoted path referencing `$HOME`; sources `load_env_safe.sh`, invokes `load_env_assignments` on that file with `HOME` set to a fake directory, and asserts the loaded values match the assignments with `$HOME` expanded.
    """
    env_file = tmp_path / ".env"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    env_file.write_text(
        "\n".join(
            [
                'OPENROUTER_API_KEY="abc123"',
                "codex",
                "LITELLM_MASTER_KEY=kitty-local-key-change-me",
                'OPENWEBUI_DATA_DIR="$HOME/kitty-services/open-webui-data"',
            ]
        )
    )

    load_env_safe = _REPO_ROOT / "gateway" / "lib" / "load_env_safe.sh"
    script = f"""
source {load_env_safe}
load_env_assignments "$1"
printf '%s\n' "$OPENROUTER_API_KEY|$LITELLM_MASTER_KEY|$OPENWEBUI_DATA_DIR"
"""
    result = subprocess.run(
        ["bash", "-lc", script, "bash", str(env_file)],
        capture_output=True,
        text=True,
        check=True,
        env={
            "HOME": str(fake_home),
            "PATH": "/usr/bin:/bin:/opt/homebrew/bin",
            # Pin the loader to the interpreter running the tests so the test
            # doesn't depend on a system python3.12 having python-dotenv.
            "PYTHON_BIN": sys.executable,
        },
    )

    assert (
        result.stdout.strip()
        == f"abc123|kitty-local-key-change-me|{fake_home}/kitty-services/open-webui-data"
    )
