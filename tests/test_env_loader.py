import subprocess
import pytest


@pytest.mark.skip(reason="requires shell env with PATH/HOME — skipped in CI/non-interactive")
def test_safe_env_loader_ignores_stray_commands(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                'OPENROUTER_API_KEY="abc123"',
                "codex",
                "LITELLM_MASTER_KEY=kitty-local-key-change-me",
            ]
        )
    )

    script = """
source /Users/jacobbrizinski/Projects/kitty/kitty_gateway/lib/load_env_safe.sh
load_env_assignments "$1"
printf '%s\n' "$OPENROUTER_API_KEY|$LITELLM_MASTER_KEY"
"""
    result = subprocess.run(
        ["bash", "-lc", script, "bash", str(env_file)],
        capture_output=True,
        text=True,
        check=True,
        env={},
    )

    assert result.stdout.strip() == "abc123|kitty-local-key-change-me"
