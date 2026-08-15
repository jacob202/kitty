"""Tests for scripts/kittybuilder_claude_adapter.py — Claude worker/reviewer.

Integration-style: fake ``claude`` executable on PATH, isolated worktree,
strict contracts. The fake binary writes known-good worker/review JSON without
making a real API call. Tests validate the strict contract: exit 75 for
unavailable/unauthed, no fallback, reviewer immutability, hash binding.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ADAPTER = (Path(__file__).parents[1] / "scripts" / "kittybuilder_claude_adapter.py").resolve()
_GOOD_WORKER_RESULT = json.dumps(
    {
        "contract_version": 1,
        "status": "completed",
        "summary": "did it",
        "diff_summary": "changed one file",
        "validation": {"passed": True, "output": "all tests green"},
        "claims": ["implemented p1"],
    }
)
_GOOD_REVIEW_RESULT = json.dumps(
    {
        "contract_version": 1,
        "verdict": "approve",
        "summary": "looks good",
        "findings": [],
    }
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
    return root


def _fake_claude(tmp_path: Path, *, probe_ok: bool = True, worker_ok: bool = True, review_ok: bool = True) -> Path:
    """Fake claude executable that mimics success/failure."""
    fake = tmp_path / "fake-claude"
    # Determine behavior based on prompt content
    fake.write_text(
        f"""#!/bin/sh
# Fake claude for testing
if echo "$*" | grep -q "Reply with exactly: ok"; then
  {"exit 0" if probe_ok else "echo not authenticated >&2; exit 1"}
fi
if echo "$*" | grep -q "KittyBuilder implementation worker"; then
  if [ {"1" if worker_ok else "0"} -eq 1 ]; then
    # Extract result path from prompt (case-insensitive)
    result_path=$(echo "$*" | sed -n 's/.*[Ww]rite a JSON object to \\(.*\\.json\\) with.*/\\1/p' | head -1)
    if [ -n "$result_path" ]; then
      printf '%s' '{_GOOD_WORKER_RESULT}' > "$result_path"
    fi
    exit 0
  else
    exit 1
  fi
fi
if echo "$*" | grep -q "independent, read-only KittyBuilder reviewer"; then
  if [ {"1" if review_ok else "0"} -eq 1 ]; then
    # Extract result path from prompt (case-insensitive)
    result_path=$(echo "$*" | sed -n 's/.*[Ww]rite a JSON object to \\(.*\\.json\\) with.*/\\1/p' | head -1)
    if [ -n "$result_path" ]; then
      printf '%s' '{_GOOD_REVIEW_RESULT}' > "$result_path"
    fi
    exit 0
  else
    exit 1
  fi
fi
exit 1
""",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def _bundle(tmp_path: Path, task_id: str, attempt_id: str) -> tuple[Path, Path, str]:
    """Create minimal bundle + context manifest."""
    bundle_path = tmp_path / "bundle.json"
    manifest_path = tmp_path / "manifest.json"
    bundle = {
        "bundle_version": 1,
        "initiative_id": "test-init",
        "packet_id": "p1",
        "task_id": task_id,
        "attempt_no": 1,
        "objective": "test",
        "acceptance_criteria": ["done"],
        "allowed_paths": ["README.md"],
        "policy": {"max_attempts": 1},
        "validation_commands": ["true"],
        "prior_attempts": [],
    }
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    bundle_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    manifest = {
        "manifest_version": 1,
        "task_id": task_id,
        "attempt_id": int(attempt_id),
        "bundle_sha256": bundle_sha,
        "context": {
            "task_bundle": {
                "sha256": bundle_sha,
            }
        },
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return bundle_path, manifest_path, bundle_sha


def test_worker_success(repo: Path, tmp_path: Path) -> None:
    """Worker with valid env and fake claude writes result."""
    fake = _fake_claude(tmp_path)
    task_id = "task_abc"
    attempt_id = "123"
    bundle_path, manifest_path, _ = _bundle(tmp_path, task_id, attempt_id)
    result_path = tmp_path / "result.json"

    env = os.environ.copy()
    env["KITTYBUILDER_CLAUDE_BIN"] = str(fake)
    env["KITTYBUILDER_CLAUDE_PROBE_TIMEOUT"] = "5"
    env["KB_BUNDLE_PATH"] = str(bundle_path)
    env["KB_RESULT_PATH"] = str(result_path)
    env["KB_CONTEXT_MANIFEST_PATH"] = str(manifest_path)
    env["KB_ATTEMPT_ID"] = attempt_id
    env["KB_TASK_ID"] = task_id

    rc = subprocess.run(
        [sys.executable, str(_ADAPTER), "worker"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    ).returncode

    assert rc == 0
    assert result_path.exists()
    result = json.loads(result_path.read_text())
    assert result["contract_version"] == 1
    assert result["status"] == "completed"
    tracked = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True, check=True).stdout
    assert ".kittybuilder-claude-" not in tracked
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True).stdout
    assert status == ""


def test_worker_missing_claude_exits_75(repo: Path, tmp_path: Path) -> None:
    """Worker with unavailable claude exits 75 without output."""
    task_id = "task_abc"
    attempt_id = "123"
    bundle_path, manifest_path, _ = _bundle(tmp_path, task_id, attempt_id)
    result_path = tmp_path / "result.json"

    env = os.environ.copy()
    env["KITTYBUILDER_CLAUDE_BIN"] = "/nonexistent/claude"
    env["KB_BUNDLE_PATH"] = str(bundle_path)
    env["KB_RESULT_PATH"] = str(result_path)
    env["KB_CONTEXT_MANIFEST_PATH"] = str(manifest_path)
    env["KB_ATTEMPT_ID"] = attempt_id
    env["KB_TASK_ID"] = task_id

    rc = subprocess.run(
        [sys.executable, str(_ADAPTER), "worker"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    ).returncode

    assert rc == 75
    assert not result_path.exists()


def test_worker_probe_fail_exits_75(repo: Path, tmp_path: Path) -> None:
    """Worker probe failure exits 75 without result."""
    fake = _fake_claude(tmp_path, probe_ok=False)
    task_id = "task_abc"
    attempt_id = "123"
    bundle_path, manifest_path, _ = _bundle(tmp_path, task_id, attempt_id)
    result_path = tmp_path / "result.json"

    env = os.environ.copy()
    env["KITTYBUILDER_CLAUDE_BIN"] = str(fake)
    env["KITTYBUILDER_CLAUDE_PROBE_TIMEOUT"] = "5"
    env["KB_BUNDLE_PATH"] = str(bundle_path)
    env["KB_RESULT_PATH"] = str(result_path)
    env["KB_CONTEXT_MANIFEST_PATH"] = str(manifest_path)
    env["KB_ATTEMPT_ID"] = attempt_id
    env["KB_TASK_ID"] = task_id

    rc = subprocess.run(
        [sys.executable, str(_ADAPTER), "worker"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    ).returncode

    assert rc == 75
    assert not result_path.exists()


def test_worker_model_fail_exits_1(repo: Path, tmp_path: Path) -> None:
    """Worker model failure exits 1 (no fallback)."""
    fake = _fake_claude(tmp_path, worker_ok=False)
    task_id = "task_abc"
    attempt_id = "123"
    bundle_path, manifest_path, _ = _bundle(tmp_path, task_id, attempt_id)
    result_path = tmp_path / "result.json"

    env = os.environ.copy()
    env["KITTYBUILDER_CLAUDE_BIN"] = str(fake)
    env["KITTYBUILDER_CLAUDE_PROBE_TIMEOUT"] = "5"
    env["KB_BUNDLE_PATH"] = str(bundle_path)
    env["KB_RESULT_PATH"] = str(result_path)
    env["KB_CONTEXT_MANIFEST_PATH"] = str(manifest_path)
    env["KB_ATTEMPT_ID"] = attempt_id
    env["KB_TASK_ID"] = task_id

    rc = subprocess.run(
        [sys.executable, str(_ADAPTER), "worker"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    ).returncode

    assert rc == 1


def test_reviewer_success(repo: Path, tmp_path: Path) -> None:
    """Reviewer with valid env and no mutation writes review."""
    fake = _fake_claude(tmp_path)
    task_id = "task_abc"
    attempt_id = "123"
    bundle_path, manifest_path, _bundle_sha = _bundle(tmp_path, task_id, attempt_id)
    impl_result_path = tmp_path / "impl.json"
    impl_result_path.write_text(_GOOD_WORKER_RESULT, encoding="utf-8")
    review_result_path = tmp_path / "review.json"

    # Get HEAD sha
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    # Create review context
    review_context = tmp_path / "review_context.json"
    diff_sha = hashlib.sha256(b"").hexdigest()  # empty diff
    review_context.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "attempt_id": int(attempt_id),
                "review_sha": head,
                "diff_sha256": diff_sha,
            }
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["KITTYBUILDER_CLAUDE_BIN"] = str(fake)
    env["KITTYBUILDER_CLAUDE_PROBE_TIMEOUT"] = "5"
    env["KB_BUNDLE_PATH"] = str(bundle_path)
    env["KB_IMPL_RESULT_PATH"] = str(impl_result_path)
    env["KB_REVIEW_RESULT_PATH"] = str(review_result_path)
    env["KB_CONTEXT_MANIFEST_PATH"] = str(manifest_path)
    env["KB_REVIEW_CONTEXT_PATH"] = str(review_context)
    env["KB_REVIEW_SHA"] = head
    env["KB_REVIEW_DIFF_SHA256"] = diff_sha
    env["KB_ATTEMPT_ID"] = attempt_id
    env["KB_TASK_ID"] = task_id

    result = subprocess.run(
        [sys.executable, str(_ADAPTER), "review"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
    assert result.returncode == 0
    assert review_result_path.exists()
    review = json.loads(review_result_path.read_text())
    assert review["contract_version"] == 1
    assert review["verdict"] in {"approve", "request_changes", "reject"}


def test_reviewer_mutated_worktree_fails(repo: Path, tmp_path: Path) -> None:
    """Reviewer that mutates worktree exits 1 without publishing review."""
    # Create a fake claude that writes a file (mutation)
    fake = tmp_path / "mutating-claude"
    fake.write_text(
        f"""#!/bin/sh
if echo "$*" | grep -q "Reply with exactly: ok"; then
  exit 0
fi
if echo "$*" | grep -q "independent, read-only KittyBuilder reviewer"; then
  result_path=$(echo "$*" | sed -n 's/.*[Ww]rite a JSON object to \\(.*\\.json\\) with.*/\\1/p' | head -1)
  if [ -n "$result_path" ]; then
    printf '%s' '{_GOOD_REVIEW_RESULT}' > "$result_path"
  fi
  # Mutate the worktree
  echo "mutation" >> README.md
  exit 0
fi
exit 1
""",
        encoding="utf-8",
    )
    fake.chmod(0o755)

    task_id = "task_abc"
    attempt_id = "123"
    bundle_path, manifest_path, _ = _bundle(tmp_path, task_id, attempt_id)
    impl_result_path = tmp_path / "impl.json"
    impl_result_path.write_text(_GOOD_WORKER_RESULT, encoding="utf-8")
    review_result_path = tmp_path / "review.json"

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    review_context = tmp_path / "review_context.json"
    diff_sha = hashlib.sha256(b"").hexdigest()
    review_context.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "attempt_id": int(attempt_id),
                "review_sha": head,
                "diff_sha256": diff_sha,
            }
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["KITTYBUILDER_CLAUDE_BIN"] = str(fake)
    env["KITTYBUILDER_CLAUDE_PROBE_TIMEOUT"] = "5"
    env["KB_BUNDLE_PATH"] = str(bundle_path)
    env["KB_IMPL_RESULT_PATH"] = str(impl_result_path)
    env["KB_REVIEW_RESULT_PATH"] = str(review_result_path)
    env["KB_CONTEXT_MANIFEST_PATH"] = str(manifest_path)
    env["KB_REVIEW_CONTEXT_PATH"] = str(review_context)
    env["KB_REVIEW_SHA"] = head
    env["KB_REVIEW_DIFF_SHA256"] = diff_sha
    env["KB_ATTEMPT_ID"] = attempt_id
    env["KB_TASK_ID"] = task_id
    note_path = tmp_path / "review-note.md"
    env["KB_REVIEW_NOTE_PATH"] = str(note_path)

    rc = subprocess.run(
        [sys.executable, str(_ADAPTER), "review"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    ).returncode

    assert rc == 1
    # Review should not be published
    assert not review_result_path.exists()
    assert not note_path.exists()



def test_worker_commit_failure_is_reported(repo: Path, tmp_path: Path) -> None:
    fake = _fake_claude(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho hook-rejected >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    task_id, attempt_id = "task_abc", "123"
    bundle_path, manifest_path, _ = _bundle(tmp_path, task_id, attempt_id)
    result_path = tmp_path / "result.json"
    env = os.environ.copy()
    (repo / "README.md").write_text("changed before commit\n", encoding="utf-8")
    env.update({
        "KITTYBUILDER_CLAUDE_BIN": str(fake),
        "KITTYBUILDER_CLAUDE_PROBE_TIMEOUT": "5",
        "KB_BUNDLE_PATH": str(bundle_path),
        "KB_RESULT_PATH": str(result_path),
        "KB_CONTEXT_MANIFEST_PATH": str(manifest_path),
        "KB_ATTEMPT_ID": attempt_id,
        "KB_TASK_ID": task_id,
    })
    result = subprocess.run([sys.executable, str(_ADAPTER), "worker"], cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert "hook-rejected" in result.stderr


def test_non_auth_probe_failure_preserves_context(repo: Path, tmp_path: Path) -> None:
    fake = tmp_path / "bad-probe-claude"
    fake.write_text("#!/bin/sh\necho 'invalid model: bogus' >&2\nexit 2\n", encoding="utf-8")
    fake.chmod(0o755)
    task_id, attempt_id = "task_abc", "123"
    bundle_path, manifest_path, _ = _bundle(tmp_path, task_id, attempt_id)
    result_path = tmp_path / "result.json"
    env = os.environ.copy()
    env.update({
        "KITTYBUILDER_CLAUDE_BIN": str(fake),
        "KITTYBUILDER_CLAUDE_PROBE_TIMEOUT": "5",
        "KB_BUNDLE_PATH": str(bundle_path),
        "KB_RESULT_PATH": str(result_path),
        "KB_CONTEXT_MANIFEST_PATH": str(manifest_path),
        "KB_ATTEMPT_ID": attempt_id,
        "KB_TASK_ID": task_id,
    })
    result = subprocess.run([sys.executable, str(_ADAPTER), "worker"], cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert "invalid model: bogus" in result.stderr
    assert "claude-sonnet-4-5" in result.stderr


def test_silent_probe_failure_is_error_not_provider_unavailable(repo: Path, tmp_path: Path) -> None:
    fake = tmp_path / "silent-probe-claude"
    fake.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
    fake.chmod(0o755)
    task_id, attempt_id = "task_abc", "123"
    bundle_path, manifest_path, _ = _bundle(tmp_path, task_id, attempt_id)
    result_path = tmp_path / "result.json"
    env = os.environ.copy()
    env.update({
        "KITTYBUILDER_CLAUDE_BIN": str(fake),
        "KITTYBUILDER_CLAUDE_PROBE_TIMEOUT": "5",
        "KB_BUNDLE_PATH": str(bundle_path),
        "KB_RESULT_PATH": str(result_path),
        "KB_CONTEXT_MANIFEST_PATH": str(manifest_path),
        "KB_ATTEMPT_ID": attempt_id,
        "KB_TASK_ID": task_id,
    })
    result = subprocess.run(
        [sys.executable, str(_ADAPTER), "worker"],
        cwd=repo, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "exit 2" in result.stderr
    assert "without output" in result.stderr


def test_reviewer_rejects_note_path_inside_worktree(repo: Path, tmp_path: Path) -> None:
    fake = _fake_claude(tmp_path)
    task_id, attempt_id = "task_abc", "123"
    bundle_path, manifest_path, _ = _bundle(tmp_path, task_id, attempt_id)
    impl_result_path = tmp_path / "impl.json"
    impl_result_path.write_text(_GOOD_WORKER_RESULT, encoding="utf-8")
    review_result_path = tmp_path / "review.json"
    note_path = repo / "review-note.md"
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    review_context = tmp_path / "review_context.json"
    diff_sha = hashlib.sha256(b"").hexdigest()
    review_context.write_text(json.dumps({
        "task_id": task_id,
        "attempt_id": int(attempt_id),
        "review_sha": head,
        "diff_sha256": diff_sha,
    }), encoding="utf-8")
    env = os.environ.copy()
    env.update({
        "KITTYBUILDER_CLAUDE_BIN": str(fake),
        "KITTYBUILDER_CLAUDE_PROBE_TIMEOUT": "5",
        "KB_BUNDLE_PATH": str(bundle_path),
        "KB_IMPL_RESULT_PATH": str(impl_result_path),
        "KB_REVIEW_RESULT_PATH": str(review_result_path),
        "KB_CONTEXT_MANIFEST_PATH": str(manifest_path),
        "KB_REVIEW_CONTEXT_PATH": str(review_context),
        "KB_REVIEW_SHA": head,
        "KB_REVIEW_DIFF_SHA256": diff_sha,
        "KB_REVIEW_NOTE_PATH": str(note_path),
        "KB_ATTEMPT_ID": attempt_id,
        "KB_TASK_ID": task_id,
    })
    result = subprocess.run(
        [sys.executable, str(_ADAPTER), "review"], cwd=repo,
        env=env, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "review note path must be outside" in result.stderr.lower()
    assert not review_result_path.exists()
    assert not note_path.exists()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout
    assert status == ""

def test_reviewer_missing_claude_exits_75(repo: Path, tmp_path: Path) -> None:
    """Reviewer with unavailable claude exits 75."""
    task_id = "task_abc"
    attempt_id = "123"
    bundle_path, manifest_path, _ = _bundle(tmp_path, task_id, attempt_id)
    impl_result_path = tmp_path / "impl.json"
    impl_result_path.write_text(_GOOD_WORKER_RESULT, encoding="utf-8")
    review_result_path = tmp_path / "review.json"

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    review_context = tmp_path / "review_context.json"
    diff_sha = hashlib.sha256(b"").hexdigest()
    review_context.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "attempt_id": int(attempt_id),
                "review_sha": head,
                "diff_sha256": diff_sha,
            }
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["KITTYBUILDER_CLAUDE_BIN"] = "/nonexistent/claude"
    env["KB_BUNDLE_PATH"] = str(bundle_path)
    env["KB_IMPL_RESULT_PATH"] = str(impl_result_path)
    env["KB_REVIEW_RESULT_PATH"] = str(review_result_path)
    env["KB_CONTEXT_MANIFEST_PATH"] = str(manifest_path)
    env["KB_REVIEW_CONTEXT_PATH"] = str(review_context)
    env["KB_REVIEW_SHA"] = head
    env["KB_REVIEW_DIFF_SHA256"] = diff_sha
    env["KB_ATTEMPT_ID"] = attempt_id
    env["KB_TASK_ID"] = task_id

    rc = subprocess.run(
        [sys.executable, str(_ADAPTER), "review"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    ).returncode

    assert rc == 75
    assert not review_result_path.exists()
