from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import memory_mission
from gateway.routes import missions


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(memory_mission, "MISSION_DB_FILE", tmp_path / "kitty.db")
    app = FastAPI()
    app.include_router(missions.router)
    return TestClient(app)


def test_create_list_get_preserves_durable_mission(client: TestClient) -> None:
    created = client.post(
        "/missions",
        json={
            "objective": "Ship one reliable outcome",
            "definition_of_done": ["The running product completes the journey."],
        },
    )
    assert created.status_code == 201
    mission = created.json()
    assert mission["mission_id"].startswith("mission_")
    assert mission["objective"] == "Ship one reliable outcome"
    assert mission["status"] == "PLANNING"
    assert mission["supervisor"] == {"id": "kitty", "epoch": 1}

    listing = client.get("/missions")
    assert listing.status_code == 200
    assert [item["mission_id"] for item in listing.json()["missions"]] == [mission["mission_id"]]

    loaded = client.get(f"/missions/{mission['mission_id']}")
    assert loaded.status_code == 200
    assert loaded.json() == mission


def test_pause_resume_stop_and_unknown_id_are_truthful(client: TestClient) -> None:
    mission = client.post(
        "/missions",
        json={"objective": "Control lifecycle", "definition_of_done": ["Lifecycle is durable."]},
    ).json()
    mission_id = mission["mission_id"]

    paused = client.post(f"/missions/{mission_id}/pause", json={"reason": "Jacob asked to pause"})
    assert paused.status_code == 200
    assert paused.json()["status"] == "PAUSED"
    assert paused.json()["paused_from_status"] == "PLANNING"

    resumed = client.post(f"/missions/{mission_id}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "PLANNING"

    stopped = client.post(f"/missions/{mission_id}/stop", json={"reason": "Outcome cancelled"})
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "STOPPED"

    refused = client.post(f"/missions/{mission_id}/resume")
    assert refused.status_code == 409
    assert "stopped Mission" in refused.json()["detail"]

    missing = client.get("/missions/does-not-exist")
    assert missing.status_code == 404


def _seed_conversation(
    db_path: Path,
    *,
    conversation_id: str = "conv-1",
    conversation_project: int | None = 7,
    turn_project: int | None = None,
    message_id: str = "msg-1",
) -> None:
    """Create the minimum chat rows an origin binding resolves against."""
    from gateway import db as kitty_db

    memory_mission.init_db(db_path=db_path)
    with kitty_db.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_conversations (
                id TEXT PRIMARY KEY, project_id INTEGER, title TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL, updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS chat_turns (
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, project_id INTEGER,
                sequence INTEGER NOT NULL, status TEXT NOT NULL,
                manifest_revision TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY, turn_id TEXT NOT NULL, role TEXT NOT NULL,
                content TEXT NOT NULL, status TEXT NOT NULL, created_at REAL NOT NULL);
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO chat_conversations (id, project_id, created_at, updated_at) "
            "VALUES (?, ?, 0, 0)",
            (conversation_id, conversation_project),
        )
        conn.execute(
            "INSERT OR REPLACE INTO chat_turns "
            "(id, conversation_id, project_id, sequence, status, manifest_revision, created_at) "
            "VALUES ('turn-1', ?, ?, 1, 'succeeded', 'r1', 0)",
            (conversation_id, turn_project),
        )
        conn.execute(
            "INSERT OR REPLACE INTO chat_messages "
            "(id, turn_id, role, content, status, created_at) "
            "VALUES (?, 'turn-1', 'user', 'do the thing', 'complete', 0)",
            (message_id,),
        )
        conn.commit()


def test_chat_origin_prefers_the_originating_turn_project(tmp_path: Path) -> None:
    db_path = tmp_path / "kitty.db"
    _seed_conversation(db_path, conversation_project=7, turn_project=9)

    origin = memory_mission.resolve_chat_origin(
        conversation_id="conv-1", message_id="msg-1", db_path=db_path
    )

    assert origin == {
        "kind": "chat",
        "conversation_id": "conv-1",
        "message_id": "msg-1",
        "project_id": 9,
    }


def test_chat_origin_falls_back_to_the_conversation_project(tmp_path: Path) -> None:
    db_path = tmp_path / "kitty.db"
    _seed_conversation(db_path, conversation_project=7, turn_project=None)

    origin = memory_mission.resolve_chat_origin(
        conversation_id="conv-1", message_id="msg-1", db_path=db_path
    )

    assert origin["project_id"] == 7


def test_chat_origin_refuses_a_message_from_another_conversation(tmp_path: Path) -> None:
    db_path = tmp_path / "kitty.db"
    _seed_conversation(db_path)
    from gateway import db as kitty_db

    with kitty_db.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO chat_conversations (id, project_id, created_at, updated_at) "
            "VALUES ('conv-2', 3, 0, 0)"
        )
        conn.commit()

    with pytest.raises(memory_mission.MissionError, match="does not belong to conversation"):
        memory_mission.resolve_chat_origin(
            conversation_id="conv-2", message_id="msg-1", db_path=db_path
        )


def test_reassigning_the_conversation_does_not_move_historical_origin(tmp_path: Path) -> None:
    """P3 acceptance 5: history stays where the work was actually done."""
    db_path = tmp_path / "kitty.db"
    _seed_conversation(db_path, conversation_project=7)
    origin = memory_mission.resolve_chat_origin(
        conversation_id="conv-1", message_id="msg-1", db_path=db_path
    )
    memory_mission.create_mission(
        mission_id="mission_origin",
        objective="Ship one reliable outcome",
        definition_of_done=["done"],
        supervisor_id="kitty",
        origin=origin,
        db_path=db_path,
    )

    from gateway import db as kitty_db

    with kitty_db.connect(db_path) as conn:
        conn.execute("UPDATE chat_conversations SET project_id = 99 WHERE id = 'conv-1'")
        conn.commit()

    stored = memory_mission.get_mission("mission_origin", db_path=db_path)
    assert stored["origin"]["project_id"] == 7


def test_origin_survives_replay_and_refuses_a_conflicting_rebind(tmp_path: Path) -> None:
    """P3 acceptance 7: an ambiguous replay creates no second, rehomed job."""
    db_path = tmp_path / "kitty.db"
    _seed_conversation(db_path)
    origin = memory_mission.resolve_chat_origin(
        conversation_id="conv-1", message_id="msg-1", db_path=db_path
    )
    first = memory_mission.ensure_mission(
        mission_id="mission_replay",
        objective="Ship one reliable outcome",
        definition_of_done=["done"],
        supervisor_id="kitty",
        origin=origin,
        db_path=db_path,
    )

    # Same origin replays cleanly.
    again = memory_mission.ensure_mission(
        mission_id="mission_replay",
        objective="Ship one reliable outcome",
        definition_of_done=["done"],
        supervisor_id="kitty",
        origin=origin,
        db_path=db_path,
    )
    assert again["origin"] == first["origin"]

    # A replay that has lost its context leaves the binding alone.
    forgetful = memory_mission.ensure_mission(
        mission_id="mission_replay",
        objective="Ship one reliable outcome",
        definition_of_done=["done"],
        supervisor_id="kitty",
        db_path=db_path,
    )
    assert forgetful["origin"] == first["origin"]

    # A replay claiming a different home is refused.
    with pytest.raises(memory_mission.MissionError, match="different origin"):
        memory_mission.ensure_mission(
            mission_id="mission_replay",
            objective="Ship one reliable outcome",
            definition_of_done=["done"],
            supervisor_id="kitty",
            origin=memory_mission.project_origin(42),
            db_path=db_path,
        )


def test_by_origin_route_recovers_work_without_any_browser_state(
    client: TestClient, tmp_path: Path
) -> None:
    """P3 acceptance 3: empty localStorage still finds the delegated work."""
    db_path = tmp_path / "kitty.db"
    _seed_conversation(db_path)
    origin = memory_mission.resolve_chat_origin(
        conversation_id="conv-1", message_id="msg-1", db_path=db_path
    )
    memory_mission.create_mission(
        mission_id="mission_recoverable",
        objective="Ship one reliable outcome",
        definition_of_done=["done"],
        supervisor_id="kitty",
        origin=origin,
        db_path=db_path,
    )

    found = client.get("/missions/by-origin", params={"conversation_id": "conv-1"})
    assert found.status_code == 200
    assert [m["mission_id"] for m in found.json()["missions"]] == ["mission_recoverable"]

    by_project = client.get("/missions/by-origin", params={"project_id": 7})
    assert [m["mission_id"] for m in by_project.json()["missions"]] == ["mission_recoverable"]

    assert client.get("/missions/by-origin").status_code == 400


def test_unbound_missions_report_no_origin_rather_than_a_guess(client: TestClient) -> None:
    created = client.post(
        "/missions",
        json={"objective": "No origin", "definition_of_done": ["done"]},
    )
    assert created.json()["origin"] is None


def test_mission_for_initiative_finds_the_bound_mission(tmp_path: Path) -> None:
    db_path = tmp_path / "kitty.db"
    memory_mission.create_mission(
        mission_id="mission_bound",
        objective="Ship it",
        definition_of_done=["done"],
        supervisor_id="kitty",
        db_path=db_path,
    )
    memory_mission.bind_builder_locator(
        "mission_bound", initiative_id="conv-initiative-1", db_path=db_path
    )

    found = memory_mission.mission_for_initiative("conv-initiative-1", db_path=db_path)

    assert found is not None
    assert found["mission_id"] == "mission_bound"
    assert found["acceptance"]["state"] == "unreviewed"


def test_mission_lookup_does_not_create_sidecars_for_clean_wal_database(tmp_path: Path) -> None:
    db_path = tmp_path / "kitty.db"
    memory_mission.create_mission(
        mission_id="mission_clean_wal",
        objective="Ship it",
        definition_of_done=["done"],
        supervisor_id="kitty",
        db_path=db_path,
    )
    memory_mission.bind_builder_locator(
        "mission_clean_wal", initiative_id="init-clean-wal", db_path=db_path
    )
    wal = Path(f"{db_path}-wal")
    shm = Path(f"{db_path}-shm")
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        checkpoint = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    assert checkpoint is not None and checkpoint[0] == 0
    wal.unlink(missing_ok=True)
    shm.unlink(missing_ok=True)

    found = memory_mission.mission_for_initiative("init-clean-wal", db_path=db_path)

    assert found is not None
    assert found["mission_id"] == "mission_clean_wal"
    assert not wal.exists()
    assert not shm.exists()


def test_mission_lookup_reads_wal_without_creating_source_shm(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    memory_mission.create_mission(
        mission_id="mission_live_wal",
        objective="Ship it",
        definition_of_done=["done"],
        supervisor_id="kitty",
        db_path=source,
    )
    writer = sqlite3.connect(source)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute(
            "UPDATE missions SET builder_locator_json = ? WHERE mission_id = ?",
            ('{"initiative_id":"init-live-wal"}', "mission_live_wal"),
        )
        writer.commit()
        source_wal = Path(f"{source}-wal")
        assert source_wal.exists()

        snapshot = tmp_path / "snapshot.db"
        shutil.copy2(source, snapshot)
        shutil.copy2(source_wal, Path(f"{snapshot}-wal"))
        snapshot_shm = Path(f"{snapshot}-shm")
        assert not snapshot_shm.exists()

        found = memory_mission.mission_for_initiative("init-live-wal", db_path=snapshot)

        assert found is not None
        assert found["mission_id"] == "mission_live_wal"
        assert not snapshot_shm.exists()
    finally:
        writer.close()


def test_mission_for_initiative_is_none_for_unbound_work(tmp_path: Path) -> None:
    """No Mission is 'unknown', which callers must not read as accepted."""
    db_path = tmp_path / "kitty.db"
    memory_mission.create_mission(
        mission_id="mission_unbound",
        objective="Ship it",
        definition_of_done=["done"],
        supervisor_id="kitty",
        db_path=db_path,
    )

    assert memory_mission.mission_for_initiative("no-such-initiative", db_path=db_path) is None
