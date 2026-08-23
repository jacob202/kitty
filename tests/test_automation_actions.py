from __future__ import annotations

import pytest


@pytest.fixture
def automation_db(tmp_path, monkeypatch):
    import gateway.automation_actions as actions
    from gateway import action_grants, automation_runs

    db_file = tmp_path / "kitty.db"
    monkeypatch.setattr(automation_runs, "DB_FILE", db_file)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_file)
    actions.clear_registry()
    yield db_file
    actions.clear_registry()


@pytest.mark.asyncio
async def test_manual_and_signal_triggers_share_one_registered_action(automation_db):
    import gateway.automation_actions as actions

    calls: list[int] = []

    async def execute(payload):
        calls.append(payload["value"])
        return actions.ActionResult(result_pointer=f"demo:{payload['value']}")

    actions.register_action("demo.run", execute)
    manual = await actions.run_action(
        "demo.run",
        trigger_kind="manual",
        automation_id="manual:demo.run",
        trigger_ref="api",
        payload={"value": 1},
    )
    signal = await actions.run_action(
        "demo.run",
        trigger_kind="signal",
        automation_id="signal:42",
        trigger_ref="42",
        payload={"value": 2},
    )

    assert calls == [1, 2]
    assert manual["status"] == "completed"
    assert manual["trigger_kind"] == "manual"
    assert manual["result_pointer"] == "demo:1"
    assert signal["status"] == "completed"
    assert signal["trigger_kind"] == "signal"
    assert signal["result_pointer"] == "demo:2"


@pytest.mark.asyncio
async def test_scoped_grant_deny_records_policy_refused_without_dispatch(automation_db):
    import gateway.automation_actions as actions
    from gateway import action_grants

    called: list[str] = []

    async def execute(_payload):
        called.append("ran")

    actions.register_action(
        "notify.test",
        execute,
        policy=actions.ActionPolicy(capability="notify.test", tier="T1"),
    )
    deny = action_grants.create_grant(
        capability="notify.test",
        decision="deny",
        granted_tier="T1",
        reason="do not notify from this automation",
        created_by="system",
    )

    run = await actions.run_action(
        "notify.test",
        trigger_kind="manual",
        automation_id="manual:notify.test",
    )

    assert called == []
    assert run["status"] == "policy_refused"
    assert run["policy"]["outcome"] == "deny"
    assert run["policy"]["grant_id"] == deny["id"]


@pytest.mark.asyncio
async def test_t2_requires_existing_grant_and_revocation_stops_it(automation_db):
    import gateway.automation_actions as actions
    from gateway import action_grants

    calls: list[str] = []

    async def execute(_payload):
        calls.append("ran")

    policy = actions.ActionPolicy(capability="external.demo", tier="T2")
    actions.register_action("external.demo", execute, policy=policy)

    refused = await actions.run_action(
        "external.demo", trigger_kind="manual", automation_id="manual:external.demo"
    )
    assert refused["status"] == "policy_refused"
    assert calls == []

    grant = action_grants.create_grant(
        capability="external.demo",
        decision="allow",
        granted_tier="T2",
        reason="approved recurring demo",
        created_by="user",
        user_confirmed=True,
    )
    allowed = await actions.run_action(
        "external.demo", trigger_kind="manual", automation_id="manual:external.demo"
    )
    assert allowed["status"] == "completed"
    assert allowed["policy"]["grant_id"] == grant["id"]
    assert calls == ["ran"]

    action_grants.revoke_grant(grant["id"])
    refused_again = await actions.run_action(
        "external.demo", trigger_kind="manual", automation_id="manual:external.demo"
    )
    assert refused_again["status"] == "policy_refused"
    assert calls == ["ran"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc_type", "expected"),
    [("source", "source_unavailable"), ("condition", "condition_false")],
)
async def test_domain_non_execution_outcomes_remain_distinct(automation_db, exc_type, expected):
    import gateway.automation_actions as actions

    async def execute(_payload):
        if exc_type == "source":
            raise actions.SourceUnavailable("connector offline")
        raise actions.ConditionFalse("keyword absent")

    actions.register_action("demo.condition", execute)
    run = await actions.run_action(
        "demo.condition",
        trigger_kind="manual",
        automation_id="manual:demo.condition",
    )

    assert run["status"] == expected
    assert run["error"] in {"connector offline", "keyword absent"}


@pytest.mark.asyncio
async def test_missing_action_records_action_unavailable(automation_db):
    import gateway.automation_actions as actions

    run = await actions.run_action(
        "missing.action",
        trigger_kind="manual",
        automation_id="manual:missing.action",
    )
    assert run["status"] == "action_unavailable"


@pytest.mark.asyncio
async def test_server_owned_automation_scope_applies_without_becoming_caller_authority(
    automation_db,
):
    import gateway.automation_actions as actions
    from gateway import action_grants

    calls: list[str] = []

    async def execute(_payload):
        calls.append("ran")

    actions.register_action(
        "notify.scoped",
        execute,
        policy=actions.ActionPolicy(capability="notify.scoped", tier="T1"),
    )
    action_grants.create_grant(
        capability="notify.scoped",
        decision="deny",
        granted_tier="T1",
        reason="disable only this automation",
        scope_type="automation",
        scope_id="watch:one",
        created_by="system",
    )

    denied = await actions.run_action(
        "notify.scoped",
        trigger_kind="signal",
        automation_id="watch:one",
        policy_scope_type="automation",
        policy_scope_id="watch:one",
    )
    allowed = await actions.run_action(
        "notify.scoped",
        trigger_kind="signal",
        automation_id="watch:two",
        policy_scope_type="automation",
        policy_scope_id="watch:two",
    )

    assert denied["status"] == "policy_refused"
    assert denied["policy"]["scope_type"] == "automation"
    assert denied["policy"]["scope_id"] == "watch:one"
    assert allowed["status"] == "completed"
    assert calls == ["ran"]
