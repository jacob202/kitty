from __future__ import annotations

import glob
import multiprocessing as mp
import sqlite3
from pathlib import Path

import pytest
import yaml

from gateway import agent_coordination, agent_room_cli, agent_workspace

ROOT = Path(__file__).resolve().parents[1]
TRACKED_REGISTRY = ROOT / "coordination/resources.yaml"
BASE = "a" * 40
T0 = "2026-09-03T12:00:00+00:00"
T1 = "2026-09-03T12:00:02+00:00"
REQUIRED_RESOURCES = {
    "builder:initiative-lifecycle",
    "builder:queue-reconciliation",
    "runtime:provenance",
    "ui:action-grammar",
    "docs:roadmap",
    "memory:continuity",
    "image-lab:generation",
}


def _write_registry(path: Path) -> Path:
    path.write_text(
        """resources:
  runtime:provenance:
    paths:
      - gateway/routes/runtime.py
      - gateway/runtime_manifest.py
  docs:roadmap:
    paths:
      - docs/ROADMAP.md
  memory:continuity:
    paths:
      - gateway/memory*.py
""",
        encoding="utf-8",
    )
    return path


def _acquire(
    db_path: Path,
    registry_path: Path,
    *,
    session: str,
    resource: str = "runtime:provenance",
    role: str = "OWN",
    paths: tuple[str, ...] = ("gateway/**",),
    now: str = T0,
    lease_seconds: int = 2700,
    worktree: str | None = None,
):
    return agent_coordination.acquire(
        session_id=session,
        participant="chatgpt",
        role=role,
        resource_id=resource,
        lane=f"lane-{session}",
        task_id=f"task-{session}",
        branch=f"feat/{session}",
        worktree=worktree or f"/tmp/{session}",
        base_sha=BASE,
        paths=paths,
        lease_seconds=lease_seconds,
        db_path=db_path,
        registry_path=registry_path,
        now=now,
    )


def _race_worker(
    db_path: str,
    registry_path: str,
    session: str,
    start_event,
    result_queue,
) -> None:
    start_event.wait(10)
    try:
        result = agent_coordination.acquire(
            session_id=session,
            participant="chatgpt",
            role="OWN",
            resource_id="runtime:provenance",
            lane="race",
            task_id=None,
            branch=f"feat/{session}",
            worktree=f"/tmp/{session}",
            base_sha=BASE,
            paths=("gateway/**",),
            db_path=Path(db_path),
            registry_path=Path(registry_path),
            now=T0,
        )
    except Exception as exc:
        result_queue.put({"session": session, "error": f"{type(exc).__name__}: {exc}"})
        return
    result_queue.put(
        {
            "session": session,
            "status": result["status"],
            "holder": (result.get("holder") or {}).get("session_id"),
        }
    )


@pytest.fixture
def store(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "coordination.db", _write_registry(tmp_path / "resources.yaml")


def test_own_vs_own_race_has_one_database_winner(store: tuple[Path, Path]) -> None:
    """Acceptance 1: independent OS processes cannot both own one resource."""
    db_path, registry_path = store
    assert not db_path.exists(), "race must start from a brand-new store"

    ctx = mp.get_context("spawn")
    start_event = ctx.Event()
    result_queue = ctx.Queue()
    processes = [
        ctx.Process(
            target=_race_worker,
            args=(str(db_path), str(registry_path), session, start_event, result_queue),
        )
        for session in ("race-one", "race-two")
    ]
    for process in processes:
        process.start()
    start_event.set()
    results = [result_queue.get(timeout=15) for _ in processes]
    for process in processes:
        process.join(timeout=15)
        assert process.exitcode == 0

    assert all("error" not in item for item in results), results
    winners = [item for item in results if item["status"] == "ACQUIRED"]
    losers = [item for item in results if item["status"] == "CONFLICT"]
    assert len(winners) == 1
    assert len(losers) == 1
    assert losers[0]["holder"] == winners[0]["session"]


def test_own_and_review_can_coexist(store: tuple[Path, Path]) -> None:
    """Acceptance 2: REVIEW is outside the mutating-resource mutex."""
    db_path, registry_path = store
    owner = _acquire(db_path, registry_path, session="owner")
    reviewer = _acquire(db_path, registry_path, session="reviewer", role="REVIEW", paths=())
    assert owner["status"] == "ACQUIRED"
    assert reviewer["status"] == "ACQUIRED"


def test_expired_owner_is_rejected_after_transfer(store: tuple[Path, Path]) -> None:
    """Acceptance 3: an expired owner cannot mutate after a new owner acquires."""
    db_path, registry_path = store
    first = _acquire(
        db_path,
        registry_path,
        session="old-owner",
        lease_seconds=1,
        paths=("gateway/**",),
    )
    assert first["status"] == "ACQUIRED"
    second = _acquire(
        db_path,
        registry_path,
        session="new-owner",
        now=T1,
        paths=("gateway/**",),
    )
    assert second["status"] == "ACQUIRED"

    stale = agent_coordination.preflight_mutation(
        "old-owner",
        ["gateway/runtime_manifest.py"],
        db_path=db_path,
        registry_path=registry_path,
        now=T1,
    )
    assert stale["ok"] is False
    assert "active" in stale["reason"].lower() or "expired" in stale["reason"].lower()


def test_path_fence_rejects_staged_path_outside_declared_globs(store: tuple[Path, Path]) -> None:
    """Acceptance 4: literal claim paths are an independent mutation fence."""
    db_path, registry_path = store
    assert _acquire(
        db_path,
        registry_path,
        session="path-owner",
        resource="docs:roadmap",
        paths=("docs/ROADMAP.md",),
    )["status"] == "ACQUIRED"
    result = agent_coordination.preflight_mutation(
        "path-owner",
        ["gateway/runtime_manifest.py"],
        db_path=db_path,
        registry_path=registry_path,
        now=T0,
    )
    assert result["ok"] is False
    assert "path" in result["reason"].lower()


def test_semantic_fence_rejects_unclaimed_resource_inside_literal_fence(store: tuple[Path, Path]) -> None:
    """Acceptance 5: a broad literal fence cannot bypass semantic ownership."""
    db_path, registry_path = store
    assert _acquire(
        db_path,
        registry_path,
        session="semantic-owner",
        resource="docs:roadmap",
        paths=("gateway/**", "docs/**"),
    )["status"] == "ACQUIRED"
    result = agent_coordination.preflight_mutation(
        "semantic-owner",
        ["gateway/runtime_manifest.py"],
        db_path=db_path,
        registry_path=registry_path,
        now=T0,
    )
    assert result["ok"] is False
    assert "runtime:provenance" in result["reason"]



def test_unmapped_path_is_fail_closed_for_all_mutating_owners(store: tuple[Path, Path]) -> None:
    """A registry coverage gap cannot become a shared mutation escape hatch."""
    db_path, registry_path = store
    one = _acquire(
        db_path, registry_path, session="alpha-owner", resource="runtime:provenance",
        paths=("scratch/**",),
    )
    two = _acquire(
        db_path, registry_path, session="beta-owner", resource="docs:roadmap",
        paths=("scratch/**",),
    )
    assert one["status"] == two["status"] == "ACQUIRED"
    for session in ("alpha-owner", "beta-owner"):
        result = agent_coordination.preflight_mutation(
            session, ["scratch/unmapped.py"], db_path=db_path,
            registry_path=registry_path, now=T0,
        )
        assert result["ok"] is False
        assert "registered semantic resource" in result["reason"]

def test_force_release_frees_resource_and_projects_event(
    store: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 6: force-release is break-glass, durable, and visible in GAR."""
    db_path, registry_path = store
    gar_db = tmp_path / "gar.db"
    monkeypatch.setattr(agent_workspace, "WORKSPACE_DB_FILE", gar_db)

    assert _acquire(db_path, registry_path, session="stuck-owner")["status"] == "ACQUIRED"
    forced = agent_coordination.force_release(
        "stuck-owner",
        "interactive session disappeared",
        participant="chatgpt",
        db_path=db_path,
        now=T0,
    )
    assert forced["released"] == 1
    assert _acquire(db_path, registry_path, session="replacement")["status"] == "ACQUIRED"

    messages = agent_workspace.list_messages(agent_workspace.GLOBAL_WORKSPACE_ID, limit=20)
    assert any(
        "COORDINATION FORCE RELEASE" in message["content"]
        and "stuck-owner" in message["content"]
        and "interactive session disappeared" in message["content"]
        for message in messages
    )


def test_unregistered_resource_is_rejected(store: tuple[Path, Path]) -> None:
    """Acceptance 7: agents cannot mint semantic resource IDs at runtime."""
    db_path, registry_path = store
    with pytest.raises(agent_coordination.CoordinationClaimError, match="registered"):
        _acquire(
            db_path,
            registry_path,
            session="inventor",
            resource="runtime:made-up-resource",
        )


def test_store_is_wal_and_mutex_is_a_partial_unique_index(store: tuple[Path, Path]) -> None:
    """The database itself, not a process-local lock, owns mutating exclusion."""
    db_path, registry_path = store
    acquired = _acquire(db_path, registry_path, session="schema-owner")
    assert acquired["status"] == "ACQUIRED"
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='claims'"
        ).fetchone()[0]
        index_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_claims_active_mutator_resource'"
        ).fetchone()[0]
    assert "state" in table_sql
    assert "role" in table_sql
    normalized = " ".join(index_sql.lower().split())
    assert "unique index" in normalized
    assert "resource_id" in normalized
    assert "where state = 'active'" in normalized
    assert "role in ('own','integrate')" in normalized.replace(" ", "") or "rolein('own','integrate')" in normalized.replace(" ", "")


def test_registry_seed_is_exact_deterministic_and_points_at_real_tree() -> None:
    data = yaml.safe_load(TRACKED_REGISTRY.read_text(encoding="utf-8"))
    assert REQUIRED_RESOURCES <= set(data["resources"])
    for resource_id, spec in data["resources"].items():
        paths = spec["paths"]
        assert paths == sorted(paths), f"{resource_id} paths must be deterministic"
        assert paths, f"{resource_id} must own at least one real path"
        for pattern in paths:
            matches = [Path(item) for item in glob.glob(str(ROOT / pattern), recursive=True)]
            assert any(match.exists() for match in matches), f"{resource_id}: {pattern} matches nothing"

    one = agent_coordination.resolve_paths_to_resources(
        ["gateway/runtime_manifest.py", "docs/ROADMAP.md"],
        registry_path=TRACKED_REGISTRY,
    )
    two = agent_coordination.resolve_paths_to_resources(
        ["docs/ROADMAP.md", "gateway/runtime_manifest.py"],
        registry_path=TRACKED_REGISTRY,
    )
    assert one == two == ["docs:roadmap", "runtime:provenance"]


def test_gar_heartbeat_renews_matching_coordination_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "coordination.db"
    registry_path = _write_registry(tmp_path / "resources.yaml")
    gar_db = tmp_path / "gar.db"
    monkeypatch.setenv("KITTY_COORDINATION_DB", str(db_path))
    monkeypatch.setenv("KITTY_COORDINATION_REGISTRY", str(registry_path))
    monkeypatch.setattr(agent_workspace, "WORKSPACE_DB_FILE", gar_db)
    agent_workspace.check_in(
        participant_id="chatgpt", session_id="heartbeat-owner", runtime="test"
    )
    acquired = _acquire(
        db_path, registry_path, session="heartbeat-owner", now=None
    )
    before = acquired["claim"]["expires_at"]
    code = agent_room_cli.main(
        ["heartbeat", "--as", "chatgpt", "--session-id", "heartbeat-owner", "--json"]
    )
    assert code == 0, capsys.readouterr().err
    active = agent_coordination.list_claims(active_only=True, db_path=db_path)
    after = next(row["expires_at"] for row in active if row["session_id"] == "heartbeat-owner")
    assert after > before
