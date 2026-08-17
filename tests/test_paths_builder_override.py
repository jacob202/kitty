"""Regression test for KPROOF-001: KITTYBUILDER_DIR must honor an env override.

gateway/paths.py computes KITTYBUILDER_DIR/BUILDER_QUEUE_DB as module-level
constants derived from DATA_DIR (which is checkout-relative). A clean worktree
therefore looks for Builder's durable queue DB in its own (empty) data/ dir
instead of the canonical checkout. Each case below imports gateway.paths in a
fresh subprocess so the module-level constants are computed under a controlled
environment, without polluting the current process's already-imported module.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

_PRINT_PATHS = (
    "import gateway.paths as p; "
    "print(p.KITTYBUILDER_DIR); "
    "print(p.BUILDER_QUEUE_DB)"
)


def _run_with_env(env: dict) -> list[str]:
    result = subprocess.run(
        [sys.executable, "-c", _PRINT_PATHS],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip().splitlines()


def test_kittybuilder_dir_uses_override_when_set(monkeypatch):
    override = "/tmp/kproof-001-canonical/kittybuilder"
    env = {**__import__("os").environ, "KITTY_BUILDER_DATA_DIR": override}
    lines = _run_with_env(env)
    assert lines[0] == override
    assert lines[1] == f"{override}/builder_queue.db"


def test_kittybuilder_dir_defaults_without_override():
    import os

    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"KITTY_DATA_ROOT", "KITTY_BUILDER_DATA_DIR"}
    }
    lines = _run_with_env(env)
    expected_dir = str(ROOT / "data" / "kittybuilder")
    assert lines[0] == expected_dir
    assert lines[1] == str(Path(expected_dir) / "builder_queue.db")
