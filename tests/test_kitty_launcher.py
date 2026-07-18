from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_launcher_generates_gateway_secret_for_runtime_commands() -> None:
    launcher = (ROOT / "kitty").read_text(encoding="utf-8")

    assert "ensure_gateway_secret()" in launcher
    assert "GATEWAY_SECRET=" in launcher
    assert "KITTY_GATEWAY_SECRET=" in launcher
    assert launcher.count("ensure_gateway_secret") >= 4


def test_launcher_status_understands_launchd_services() -> None:
    launcher = (ROOT / "kitty").read_text(encoding="utf-8")

    assert "launchd_pid()" in launcher
    assert "gui/$(id -u)/com.kitty.$svc" in launcher
    assert "running via launchd" in launcher


def test_launcher_uses_safe_dotenv_loader() -> None:
    launcher = (ROOT / "kitty").read_text(encoding="utf-8")

    assert 'source "$KITTY_ROOT/gateway/lib/load_env_safe.sh"' in launcher
    assert 'load_env_assignments "$KITTY_ROOT/.env"' in launcher


def test_launcher_uses_litellm_readiness_for_status() -> None:
    launcher = (ROOT / "kitty").read_text(encoding="utf-8")

    assert 'http://127.0.0.1:$LITELLM_PORT/health/readiness' in launcher


def test_launcher_exposes_backup_and_restore_drill() -> None:
    launcher = (ROOT / "kitty").read_text(encoding="utf-8")

    assert "cmd_backup()" in launcher
    assert "cmd_restore_drill()" in launcher
    assert 'scripts/kitty_backup.py" backup' in launcher
    assert 'scripts/kitty_backup.py" restore-drill' in launcher
    assert "backup)    shift; cmd_backup" in launcher
    assert "restore-drill) shift; cmd_restore_drill" in launcher


def test_launcher_exposes_agent_context_receipt() -> None:
    launcher = (ROOT / "kitty").read_text(encoding="utf-8")

    assert "cmd_context()" in launcher
    assert '-m gateway.context_receipt "$@"' in launcher
    assert 'context)   shift; cmd_context "$@"' in launcher


def test_agent_context_receipt_runs_outside_checkout(tmp_path: Path) -> None:
    """The bootloader must import the checkout that owns the invoked launcher."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [str(ROOT / "kitty"), "context", "--agent"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    # This test asserts checkout resolution, not the continuity verdict. The
    # receipt exits 1 whenever continuity failures are present (a legitimately
    # stale checkpoint, an environment-specific canonical-checkout mismatch),
    # which is orthogonal to whether the bootloader found the right checkout.
    # Accept 0 (ok) or 1 (receipt built, continuity not ok); reject a real
    # invocation failure (bad import, crash) that produces no parseable receipt.
    assert result.returncode in (0, 1), result.stdout + result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["repository"]["repo_path"] == str(ROOT)
    assert isinstance(receipt["schema_version"], int)
