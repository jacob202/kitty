from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/work_claim.py"
HOOK = ROOT / ".githooks/pre-commit"


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd, capture_output=True, text=True, check=False,
    )


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def worktrees(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Kitty Test")
    _git(repo, "config", "user.email", "kitty@example.invalid")
    (repo / "gateway").mkdir()
    (repo / "docs").mkdir()
    (repo / "gateway" / "a.py").write_text("x = 1\n")
    (repo / "docs" / "note.md").write_text("start\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")

    first = tmp_path / "first"
    second = tmp_path / "second"
    _git(repo, "worktree", "add", "-b", "first", str(first), "main")
    _git(repo, "worktree", "add", "-b", "second", str(second), "main")
    return repo, first, second


@pytest.mark.parametrize("ttl", ["nan", "inf", "-inf"])
def test_claim_rejects_non_finite_ttl(
    worktrees: tuple[Path, Path, Path], ttl: str,
) -> None:
    _repo, first, _second = worktrees

    result = _run(
        first, "claim", "--owner", "alpha", "--task", "invalid-ttl",
        "--path", "gateway", f"--ttl-minutes={ttl}",
    )

    assert result.returncode == 2
    assert "ttl-minutes must be finite" in result.stderr


def test_renew_rejects_non_finite_ttl(
    worktrees: tuple[Path, Path, Path],
) -> None:
    _repo, first, _second = worktrees
    claimed = _run(
        first, "claim", "--owner", "alpha", "--task", "renew",
        "--path", "gateway",
    )
    assert claimed.returncode == 0, claimed.stderr

    for ttl in ("nan", "inf", "-inf"):
        renewed = _run(first, "renew", f"--ttl-minutes={ttl}")
        assert renewed.returncode == 2
        assert "ttl-minutes must be finite" in renewed.stderr


def test_claim_and_renew_reject_excessive_finite_ttl(
    worktrees: tuple[Path, Path, Path],
) -> None:
    _repo, first, _second = worktrees

    claimed = _run(
        first, "claim", "--owner", "alpha", "--task", "too-long",
        "--path", "gateway", "--ttl-minutes", "1e308",
    )
    assert claimed.returncode == 2
    assert "no more than" in claimed.stderr

    normal = _run(
        first, "claim", "--owner", "alpha", "--task", "renew-too-long",
        "--path", "gateway",
    )
    assert normal.returncode == 0, normal.stderr
    renewed = _run(first, "renew", "--ttl-minutes", "1e308")
    assert renewed.returncode == 2
    assert "no more than" in renewed.stderr


def test_overlapping_claim_is_blocked_but_parallel_scope_is_allowed(
    worktrees: tuple[Path, Path, Path],
) -> None:
    _repo, first, second = worktrees
    one = _run(
        first, "claim", "--owner", "alpha", "--task", "one",
        "--path", "gateway",
    )
    assert one.returncode == 0, one.stderr

    overlap = _run(
        second, "claim", "--owner", "beta", "--task", "two",
        "--path", "gateway/routes",
    )
    assert overlap.returncode == 2
    assert "ownership conflict with alpha" in overlap.stderr

    parallel = _run(
        second, "claim", "--owner", "beta", "--task", "two",
        "--path", "docs",
    )
    assert parallel.returncode == 0, parallel.stderr


def test_extend_adds_scope_without_releasing_existing_claim(
    worktrees: tuple[Path, Path, Path],
) -> None:
    _repo, first, _second = worktrees
    claimed = _run(
        first, "claim", "--owner", "alpha", "--task", "grow",
        "--path", "gateway",
    )
    assert claimed.returncode == 0, claimed.stderr
    claim_id = json.loads(claimed.stdout)["claim_id"]

    extended = _run(first, "extend", "--path", "docs")

    assert extended.returncode == 0, extended.stderr
    payload = json.loads(extended.stdout)
    assert payload["claim_id"] == claim_id
    assert payload["paths"] == ["docs", "gateway"]


def test_extend_conflict_is_atomic_and_preserves_existing_scope(
    worktrees: tuple[Path, Path, Path],
) -> None:
    _repo, first, second = worktrees
    first_claim = _run(
        first, "claim", "--owner", "alpha", "--task", "grow",
        "--path", "gateway",
    )
    assert first_claim.returncode == 0, first_claim.stderr
    second_claim = _run(
        second, "claim", "--owner", "beta", "--task", "parallel",
        "--path", "docs",
    )
    assert second_claim.returncode == 0, second_claim.stderr

    blocked = _run(first, "extend", "--path", "docs")
    assert blocked.returncode == 2
    assert "ownership conflict with beta" in blocked.stderr

    status = json.loads(_run(first, "status").stdout)["claims"]
    alpha = next(claim for claim in status if claim["owner"] == "alpha")
    assert alpha["state"] == "active"
    assert alpha["paths"] == ["gateway"]


def test_expired_claim_is_visible_and_does_not_block_recovery(
    worktrees: tuple[Path, Path, Path],
) -> None:
    _repo, first, second = worktrees
    created = _run(
        first, "claim", "--owner", "alpha", "--task", "short",
        "--path", "gateway", "--ttl-minutes", "0.0002",
    )
    assert created.returncode == 0, created.stderr
    time.sleep(0.05)
    status = _run(second, "status")
    assert status.returncode == 0
    claims = json.loads(status.stdout)["claims"]
    assert claims[0]["state"] == "stale"

    recovered = _run(
        second, "claim", "--owner", "beta", "--task", "recovery",
        "--path", "gateway/routes",
    )
    assert recovered.returncode == 0, recovered.stderr

    reaped = _run(second, "reap")
    assert reaped.returncode == 0
    assert json.loads(reaped.stdout)["reaped"]


def test_preflight_requires_claim_coverage(
    worktrees: tuple[Path, Path, Path],
) -> None:
    _repo, first, _second = worktrees
    claimed = _run(
        first, "claim", "--owner", "alpha", "--task", "edit",
        "--path", "gateway",
    )
    assert claimed.returncode == 0, claimed.stderr

    (first / "gateway" / "a.py").write_text("x = 2\n")
    _git(first, "add", "gateway/a.py")
    allowed = _run(first, "preflight", "--staged")
    assert allowed.returncode == 0, allowed.stderr

    (first / "docs" / "note.md").write_text("changed\n")
    _git(first, "add", "docs/note.md")
    blocked = _run(first, "preflight", "--staged")
    assert blocked.returncode == 2
    assert "outside claim" in blocked.stderr


def test_preflight_blocks_typechange_outside_claim(
    worktrees: tuple[Path, Path, Path],
) -> None:
    _repo, first, _second = worktrees
    claimed = _run(
        first, "claim", "--owner", "alpha", "--task", "typechange",
        "--path", "gateway",
    )
    assert claimed.returncode == 0, claimed.stderr

    note = first / "docs" / "note.md"
    note.unlink()
    note.symlink_to("../gateway/a.py")
    _git(first, "add", "docs/note.md")

    blocked = _run(first, "preflight", "--staged")

    assert blocked.returncode == 2
    assert "docs/note.md" in blocked.stderr
    assert "outside claim" in blocked.stderr


def test_preflight_supports_initial_commit_with_covering_claim(tmp_path: Path) -> None:
    repo = tmp_path / "new-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Kitty Test")
    _git(repo, "config", "user.email", "kitty@example.invalid")
    (repo / "scripts").mkdir()
    (repo / ".githooks").mkdir()
    (repo / "scripts" / "work_claim.py").write_bytes(SCRIPT.read_bytes())
    (repo / ".githooks" / "pre-commit").write_bytes(HOOK.read_bytes())
    (repo / ".githooks" / "pre-commit").chmod(0o755)
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    _git(repo, "config", "core.hooksPath", ".githooks")
    _git(repo, "add", ".")

    claim = subprocess.run(
        [
            sys.executable, str(repo / "scripts/work_claim.py"), "claim",
            "--owner", "alpha", "--task", "initial", "--path", ".",
        ],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    assert claim.returncode == 0, claim.stderr

    commit = subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    assert commit.returncode == 0, commit.stdout + commit.stderr


def test_release_allows_another_owner_to_take_same_scope(
    worktrees: tuple[Path, Path, Path],
) -> None:
    _repo, first, second = worktrees
    claimed = _run(
        first, "claim", "--owner", "alpha", "--task", "one",
        "--path", "gateway",
    )
    assert claimed.returncode == 0
    released = _run(first, "release")
    assert released.returncode == 0

    next_owner = _run(
        second, "claim", "--owner", "beta", "--task", "two",
        "--path", "gateway",
    )
    assert next_owner.returncode == 0, next_owner.stderr


def test_claim_state_is_shared_across_linked_worktrees(
    worktrees: tuple[Path, Path, Path],
) -> None:
    _repo, first, second = worktrees
    claimed = _run(
        first, "claim", "--owner", "alpha", "--task", "shared",
        "--path", "gateway",
    )
    assert claimed.returncode == 0
    status = _run(second, "status")
    claims = json.loads(status.stdout)["claims"]
    assert len(claims) == 1
    assert claims[0]["owner"] == "alpha"
    assert claims[0]["worktree"] == str(first.resolve())
