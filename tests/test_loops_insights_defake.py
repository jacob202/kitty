"""Tests that /loops and /insights no longer return hard-coded fake payloads."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from gateway import cron, db as kitty_db, dream_insights
    from gateway.app import app

    # Pin the cron store to a tmp kitty.db with the required tables
    # (cron_schedules + app_settings) so tests are isolated.
    db_file = tmp_path / "kitty.db"
    with kitty_db.connect(db_file) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cron_schedules (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, action TEXT NOT NULL,
                schedule_type TEXT NOT NULL, schedule_value TEXT NOT NULL,
                metadata TEXT DEFAULT '{}', enabled INTEGER DEFAULT 1,
                last_run REAL DEFAULT 0, created_at REAL
            )
            """
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)"
        )
        conn.commit()
    monkeypatch.setattr(cron, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(
        dream_insights, "DREAM_INSIGHTS_FILE", tmp_path / "data" / "dream_insights.json"
    )

    return TestClient(app)


class TestLoopsNotFake:
    def test_get_loops_empty_when_no_schedules(self, client):
        response = client.get("/loops")
        assert response.status_code == 200
        body = response.json()
        assert body == {"loops": []}

    def test_get_loops_not_hardcoded_fake(self, client):
        """The old payload contained a 'daily-brief' row; real data must not."""
        response = client.get("/loops")
        assert response.status_code == 200
        body = response.json()
        ids = [loop["loop_id"] for loop in body["loops"]]
        assert "daily-brief" not in ids
        for loop in body["loops"]:
            assert loop.get("description") != "Generates morning brief at 7am"

    def test_create_loop_then_toggle_then_delete(self, client):
        create_resp = client.post(
            "/loops",
            json={
                "name": "Test Loop",
                "description": "A test loop",
                "interval_minutes": 30,
                "action": "noop",
            },
        )
        assert create_resp.status_code == 200
        loop = create_resp.json()
        assert loop["name"] == "Test Loop"
        assert loop["status"] == "running"
        loop_id = loop["loop_id"]

        get_resp = client.get("/loops")
        assert any(loop["loop_id"] == loop_id for loop in get_resp.json()["loops"])

        toggle_resp = client.post(f"/loop/{loop_id}/toggle")
        assert toggle_resp.status_code == 200
        assert toggle_resp.json()["status"] == "paused"

        delete_resp = client.delete(f"/loop/{loop_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["deleted"] == loop_id

        get_resp2 = client.get("/loops")
        assert not any(loop["loop_id"] == loop_id for loop in get_resp2.json()["loops"])


class TestInsightsNotFake:
    def test_get_insights_empty_when_no_file(self, client):
        response = client.get("/insights")
        assert response.status_code == 200
        body = response.json()
        assert body == {"insights": []}

    def test_get_insights_not_hardcoded_fake(self, client):
        """The old payload contained 'pattern-morning-weather'; real data must not."""
        response = client.get("/insights")
        assert response.status_code == 200
        body = response.json()
        ids = [i["insight_id"] for i in body["insights"]]
        assert "pattern-morning-weather" not in ids
        assert "suggestion-daily-loop" not in ids
        assert "milestone-100-chats" not in ids

    def test_insights_loaded_from_dream_store(self, client, tmp_path):
        from gateway.dream_insights import DREAM_INSIGHTS_FILE

        DREAM_INSIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        DREAM_INSIGHTS_FILE.write_text(
            json.dumps(
                [
                    {
                        "insight_id": "real-1",
                        "kind": "consolidation",
                        "title": "Real insight",
                        "detail": "From the dream store",
                        "source": "nightly_dream",
                        "confidence": 0.9,
                        "created_at": "2026-06-01T08:00:00",
                        "actions": [],
                    }
                ]
            )
        )

        response = client.get("/insights")
        assert response.status_code == 200
        body = response.json()
        assert len(body["insights"]) == 1
        assert body["insights"][0]["insight_id"] == "real-1"
        assert body["insights"][0]["title"] == "Real insight"
