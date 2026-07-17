"""Branch-lease ownership and post-worker Git identity tests."""

from __future__ import annotations

import sqlite3
import subprocess
import threading
from pathlib import Path

import pytest

from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway.builder_identity import verify_and_escalate, verify_worker_identity
from gateway.builder_scope import EscalationError

INITIATIVE = "identity-test"
PACKET = "ID-1"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "kittybuilder" / "builder_queue.db"
    bi.init_db(path)
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
    return root


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _apply(
    db_path: Path,
    *,
    initiative_id: str = INITIATIVE,
    packet_id: str = PACKET,
    allowed_paths: list[str] | None = None,
) -> None:
    bi.apply_manifest(
        {
            "manifest_version": 1,
            "initiative_id": initiative_id,
            "title": "Identity test",
            "packets": [
                {
                    "id": packet_id,
                    "title": "Identity packet",
                    "objective": "Implement the bounded packet.",
                    "acceptance_criteria": ["bounded change exists"],
                    "allowed_paths": allowed_paths or ["gateway/a.py"],
                }
            ],
        },
        db_path=db_path,
    )


def _claim(
    db_path: Path,
    *,
    packet_id: str = PACKET,
    worker_id: str = "worker-1",
    branch: str = "feat/identity",
    worktree_path: str = "/tmp/kitty-identity",
    base_sha: str = "a" * 40,
) -> dict:
    return bq.claim_branch_lease(
        packet_id,
        worker_id,
        branch,
        worktree_path,
        base_sha,
        db_path=db_path,
    )


class TestBranchLease:
    def test_partial_phase2_database_migrates_worker_uniqueness(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "legacy.db"
        with sqlite3.connect(path) as conn:
            conn.execute(
                """
                CREATE TABLE branch_leases (
                    lease_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    packet_id TEXT NOT NULL UNIQUE,
                    worker_id TEXT NOT NULL,
                    branch TEXT NOT NULL UNIQUE,
                    worktree_path TEXT NOT NULL UNIQUE,
                    base_sha TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        bq.init_db(path)
        _claim(path, packet_id="ID-1", worker_id="shared-worker")
        with pytest.raises(bq.BranchLeaseConflictError, match="worker_id"):
            _claim(
                path,
                packet_id="ID-2",
                worker_id="shared-worker",
                branch="feat/other",
                worktree_path="/tmp/other",
            )

    def test_partial_phase2_duplicate_workers_fail_migration_loudly(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "corrupt-legacy.db"
        with sqlite3.connect(path) as conn:
            conn.execute(
                """
                CREATE TABLE branch_leases (
                    lease_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    packet_id TEXT NOT NULL UNIQUE,
                    worker_id TEXT NOT NULL,
                    branch TEXT NOT NULL UNIQUE,
                    worktree_path TEXT NOT NULL UNIQUE,
                    base_sha TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.executemany(
                "INSERT INTO branch_leases "
                "(packet_id, worker_id, branch, worktree_path, base_sha) "
                "VALUES (?, 'duplicate-worker', ?, ?, ?)",
                [
                    ("ID-1", "feat/one", "/tmp/one", "a" * 40),
                    ("ID-2", "feat/two", "/tmp/two", "a" * 40),
                ],
            )
        with pytest.raises(sqlite3.IntegrityError):
            bq.init_db(path)

    def test_claim_canonicalizes_worktree(self, db_path: Path) -> None:
        lease = _claim(db_path, worktree_path="/tmp/kitty-identity/.")
        assert lease["worktree_path"] == str(Path("/tmp/kitty-identity").resolve())

    @pytest.mark.parametrize(
        ("field", "overrides"),
        [
            ("packet_id", {"packet_id": PACKET}),
            ("worker_id", {"packet_id": "ID-2", "worker_id": "worker-1"}),
            (
                "branch",
                {
                    "packet_id": "ID-2",
                    "worker_id": "worker-2",
                    "branch": "feat/identity",
                },
            ),
            (
                "worktree_path",
                {
                    "packet_id": "ID-2",
                    "worker_id": "worker-2",
                    "branch": "feat/other",
                    "worktree_path": "/tmp/kitty-identity/.",
                },
            ),
        ],
    )
    def test_duplicate_identity_fields_conflict(
        self, db_path: Path, field: str, overrides: dict[str, str]
    ) -> None:
        _claim(db_path)
        with pytest.raises(bq.BranchLeaseConflictError, match=field):
            _claim(db_path, **overrides)

    def test_base_sha_is_not_unique(self, db_path: Path) -> None:
        _claim(db_path)
        second = _claim(
            db_path,
            packet_id="ID-2",
            worker_id="worker-2",
            branch="feat/other",
            worktree_path="/tmp/kitty-other",
        )
        assert second["base_sha"] == "a" * 40

    def test_release_requires_exact_owner(self, db_path: Path) -> None:
        lease = _claim(db_path)
        with pytest.raises(bq.BranchLeaseConflictError):
            bq.release_branch_lease(
                lease["lease_id"],
                packet_id=PACKET,
                worker_id="impostor",
                db_path=db_path,
            )
        assert bq.verify_branch_lease(PACKET, db_path=db_path) is not None
        bq.release_branch_lease(
            lease["lease_id"],
            packet_id=PACKET,
            worker_id="worker-1",
            db_path=db_path,
        )
        assert bq.verify_branch_lease(PACKET, db_path=db_path) is None

    def test_double_release_fails_loud(self, db_path: Path) -> None:
        lease = _claim(db_path)
        kwargs = {
            "packet_id": PACKET,
            "worker_id": "worker-1",
            "db_path": db_path,
        }
        bq.release_branch_lease(lease["lease_id"], **kwargs)
        with pytest.raises(bq.BranchLeaseConflictError):
            bq.release_branch_lease(lease["lease_id"], **kwargs)

    def test_concurrent_claim_has_one_winner(self, db_path: Path) -> None:
        results: list[dict | None] = [None] * 8
        errors: list[BaseException | None] = [None] * 8

        def claim(index: int) -> None:
            try:
                results[index] = _claim(
                    db_path,
                    worker_id=f"worker-{index}",
                    branch=f"feat/{index}",
                    worktree_path=f"/tmp/kitty-{index}",
                )
            except BaseException as exc:
                errors[index] = exc

        threads = [threading.Thread(target=claim, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sum(result is not None for result in results) == 1
        assert all(
            error is None or isinstance(error, bq.BranchLeaseConflictError)
            for error in errors
        )


class TestWorkerIdentity:
    def _valid_identity(self, repo: Path, db_path: Path) -> dict:
        _apply(db_path)
        base_sha = _head(repo)
        subprocess.run(
            ["git", "checkout", "-q", "-b", "feat/identity"],
            cwd=repo,
            check=True,
        )
        (repo / "gateway").mkdir()
        (repo / "gateway" / "a.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "[ID-1] add a.py"],
            cwd=repo,
            check=True,
        )
        return bq.claim_branch_lease(
            PACKET,
            "worker-1",
            "feat/identity",
            str(repo),
            base_sha,
            db_path=db_path,
        )

    def test_valid_identity_passes(self, repo: Path, db_path: Path) -> None:
        lease = self._valid_identity(repo, db_path)
        assert verify_worker_identity(
            PACKET,
            repo_root=repo,
            db_path=db_path,
            expected_lease_id=lease["lease_id"],
            expected_worker_id="worker-1",
            expected_branch="feat/identity",
            expected_worktree_path=str(repo),
            expected_base_sha=lease["base_sha"],
        ) == []

    def test_expected_worker_drift_fails(self, repo: Path, db_path: Path) -> None:
        self._valid_identity(repo, db_path)
        findings = verify_worker_identity(
            PACKET,
            repo_root=repo,
            db_path=db_path,
            expected_worker_id="worker-2",
        )
        assert any(finding.field == "worker_id" for finding in findings)

    def test_worktree_and_branch_mismatch_fail(
        self, repo: Path, db_path: Path
    ) -> None:
        _apply(db_path)
        _claim(
            db_path,
            branch="feat/wrong",
            worktree_path="/tmp/wrong",
            base_sha=_head(repo),
        )
        findings = verify_worker_identity(
            PACKET, repo_root=repo, db_path=db_path
        )
        assert {finding.field for finding in findings} >= {
            "branch",
            "worktree_path",
        }

    def test_invalid_base_sha_fails_closed(self, repo: Path, db_path: Path) -> None:
        _apply(db_path)
        _claim(
            db_path,
            branch="main",
            worktree_path=str(repo),
            base_sha="f" * 40,
        )
        findings = verify_worker_identity(
            PACKET, repo_root=repo, db_path=db_path
        )
        assert any(finding.field == "head" for finding in findings)

    def test_foreign_commit_fails(self, repo: Path, db_path: Path) -> None:
        _apply(db_path)
        base_sha = _head(repo)
        subprocess.run(
            ["git", "checkout", "-q", "-b", "feat/identity"],
            cwd=repo,
            check=True,
        )
        (repo / "gateway").mkdir()
        (repo / "gateway" / "a.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "unmarked commit"],
            cwd=repo,
            check=True,
        )
        bq.claim_branch_lease(
            PACKET,
            "worker-1",
            "feat/identity",
            str(repo),
            base_sha,
            db_path=db_path,
        )
        findings = verify_worker_identity(
            PACKET, repo_root=repo, db_path=db_path
        )
        assert any(finding.field == "commits" for finding in findings)

    def test_unmarked_merge_commit_fails(self, repo: Path, db_path: Path) -> None:
        self._valid_identity(repo, db_path)
        subprocess.run(
            ["git", "checkout", "-q", "-b", "feat/side"],
            cwd=repo,
            check=True,
        )
        (repo / "gateway" / "a.py").write_text("x = 2\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "[ID-1] side change"],
            cwd=repo,
            check=True,
        )
        subprocess.run(
            ["git", "checkout", "-q", "feat/identity"],
            cwd=repo,
            check=True,
        )
        subprocess.run(
            ["git", "merge", "-q", "--no-ff", "feat/side", "-m", "merge side"],
            cwd=repo,
            check=True,
        )

        findings = verify_worker_identity(
            PACKET, repo_root=repo, db_path=db_path
        )

        assert any(
            finding.field == "commits" and "merge side" in finding.message
            for finding in findings
        )

    def test_untracked_scope_drift_fails(self, repo: Path, db_path: Path) -> None:
        lease = self._valid_identity(repo, db_path)
        (repo / "secret.txt").write_text("outside\n", encoding="utf-8")
        findings = verify_worker_identity(
            PACKET,
            repo_root=repo,
            db_path=db_path,
            expected_lease_id=lease["lease_id"],
        )
        assert any(finding.category == "scope_drift" for finding in findings)

    @pytest.mark.parametrize("stored", ["{", "{}", "[]", '["."]'])
    def test_corrupt_or_unbounded_allowlist_fails_closed(
        self, repo: Path, db_path: Path, stored: str
    ) -> None:
        lease = self._valid_identity(repo, db_path)
        with bq.connect(db_path) as conn:
            conn.execute(
                "UPDATE initiative_packets SET allowed_paths_json = ? "
                "WHERE packet_id = ?",
                (stored, PACKET),
            )
            conn.commit()
        findings = verify_worker_identity(
            PACKET,
            repo_root=repo,
            db_path=db_path,
            expected_lease_id=lease["lease_id"],
        )
        assert any(finding.field == "allowed_paths" for finding in findings)

    def test_duplicate_packet_ids_make_identity_ambiguous(
        self, repo: Path, db_path: Path
    ) -> None:
        lease = self._valid_identity(repo, db_path)
        _apply(db_path, initiative_id="identity-test-2", packet_id=PACKET)
        findings = verify_worker_identity(
            PACKET,
            repo_root=repo,
            db_path=db_path,
            expected_lease_id=lease["lease_id"],
        )
        assert any(finding.field == "allowed_paths" for finding in findings)

    def test_verify_and_escalate_returns_structured_artifact(
        self, repo: Path, db_path: Path
    ) -> None:
        _apply(db_path)
        with pytest.raises(EscalationError) as exc_info:
            verify_and_escalate(PACKET, repo_root=repo, db_path=db_path)
        assert exc_info.value.artifact["type"] == "identity_escalation"
