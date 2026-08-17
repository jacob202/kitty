from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def test_sanitize_builder_state_handles_builder_branch_with_slash(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    subprocess.run(["git", "switch", "-q", "-c", "kittybuilder/kb_test"], cwd=repo, check=True)

    state_dir = repo / ".claude"
    state_dir.mkdir()
    state = {
        "status": "clean",
        "next_action": "keep working",
        "head_sha": "stale",
        "branch": "main",
    }
    (state_dir / "STATE.md").write_text(json.dumps(state), encoding="utf-8")

    script = Path(__file__).resolve().parents[1] / "scripts" / "sanitize_builder_state.sh"
    result = subprocess.run(["bash", str(script)], cwd=repo, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    sanitized = json.loads((state_dir / "STATE.md").read_text(encoding="utf-8"))
    assert sanitized["branch"] == "kittybuilder/kb_test"
    assert sanitized["head_sha"] == _git(repo, "rev-parse", "HEAD")
    assert sanitized["status"] == "complete"
    assert sanitized["next_action"] == "None"


def test_sanitize_builder_state_leaves_clean_continuity_files_untouched(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    state_dir = repo / ".claude"
    state_dir.mkdir()
    original = json.dumps({
        "status": "clean",
        "next_action": "existing lane",
        "head_sha": "continuity-owned-value",
        "branch": "main",
    })
    (state_dir / "STATE.md").write_text(original, encoding="utf-8")
    subprocess.run(["git", "add", ".claude/STATE.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "continuity"], cwd=repo, check=True)
    subprocess.run(["git", "switch", "-q", "-c", "kittybuilder/kb_clean"], cwd=repo, check=True)

    script = Path(__file__).resolve().parents[1] / "scripts" / "sanitize_builder_state.sh"
    result = subprocess.run(["bash", str(script)], cwd=repo, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert (state_dir / "STATE.md").read_text(encoding="utf-8") == original
    assert _git(repo, "status", "--porcelain", "--", ".claude/STATE.md") == ""


def test_worker_only_sanitizes_state_when_packet_owns_continuity_files() -> None:
    worker = (Path(__file__).resolve().parents[1] / "scripts" / "kittybuilder_opencode_worker.sh").read_text(encoding="utf-8")

    assert 'get("allowed_paths")' in worker
    assert 'if [[ "${owns_builder_state}" == "yes" ]]' in worker
