from __future__ import annotations

import threading
from pathlib import Path

import pytest

from gateway import agent_coordination
from gateway import db as kitty_db

BASE = "a" * 40


def _db(tmp_path: Path) -> Path:
    path = tmp_path / "kitty.db"
    kitty_db.migrate(db_file=path)
    return path


def _claim(db_path: Path, *, session: str, worktree: Path, role: str = "OWN", paths=None, resources=None):
    return agent_coordination.claim(
        participant_id="chatgpt",
        session_id=session,
        role=role,
        lane_id=f"lane-{session}",
        base_sha=BASE,
        branch=f"feat/{session}",
        worktree_path=str(worktree),
        paths=paths or ["gateway/runtime.py"],
        resources=resources or ["runtime:truth"],
        lease_seconds=300,
        db_path=db_path,
    )


def test_conflicting_semantic_mutation_claim_is_rejected(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    _claim(db_path, session="one", worktree=tmp_path / "one")
    with pytest.raises(agent_coordination.CoordinationConflictError, match="runtime:truth"):
        _claim(db_path, session="two", worktree=tmp_path / "two", paths=["gateway/other.py"])


def test_path_ancestry_collision_is_rejected(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    _claim(db_path, session="one", worktree=tmp_path / "one", paths=["gateway"] , resources=["alpha"])
    with pytest.raises(agent_coordination.CoordinationConflictError, match="gateway/runtime.py"):
        _claim(db_path, session="two", worktree=tmp_path / "two", paths=["gateway/runtime.py"], resources=["beta"])


def test_read_only_review_can_coexist_with_owner(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    owner = _claim(db_path, session="one", worktree=tmp_path / "one")
    review = _claim(db_path, session="review", worktree=tmp_path / "review", role="REVIEW")
    assert owner["role"] == "OWN"
    assert review["role"] == "REVIEW"


def test_guard_rejects_path_outside_live_claim(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    worktree = tmp_path / "one"
    _claim(db_path, session="one", worktree=worktree, paths=["gateway/agent_coordination.py"], resources=["coordination:claims"])
    with pytest.raises(agent_coordination.CoordinationClaimError, match="outside claim scope"):
        agent_coordination.guard_paths(str(worktree), ["docs/ROADMAP.md"], db_path=db_path)


def test_guard_accepts_covered_descendant_path(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    worktree = tmp_path / "one"
    _claim(db_path, session="one", worktree=worktree, paths=["gateway"], resources=["coordination:claims"])
    result = agent_coordination.guard_paths(str(worktree), ["gateway/agent_coordination.py"], db_path=db_path)
    assert result["claim"]["session_id"] == "one"
    assert result["paths"] == ["gateway/agent_coordination.py"]


def test_atomic_race_allows_only_one_conflicting_owner(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    barrier = threading.Barrier(2)
    results: list[str] = []

    def runner(session: str) -> None:
        barrier.wait()
        try:
            _claim(db_path, session=session, worktree=tmp_path / session, paths=[f"gateway/{session}.py"])
        except agent_coordination.CoordinationConflictError:
            results.append("conflict")
        else:
            results.append("claimed")

    threads = [threading.Thread(target=runner, args=(name,)) for name in ("one", "two")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == ["claimed", "conflict"]


def _seed_builder_lease(db_path: Path, *, state: str = "running", worktree_path: str = "/tmp/builder-packet-1") -> None:
    import sqlite3

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE tasks (id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE initiative_packets (
                initiative_id TEXT NOT NULL,
                packet_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                allowed_paths_json TEXT NOT NULL,
                PRIMARY KEY (initiative_id, packet_id)
            );
            CREATE TABLE branch_leases (
                lease_id INTEGER PRIMARY KEY,
                initiative_id TEXT NOT NULL,
                packet_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                branch TEXT NOT NULL,
                worktree_path TEXT NOT NULL,
                base_sha TEXT NOT NULL
            );
            """
        )
        conn.execute("INSERT INTO tasks VALUES (?, ?)", ("kb_builder", state))
        conn.execute(
            "INSERT INTO initiative_packets VALUES (?, ?, ?, ?)",
            ("initiative-a", "PACKET-1", "kb_builder", '["gateway/runtime", "tests/runtime"]'),
        )
        conn.execute(
            "INSERT INTO branch_leases VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "initiative-a", "PACKET-1", "dsh-worker", "kittybuilder/packet-1", worktree_path, BASE),
        )
        conn.commit()
    finally:
        conn.close()


def test_builder_branch_lease_projects_as_read_only_coordination_claim(tmp_path: Path) -> None:
    builder_db = tmp_path / "builder.db"
    _seed_builder_lease(builder_db)
    projected = agent_coordination.list_builder_claims(builder_db_path=builder_db)
    assert len(projected) == 1
    assert projected[0]["task_id"] == "kb_builder"
    assert projected[0]["role"] == "OWN"
    assert projected[0]["paths"] == ["gateway/runtime", "tests/runtime"]
    assert projected[0]["resources"] == ["builder:initiative-a/packet-1"]


def test_builder_branch_lease_blocks_overlapping_interactive_mutation(tmp_path: Path) -> None:
    coordination_db = _db(tmp_path / "coordination")
    builder_db = tmp_path / "builder.db"
    _seed_builder_lease(builder_db)
    with pytest.raises(agent_coordination.CoordinationConflictError, match="Builder initiative-a/PACKET-1"):
        agent_coordination.claim(
            participant_id="chatgpt",
            session_id="interactive",
            role="OWN",
            lane_id="runtime-fix",
            base_sha=BASE,
            branch="feat/runtime-fix",
            worktree_path=str(tmp_path / "interactive"),
            paths=["gateway/runtime/doctor.py"],
            resources=["runtime:provenance"],
            db_path=coordination_db,
            builder_db_path=builder_db,
        )


def test_terminal_builder_task_does_not_block_interactive_claim(tmp_path: Path) -> None:
    coordination_db = _db(tmp_path / "coordination")
    builder_db = tmp_path / "builder.db"
    _seed_builder_lease(builder_db, state="done")
    claim = agent_coordination.claim(
        participant_id="chatgpt",
        session_id="interactive",
        role="OWN",
        lane_id="runtime-fix",
        base_sha=BASE,
        branch="feat/runtime-fix",
        worktree_path=str(tmp_path / "interactive"),
        paths=["gateway/runtime/doctor.py"],
        resources=["runtime:provenance"],
        db_path=coordination_db,
        builder_db_path=builder_db,
    )
    assert claim["session_id"] == "interactive"


def test_expired_claim_is_not_active_and_cannot_guard(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    worktree = tmp_path / "expired"
    agent_coordination.claim(
        participant_id="chatgpt",
        session_id="expired",
        role="OWN",
        lane_id="expired-lane",
        base_sha=BASE,
        branch="feat/expired",
        worktree_path=str(worktree),
        paths=["gateway"],
        lease_seconds=10,
        db_path=db_path,
        now=100.0,
    )
    assert agent_coordination.list_claims(db_path=db_path, now=111.0) == []
    with pytest.raises(agent_coordination.CoordinationClaimError, match="0 live mutating claims"):
        agent_coordination.guard_paths(str(worktree), ["gateway/x.py"], db_path=db_path, now=111.0)


def test_renew_and_release_preserve_session_fencing(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    worktree = tmp_path / "lease"
    claim = agent_coordination.claim(
        participant_id="chatgpt",
        session_id="lease-session",
        role="OWN",
        lane_id="lease-lane",
        base_sha=BASE,
        branch="feat/lease",
        worktree_path=str(worktree),
        paths=["gateway"],
        lease_seconds=10,
        db_path=db_path,
        now=100.0,
    )
    renewed = agent_coordination.renew(
        claim["claim_id"], "lease-session", lease_seconds=20, db_path=db_path, now=105.0
    )
    assert renewed["lease_expires_at"] == 125.0
    with pytest.raises(agent_coordination.CoordinationClaimError, match="owned by another session"):
        agent_coordination.release(claim["claim_id"], "other", db_path=db_path, now=106.0)
    released = agent_coordination.release(
        claim["claim_id"], "lease-session", db_path=db_path, now=106.0
    )
    assert released["released_at"] == 106.0
    assert agent_coordination.list_claims(db_path=db_path, now=107.0) == []


def test_blocked_builder_lease_without_recoverable_worktree_is_not_live(tmp_path: Path) -> None:
    builder_db = tmp_path / "builder.db"
    _seed_builder_lease(builder_db, state="blocked", worktree_path=str(tmp_path / "missing"))
    assert agent_coordination.list_builder_claims(builder_db_path=builder_db) == []


def test_blocked_builder_lease_with_recoverable_worktree_still_blocks(tmp_path: Path) -> None:
    builder_db = tmp_path / "builder.db"
    recoverable = tmp_path / "builder-worktree"
    recoverable.mkdir()
    _seed_builder_lease(builder_db, state="blocked", worktree_path=str(recoverable))
    projected = agent_coordination.list_builder_claims(builder_db_path=builder_db)
    assert len(projected) == 1
    assert projected[0]["state"] == "blocked"
    assert projected[0]["worktree_path"] == str(recoverable.resolve())
