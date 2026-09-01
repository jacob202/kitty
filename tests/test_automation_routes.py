from __future__ import annotations

import pytest


@pytest.fixture
def automation_env(tmp_path, monkeypatch):
    import gateway.automation_actions as actions
    from gateway import action_grants, automation_runs

    db_file = tmp_path / "kitty.db"
    monkeypatch.setenv("KITTY_ENV", "test")
    monkeypatch.setattr(automation_runs, "DB_FILE", db_file)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_file)
    actions.clear_registry()
    yield db_file
    actions.clear_registry()


@pytest.mark.asyncio
async def test_manual_route_uses_shared_action_path(automation_env):
    import gateway.automation_actions as actions
    from gateway.routes import automations

    seen: list[str] = []

    async def execute(payload):
        seen.append(payload["value"])
        return actions.ActionResult(result_pointer="artifact:1")

    actions.register_action("demo.manual", execute)
    payload = automations.ManualRunRequest(
        automation_id="manual:test",
        payload={"value": "ok"},
    )
    response = await automations.run_manual_action("demo.manual", payload)

    assert seen == ["ok"]
    assert response["run"]["status"] == "completed"
    assert response["run"]["trigger_kind"] == "manual"
    assert response["run"]["result_pointer"] == "artifact:1"


@pytest.mark.asyncio
async def test_manual_route_does_not_accept_caller_policy_override(automation_env):
    from pydantic import ValidationError

    from gateway.routes import automations

    with pytest.raises(ValidationError):
        automations.ManualRunRequest.model_validate(
            {
                "automation_id": "manual:test",
                "payload": {},
                "tier": "T0",
                "approved": True,
                "scope_type": "automation",
                "scope_id": "someone-else",
            }
        )


@pytest.mark.asyncio
async def test_automation_status_exposes_supervisor_and_registered_actions(automation_env):
    import gateway.automation_actions as actions
    from gateway.automation_supervisor import supervisor
    from gateway.routes import automations

    async def execute(_payload):
        return None

    actions.register_action("demo.status", execute)
    supervisor.mark("cron", "available", reason="runner active")

    response = await automations.automation_status()

    assert "demo.status" in response["actions"]
    cron = next(item for item in response["services"] if item["name"] == "cron")
    assert cron["status"] == "available"


def test_automation_routes_are_mounted_on_gateway(automation_env):
    from fastapi.testclient import TestClient

    import gateway.automation_actions as actions
    from gateway.app import app

    async def execute(_payload):
        return actions.ActionResult(result_pointer="artifact:mounted")

    actions.register_action("demo.mounted", execute)
    with TestClient(app, raise_server_exceptions=False) as client:
        status = client.get("/automations/status")
        run = client.post(
            "/automations/actions/demo.mounted/run",
            json={"automation_id": "manual:mounted", "payload": {}},
        )
        rejected = client.post(
            "/automations/actions/demo.mounted/run",
            json={
                "automation_id": "manual:mounted",
                "payload": {},
                "tier": "T0",
                "approved": True,
            },
        )

    assert status.status_code == 200
    assert "demo.mounted" in status.json()["actions"]
    assert run.status_code == 200
    assert run.json()["run"]["status"] == "completed"
    assert run.json()["run"]["result_pointer"] == "artifact:mounted"
    assert rejected.status_code == 422


def test_automation_runs_route_exposes_non_cron_history(automation_env):
    from fastapi.testclient import TestClient

    from gateway import automation_runs
    from gateway.app import app

    run = automation_runs.begin_run(
        automation_id="web_monitor:watch-1",
        action="web_monitor.notify",
        trigger_kind="monitor",
        trigger_ref="watch-1",
    )
    automation_runs.finish_run(run["id"], status="condition_false")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/automations/runs",
            params={"automation_id": "web_monitor:watch-1", "limit": 10},
        )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["runs"]] == [run["id"]]
    assert response.json()["runs"][0]["status"] == "condition_false"


def test_automation_run_route_fetches_exact_durable_run(automation_env):
    from fastapi.testclient import TestClient

    from gateway import automation_runs
    from gateway.app import app

    old = automation_runs.begin_run(
        automation_id='daily:old', action='brief.send', trigger_kind='time', started_at=10.0,
    )
    automation_runs.finish_run(old['id'], status='failed', error='provider unavailable', completed_at=11.0)
    for i in range(60):
        newer = automation_runs.begin_run(
            automation_id=f'daily:new-{i}', action='brief.send', trigger_kind='time',
            started_at=1000 + i,
        )
        automation_runs.finish_run(newer['id'], status='completed', completed_at=1100 + i)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"/automations/runs/{old['id']}")

    assert response.status_code == 200
    assert response.json()['run']['id'] == old['id']
    assert response.json()['run']['status'] == 'failed'
    assert response.json()['run']['error'] == 'provider unavailable'
