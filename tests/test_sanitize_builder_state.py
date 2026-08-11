from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sanitize_builder_state.sh"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def test_sanitizer_handles_builder_branch_with_slash(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "Kitty Test")
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(tmp_path, "add", "seed.txt")
    _git(tmp_path, "commit", "-qm", "seed")
    _git(tmp_path, "checkout", "-qb", "kittybuilder/kb_test")

    claude = tmp_path / ".claude"
    claude.mkdir()
    state = claude / "STATE.md"
    state.write_text(
        '{"status": "clean", "next_action": "keep going", '
        '"head_sha": "stale", "branch": "old"}\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(SCRIPT)], cwd=tmp_path, text=True, capture_output=True
    )

    assert result.returncode == 0, result.stderr
    text = state.read_text(encoding="utf-8")
    assert '"branch": "kittybuilder/kb_test"' in text
    assert '"status": "complete"' in text
    assert '"next_action": "None"' in text
    assert f'"head_sha": "{_git(tmp_path, "rev-parse", "HEAD")}"' in text


def test_worker_only_sanitizes_state_when_packet_owns_it() -> None:
    worker = (SCRIPT.parent / "kittybuilder_opencode_worker.sh").read_text(encoding="utf-8")
    assert 'get("allowed_paths")' in worker
    assert 'if [[ "${owns_builder_state}" == "yes" ]]' in worker
