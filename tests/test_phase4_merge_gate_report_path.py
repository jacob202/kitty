"""Phase 4 merge gate: relative --report must anchor to --project (D-0011)."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MERGE_GATE = REPO_ROOT / "scripts" / "run_phase4_merge_gate.sh"


@pytest.mark.skipif(not MERGE_GATE.is_file(), reason="merge gate script missing")
@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")
def test_merge_gate_relative_report_written_under_project_not_cwd(tmp_path: Path) -> None:
    """From a foreign cwd, a relative --report path must land under --project (see D-0011)."""
    bash = shutil.which("bash")
    assert bash is not None
    slug = uuid.uuid4().hex
    rel_name = f"docs/_merge_gate_anchor_{slug}.md"
    expected = REPO_ROOT / rel_name
    if expected.exists():
        expected.unlink()

    result = subprocess.run(
        [
            bash,
            str(MERGE_GATE),
            "--project",
            str(REPO_ROOT),
            "--port",
            "59999",
            "--skip-full",
            "--report",
            rel_name,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert expected.is_file(), (
        f"expected report at {expected} (stdout={result.stdout!r} stderr={result.stderr!r})"
    )
    body = expected.read_text(encoding="utf-8")
    assert body.startswith("# Phase 4 Merge Gate Run\n"), body[:200]
    assert "## Full Suite" in body
    assert f"Runtime path: `{REPO_ROOT}`" in body
    expected.unlink(missing_ok=True)
    # Curl smokes fail on bogus port — gate exits non-zero; file integrity is what we test.
    assert result.returncode != 0
