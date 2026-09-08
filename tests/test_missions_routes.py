from __future__ import annotations

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
