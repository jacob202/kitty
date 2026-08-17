"""`./kitty campaign` dispatch.

The campaign harness is only useful if it is reachable without typing a venv
path. This pins the launcher wiring: dispatch exists, honours PYTHON_BIN like
`cmd_builder` does, and forwards arguments verbatim.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LAUNCHER = REPO / "kitty"


def _python_stub(tmp_path: Path) -> Path:
    """A fake interpreter that reports only the campaign.py call.

    PYTHON_BIN is also used by gateway/lib/load_env_safe.sh, whose output the
    launcher `eval`s — a stub that echoes unconditionally gets its chatter
    evaluated as shell and dies with 'command not found'. Stay silent unless
    the invocation is the one under test.
    """
    stub = tmp_path / "fake-python"
    stub.write_text(
        '#!/bin/bash\ncase "$*" in\n  *campaign.py*) echo "STUB_SAW: $*" ;;\n  *) exit 0 ;;\nesac\n'
    )
    stub.chmod(0o755)
    return stub


def test_launcher_dispatches_campaign():
    text = LAUNCHER.read_text()
    assert "campaign)" in text, "no `campaign)` case in the launcher dispatch"
    assert "cmd_campaign()" in text, "no cmd_campaign function"


def test_campaign_help_is_documented():
    header = "\n".join(LAUNCHER.read_text().splitlines()[:40])
    assert "campaign" in header, "campaign missing from the launcher usage header"


def test_cmd_campaign_honours_python_bin(tmp_path):
    """PYTHON_BIN must win — the bug cmd_builder was already fixed for."""
    stub = _python_stub(tmp_path)

    proc = subprocess.run(
        ["bash", str(LAUNCHER), "campaign", "list"],
        capture_output=True,
        text=True,
        cwd=REPO,
        env={**os.environ, "PYTHON_BIN": str(stub)},
        check=False,
    )
    assert "STUB_SAW:" in proc.stdout, proc.stdout + proc.stderr
    assert "scripts/campaign.py" in proc.stdout
    assert proc.stdout.strip().endswith("list")


@pytest.mark.parametrize("args", [["list"], ["--slug", "x", "status"]])
def test_arguments_forwarded_verbatim(tmp_path, args):
    stub = _python_stub(tmp_path)

    proc = subprocess.run(
        ["bash", str(LAUNCHER), "campaign", *args],
        capture_output=True,
        text=True,
        cwd=REPO,
        env={**os.environ, "PYTHON_BIN": str(stub)},
        check=False,
    )
    for arg in args:
        assert arg in proc.stdout, proc.stdout + proc.stderr
