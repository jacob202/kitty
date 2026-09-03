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
