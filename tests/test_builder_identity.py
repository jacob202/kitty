"""Tests for gateway/builder_identity.py and branch lease enforcement.

Full matrix per spec:
- duplicate packet claim
- duplicate worker claim
- duplicate branch claim
- duplicate worktree claim
- concurrent claim race (threaded)
- branch mismatch
- worktree mismatch
- non-descendant HEAD
- foreign commit
- out-of-scope dirty file
- valid identity
- release and reclaim
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import pytest

from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway.builder_identity import (
    EscalationError,
    verify_and_escalate,
    verify_worker_identity,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

INITIATIVE = "id-test"
PACKET = "ID-1"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    bi.init_db(p)
    return p


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


def _apply_manifest(
    db_path: Path,
    *,
    packet_id: str = PACKET,
    allowed_paths: list[str] | None = None,
) -> str:
    """Apply a one-packet manifest; returns the packet_id."""
    paths = allowed_paths if allowed_paths is not None else ["gateway/a.py"]
    manifest = {
        "manifest_version": 1,
        "initiative_id": INITIATIVE,
        "title": "Identity test",
        "packets": [
            {
                "id": packet_id,
                "title": "Identity packet",
                "objective": "Do the thing.",
                "acceptance_criteria": ["thing done"],
                "allowed_paths": paths,
            }
        ],
    }
    bi.apply_manifest(manifest, db_path=db_path)
    return packet_id


def _head_sha(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _claim(
    db_path: Path,
    *,
    packet_id: str = PACKET,
    worker_id: str = "w-1",
    branch: str = "feat/test",
    worktree_path: str = "/tmp/wt/test",
    base_sha: str = "a" * 40,
) -> dict:
    return bq.claim_branch_lease(
        packet_id, worker_id, branch, worktree_path, base_sha,
        db_path=db_path,
    )


# ---------------------------------------------------------------------------
# Branch lease claim / release / verify
# ---------------------------------------------------------------------------


class TestBranchLease:
    def test_claim_succeeds(self, db_path: Path) -> None:
        lease = _claim(db_path)
        assert lease["packet_id"] == PACKET
        assert lease["worker_id"] == "w-1"
        assert lease["branch"] == "feat/test"

    def test_duplicate_packet_id_conflict(self, db_path: Path) -> None:
        _claim(db_path, packet_id="ID-1")
        with pytest.raises(bq.BranchLeaseConflictError, match="packet_id"):
            _claim(db_path, packet_id="ID-1")

    def test_duplicate_worker_id_conflict(self, db_path: Path) -> None:
        _claim(db_path, packet_id="ID-1", worker_id="w-1")
        with pytest.raises(bq.BranchLeaseConflictError, match="worker_id"):
            _claim(db_path, packet_id="ID-2", worker_id="w-1")

    def test_duplicate_branch_conflict(self, db_path: Path) -> None:
        _claim(db_path, packet_id="ID-1", branch="feat/shared")
        with pytest.raises(bq.BranchLeaseConflictError, match="branch"):
            _claim(
                db_path,
                packet_id="ID-2",
                worker_id="w-2",
                branch="feat/shared",
            )

    def test_duplicate_worktree_conflict(self, db_path: Path) -> None:
        _claim(
            db_path, packet_id="ID-1",
            worktree_path="/tmp/wt/shared",
        )
        with pytest.raises(bq.BranchLeaseConflictError, match="worktree_path"):
            _claim(
                db_path,
                packet_id="ID-2",
                worker_id="w-2",
                branch="feat/other",
                worktree_path="/tmp/wt/shared",
            )

    def test_same_base_sha_allowed(self, db_path: Path) -> None:
        """Multiple packets may legitimately share the same base SHA."""
        _claim(db_path, packet_id="ID-1", base_sha="a" * 40)
        lease2 = _claim(
            db_path,
            packet_id="ID-2",
            worker_id="w-2",
            branch="feat/other",
            worktree_path="/tmp/wt/other",
            base_sha="a" * 40,
        )
        assert lease2["base_sha"] == "a" * 40

    def test_release_and_reclaim(self, db_path: Path) -> None:
        lease = _claim(db_path)
        bq.release_branch_lease(
            lease["lease_id"],
            packet_id=lease["packet_id"],
            worker_id=lease["worker_id"],
            db_path=db_path,
        )
        # All fields are free again.
        lease2 = _claim(db_path)
        assert lease2["packet_id"] == PACKET
        assert lease2["lease_id"] != lease["lease_id"]

    def test_release_nonexistent_lease(self, db_path: Path) -> None:
        with pytest.raises(bq.BranchLeaseConflictError, match="not found"):
            bq.release_branch_lease(
                99999, packet_id="ID-1", worker_id="w-1", db_path=db_path,
            )

    def test_wrong_packet_cannot_release(self, db_path: Path) -> None:
        lease = _claim(db_path, packet_id="ID-1")
        with pytest.raises(bq.BranchLeaseConflictError, match="not found"):
            bq.release_branch_lease(
                lease["lease_id"],
                packet_id="ID-OTHER",
                worker_id=lease["worker_id"],
                db_path=db_path,
            )
        # Lease still intact
        assert bq.verify_branch_lease("ID-1", db_path=db_path) is not None

    def test_wrong_worker_cannot_release(self, db_path: Path) -> None:
        lease = _claim(db_path, worker_id="w-owner")
        with pytest.raises(bq.BranchLeaseConflictError, match="not found"):
            bq.release_branch_lease(
                lease["lease_id"],
                packet_id=lease["packet_id"],
                worker_id="w-impostor",
                db_path=db_path,
            )
        # Lease still intact
        assert bq.verify_branch_lease(lease["packet_id"], db_path=db_path) is not None

    def test_owner_still_can_release_after_failed_cross_release(
        self, db_path: Path
    ) -> None:
        lease = _claim(db_path, packet_id="ID-1", worker_id="w-real")
        with pytest.raises(bq.BranchLeaseConflictError):
            bq.release_branch_lease(
                lease["lease_id"],
                packet_id="ID-FAKE",
                worker_id="w-real",
                db_path=db_path,
            )
        # Rightful owner can still release
        bq.release_branch_lease(
            lease["lease_id"],
            packet_id="ID-1",
            worker_id="w-real",
            db_path=db_path,
        )
        assert bq.verify_branch_lease("ID-1", db_path=db_path) is None

    def test_verify_returns_lease(self, db_path: Path) -> None:
        _claim(db_path)
        result = bq.verify_branch_lease(PACKET, db_path=db_path)
        assert result is not None
        assert result["packet_id"] == PACKET

    def test_verify_returns_none_when_absent(self, db_path: Path) -> None:
        result = bq.verify_branch_lease("NOPE", db_path=db_path)
        assert result is None

    def test_empty_fields_rejected(self, db_path: Path) -> None:
        with pytest.raises(ValueError, match="packet_id"):
            bq.claim_branch_lease(
                "", "w-1", "feat/x", "/tmp/x", "a" * 40, db_path=db_path,
            )


class TestConcurrentClaimRace:
    """Verify that concurrent claim attempts are serialized by BEGIN IMMEDIATE
    and UNIQUE constraints — only one succeeds, the rest get conflicts."""

    def test_only_one_thread_wins(
        self, db_path: Path, tmp_path: Path
    ) -> None:
        _apply_manifest(db_path, packet_id="RACE-1")
        errors: list[BaseException | None] = [None] * 10
        results: list[dict | None] = [None] * 10

        def try_claim(idx: int) -> None:
            try:
                results[idx] = bq.claim_branch_lease(
                    "RACE-1",
                    f"w-{idx}",
                    f"feat/race-{idx}",
                    f"/tmp/wt/race-{idx}",
                    "b" * 40,
                    db_path=db_path,
                )
            except bq.BranchLeaseConflictError as exc:
                errors[idx] = exc
            except Exception as exc:
                errors[idx] = exc

        threads = [threading.Thread(target=try_claim, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [r for r in results if r is not None]
        failures = [e for e in errors if e is not None]
        assert len(successes) == 1, f"expected exactly 1 winner, got {len(successes)}"
        assert len(failures) == 9, f"expected 9 conflicts, got {len(failures)}"


# ---------------------------------------------------------------------------
# Worker identity verification — git checks
# ---------------------------------------------------------------------------


class TestVerifyWorkerIdentity:
    def test_valid_identity_passes(
        self, repo: Path, db_path: Path
    ) -> None:
        """All 6 checks pass: lease exists, worktree matches, branch matches,
        HEAD descends, marker present, files in scope."""
        _apply_manifest(db_path, allowed_paths=["gateway/a.py"])
        base = _head_sha(repo)

        subprocess.run(
            ["git", "checkout", "-q", "-b", "feat/test"], cwd=repo, check=True,
        )
        (repo / "gateway").mkdir(exist_ok=True)
        (repo / "gateway" / "a.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "[ID-1] add a.py"],
            cwd=repo, check=True,
        )

        bq.claim_branch_lease(
            PACKET, "w-1", "feat/test", str(repo), base, db_path=db_path,
        )
        findings = verify_worker_identity(
            PACKET, repo_root=repo, db_path=db_path,
        )
        assert findings == []

    def test_missing_lease_fails(
        self, repo: Path, db_path: Path
    ) -> None:
        _apply_manifest(db_path)
        findings = verify_worker_identity(
            PACKET, repo_root=repo, db_path=db_path,
        )
        assert len(findings) == 1
        assert findings[0].field == "branch_lease"

    def test_worktree_mismatch_fails(
        self, repo: Path, db_path: Path
    ) -> None:
        _apply_manifest(db_path)
        base = _head_sha(repo)
        bq.claim_branch_lease(
            PACKET, "w-1", "main", "/tmp/wrong/worktree", base,
            db_path=db_path,
        )
        findings = verify_worker_identity(
            PACKET, repo_root=repo, db_path=db_path,
        )
        assert any(
            f.category == "identity_violation" and f.field == "worktree_path"
            for f in findings
        )

    def test_branch_mismatch_fails(
        self, repo: Path, db_path: Path
    ) -> None:
        _apply_manifest(db_path)
        base = _head_sha(repo)
        # Claim with worktree matching repo but wrong branch.
        bq.claim_branch_lease(
            PACKET, "w-1", "feat/wrong-branch", str(repo), base,
            db_path=db_path,
        )
        # Repo is on 'main', not 'feat/wrong-branch'.
        findings = verify_worker_identity(
            PACKET, repo_root=repo, db_path=db_path,
        )
        assert any(
            f.category == "identity_violation" and f.field == "branch"
            for f in findings
        )

    def test_non_descendant_head_fails(
        self, repo: Path, db_path: Path
    ) -> None:
        """HEAD is not a descendant of base_sha (force-push or reset)."""
        _apply_manifest(db_path)
        subprocess.run(
            ["git", "checkout", "-q", "-b", "feat/test"], cwd=repo, check=True,
        )
        # Claim with a base_sha that doesn't exist in this branch's history.
        fake_sha = "f" * 40
        bq.claim_branch_lease(
            PACKET, "w-1", "feat/test", str(repo), fake_sha,
            db_path=db_path,
        )
        findings = verify_worker_identity(
            PACKET, repo_root=repo, db_path=db_path,
        )
        assert any(
            f.category == "identity_violation" and f.field == "head"
            for f in findings
        )

    def test_foreign_commit_detected(
        self, repo: Path, db_path: Path
    ) -> None:
        """A commit without the [PACKET-ID] marker is flagged as foreign."""
        _apply_manifest(db_path, allowed_paths=["gateway/a.py"])
        base = _head_sha(repo)

        subprocess.run(
            ["git", "checkout", "-q", "-b", "feat/test"], cwd=repo, check=True,
        )
        (repo / "gateway").mkdir(exist_ok=True)
        (repo / "gateway" / "a.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        # Commit WITHOUT the packet marker.
        subprocess.run(
            ["git", "commit", "-q", "-m", "add a.py without marker"],
            cwd=repo, check=True,
        )

        bq.claim_branch_lease(
            PACKET, "w-1", "feat/test", str(repo), base, db_path=db_path,
        )
        findings = verify_worker_identity(
            PACKET, repo_root=repo, db_path=db_path,
        )
        assert any(
            f.category == "identity_violation" and f.field == "commits"
            for f in findings
        )

    def test_scope_drift_committed_file(
        self, repo: Path, db_path: Path
    ) -> None:
        """A committed file outside allowed_paths is flagged as scope drift."""
        _apply_manifest(db_path, allowed_paths=["gateway/a.py"])
        base = _head_sha(repo)

        subprocess.run(
            ["git", "checkout", "-q", "-b", "feat/test"], cwd=repo, check=True,
        )
        (repo / "gateway").mkdir(exist_ok=True)
        (repo / "gateway" / "a.py").write_text("x = 1\n")
        (repo / "gateway" / "b.py").write_text("y = 2\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "[ID-1] add files"],
            cwd=repo, check=True,
        )

        bq.claim_branch_lease(
            PACKET, "w-1", "feat/test", str(repo), base, db_path=db_path,
        )
        findings = verify_worker_identity(
            PACKET, repo_root=repo, db_path=db_path,
        )
        assert any(
            f.category == "scope_drift" and f.field == "working_tree"
            for f in findings
        )

    def test_scope_drift_untracked_file(
        self, repo: Path, db_path: Path
    ) -> None:
        """An untracked file outside allowed_paths is also flagged."""
        _apply_manifest(db_path, allowed_paths=["gateway/a.py"])
        base = _head_sha(repo)

        subprocess.run(
            ["git", "checkout", "-q", "-b", "feat/test"], cwd=repo, check=True,
        )
        (repo / "gateway").mkdir(exist_ok=True)
        (repo / "gateway" / "a.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "[ID-1] add a.py"],
            cwd=repo, check=True,
        )
        # Untracked file outside scope.
        (repo / "secrets.env").write_text("SECRET=1\n")

        bq.claim_branch_lease(
            PACKET, "w-1", "feat/test", str(repo), base, db_path=db_path,
        )
        findings = verify_worker_identity(
            PACKET, repo_root=repo, db_path=db_path,
        )
        assert any(
            f.category == "scope_drift" and "secrets.env" in f.message
            for f in findings
        )

    def test_multiple_findings_returned(
        self, repo: Path, db_path: Path
    ) -> None:
        """Multiple independent violations are all returned, not just the first."""
        _apply_manifest(db_path, allowed_paths=["gateway/a.py"])
        # Claim with wrong branch AND wrong worktree.
        base = _head_sha(repo)
        bq.claim_branch_lease(
            PACKET, "w-1", "feat/wrong", "/tmp/wrong", base,
            db_path=db_path,
        )
        findings = verify_worker_identity(
            PACKET, repo_root=repo, db_path=db_path,
        )
        fields = {f.field for f in findings}
        assert "worktree_path" in fields
        assert "branch" in fields


# ---------------------------------------------------------------------------
# verify_and_escalate convenience wrapper
# ---------------------------------------------------------------------------


class TestVerifyAndEscalate:
    def test_raises_on_failure(self, repo: Path, db_path: Path) -> None:
        _apply_manifest(db_path)
        with pytest.raises(EscalationError) as exc_info:
            verify_and_escalate(PACKET, repo_root=repo, db_path=db_path)
        assert exc_info.value.artifact["type"] == "identity_escalation"
        assert exc_info.value.artifact["packet_id"] == PACKET

    def test_passes_when_valid(self, repo: Path, db_path: Path) -> None:
        _apply_manifest(db_path, allowed_paths=["gateway/a.py"])
        base = _head_sha(repo)
        subprocess.run(
            ["git", "checkout", "-q", "-b", "feat/test"], cwd=repo, check=True,
        )
        (repo / "gateway").mkdir(exist_ok=True)
        (repo / "gateway" / "a.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "[ID-1] add a.py"],
            cwd=repo, check=True,
        )
        bq.claim_branch_lease(
            PACKET, "w-1", "feat/test", str(repo), base, db_path=db_path,
        )
        # Should not raise.
        verify_and_escalate(PACKET, repo_root=repo, db_path=db_path)
