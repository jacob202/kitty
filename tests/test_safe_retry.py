"""Unified Safe Retry (QoL Packet 06): automation + image retry matrix.

Retry must preserve execution intent (action/parameters/identity/scope/lane)
while minting a new execution identity, and must re-evaluate authority instead
of reusing the original authorization.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from gateway.image_jobs import (
    ImageJobError,
    ImageJobStatus,
    JobNotFoundError,
)


@pytest.fixture
def automation_db(tmp_path, monkeypatch):
    from gateway import action_grants, automation_actions, automation_runs, cron
    from gateway import db as kitty_db

    db_file = tmp_path / "kitty.db"
    kitty_db.migrate(db_file=db_file)
    monkeypatch.setattr(automation_runs, "DB_FILE", db_file)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_file)
    monkeypatch.setattr(cron, "KITTY_DB_FILE", db_file)
    automation_actions.clear_registry()
    cron._runner_task = None
    yield db_file
    automation_actions.clear_registry()
    cron._runner_task = None


@pytest.fixture
def image_db(tmp_path: Path):
    import gateway.paths as gp
    from gateway import image_jobs as jobs

    test_db = tmp_path / "kitty.db"
    original = gp.KITTY_DB_FILE
    gp.KITTY_DB_FILE = test_db
    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    jobs._ensure_db(conn)
    jobs._ensure_queue_columns(conn)
    conn.close()
    yield test_db
    gp.KITTY_DB_FILE = original


def _make_failed_run(automation_db, *, action: str, payload=None) -> dict:
    from gateway import automation_actions, automation_runs

    seen: list[dict] = []

    def fn(p: dict) -> None:
        seen.append(p)
        raise RuntimeError("boom")

    automation_actions.register_action(
        action,
        fn,
        policy=automation_actions.ActionPolicy(capability=action, tier="T2"),
    )
    run = automation_runs.begin_run(
        automation_id="automation-1",
        action=action,
        trigger_kind="manual",
        trigger_ref="trigger-1",
        payload=payload,
    )
    automation_runs.finish_run(
        run["id"], status="failed", error="RuntimeError: boom"
    )
    return automation_runs.get_run(run["id"])


# ── 1. Automation retry_run ────────────────────────────────────────────────


class TestAutomationRetryRun:
    def test_retry_mints_new_identity_preserving_intent(self, automation_db):
        from gateway import automation_runs

        original = _make_failed_run(automation_db, action="retry.test", payload={"n": 7})

        retried = automation_runs.retry_run(original["id"], started_at=99_000.0)

        assert retried["id"] != original["id"]
        assert retried["id"].startswith("arun_")
        assert retried["status"] == "running"
        assert retried["started_at"] == 99_000.0
        assert retried["automation_id"] == original["automation_id"]
        assert retried["action"] == original["action"]
        assert retried["trigger_kind"] == original["trigger_kind"]
        assert retried["trigger_ref"] == original["trigger_ref"]
        assert retried["payload"] == {"n": 7}
        # The original evidence is untouched.
        assert automation_runs.get_run(original["id"])["status"] == "failed"

    def test_retry_requires_terminal_original(self, automation_db):
        from gateway import automation_actions, automation_runs

        automation_actions.register_action(
            "retry.running",
            lambda p: None,
            policy=automation_actions.ActionPolicy(capability="retry.running", tier="T2"),
        )
        run = automation_runs.begin_run(
            automation_id="a", action="retry.running", trigger_kind="manual"
        )
        with pytest.raises(automation_runs.AutomationRunStateError):
            automation_runs.retry_run(run["id"])

    def test_retry_missing_raises(self, automation_db):
        from gateway import automation_runs

        with pytest.raises(automation_runs.AutomationRunNotFound):
            automation_runs.retry_run("arun_nope")

    def test_payload_persisted_on_begin(self, automation_db):
        from gateway import automation_runs

        run = automation_runs.begin_run(
            automation_id="a",
            action="retry.payload",
            trigger_kind="manual",
            payload={"a": 1, "b": "x"},
        )
        assert run["payload"] == {"a": 1, "b": "x"}
        with sqlite3.connect(automation_db) as conn:
            raw = conn.execute(
                "SELECT payload_json FROM automation_runs WHERE id = ?", (run["id"],)
            ).fetchone()[0]
        assert json.loads(raw) == {"a": 1, "b": "x"}


# ── 2. Automation retry route (safe re-dispatch) ───────────────────────────


class TestAutomationRetryRoute:
    @pytest.mark.asyncio
    async def test_successful_retry_re_dispatches_with_same_intent(self, automation_db):
        from gateway import action_grants, automation_actions, automation_runs

        attempts: list[dict] = []
        state = {"fail_next": True}

        def fn(p: dict) -> None:
            attempts.append(p)
            if state["fail_next"]:
                raise RuntimeError("transient")
            return automation_actions.ActionResult()

        automation_actions.register_action(
            "retry.succeed",
            fn,
            policy=automation_actions.ActionPolicy(capability="retry.succeed", tier="T2"),
        )
        action_grants.create_grant(
            capability="retry.succeed",
            decision="allow",
            granted_tier="T2",
            reason="approve retry test",
            created_by="user",
            user_confirmed=True,
        )
        original = automation_runs.begin_run(
            automation_id="auto-1", action="retry.succeed", trigger_kind="manual", payload={"k": "v"}
        )
        await automation_actions.run_action(
            "retry.succeed",
            trigger_kind="manual",
            automation_id="auto-1",
            run_id=original["id"],
            payload={"k": "v"},
        )
        assert automation_runs.get_run(original["id"])["status"] == "failed"

        state["fail_next"] = False
        from gateway.routes import automations as automations_routes

        response = await automations_routes.retry_automation_run(original["id"])

        new_run = response["run"]
        assert new_run["id"] != original["id"]
        assert new_run["status"] == "completed"
        assert response["retried_from"] == original["id"]
        assert attempts == [{"k": "v"}, {"k": "v"}]

    @pytest.mark.asyncio
    async def test_failed_retry_records_failure_on_new_run(self, automation_db):
        from gateway import action_grants, automation_actions, automation_runs
        from gateway.routes import automations as automations_routes

        def fn(p: dict) -> None:
            raise RuntimeError("still broken")

        automation_actions.register_action(
            "retry.stillfails",
            fn,
            policy=automation_actions.ActionPolicy(capability="retry.stillfails", tier="T2"),
        )
        action_grants.create_grant(
            capability="retry.stillfails",
            decision="allow",
            granted_tier="T2",
            reason="approve retry test",
            created_by="user",
            user_confirmed=True,
        )
        original = automation_runs.begin_run(
            automation_id="a", action="retry.stillfails", trigger_kind="manual"
        )
        await automation_actions.run_action(
            "retry.stillfails",
            trigger_kind="manual",
            automation_id="a",
            run_id=original["id"],
        )
        response = await automations_routes.retry_automation_run(original["id"])
        assert response["run"]["status"] == "failed"
        assert "RuntimeError: still broken" in response["run"]["error"]
        assert automation_runs.get_run(original["id"])["status"] == "failed"

    @pytest.mark.asyncio
    async def test_revoked_grant_before_retry_is_refused(self, automation_db):
        from gateway import action_grants, automation_actions, automation_runs
        from gateway.routes import automations as automations_routes

        def fn(p: dict) -> None:
            return automation_actions.ActionResult()

        automation_actions.register_action(
            "retry.granted",
            fn,
            policy=automation_actions.ActionPolicy(capability="retry.granted", tier="T2"),
        )
        grant = action_grants.create_grant(
            capability="retry.granted",
            decision="allow",
            granted_tier="T2",
            reason="approve retry test",
            created_by="user",
            user_confirmed=True,
        )
        original = automation_runs.begin_run(
            automation_id="a", action="retry.granted", trigger_kind="manual"
        )
        await automation_actions.run_action(
            "retry.granted",
            trigger_kind="manual",
            automation_id="a",
            run_id=original["id"],
        )
        assert automation_runs.get_run(original["id"])["status"] == "completed"

        action_grants.revoke_grant(grant["id"])
        response = await automations_routes.retry_automation_run(original["id"])
        assert response["run"]["status"] == "policy_refused"
        assert response["run"]["id"] != original["id"]
        # Original remains completed; only the retry carries the refusal.
        assert automation_runs.get_run(original["id"])["status"] == "completed"

    @pytest.mark.asyncio
    async def test_retry_route_404_and_409(self, automation_db):
        from fastapi import HTTPException

        from gateway import automation_actions, automation_runs
        from gateway.routes import automations as automations_routes

        with pytest.raises(HTTPException) as missing:
            await automations_routes.retry_automation_run("arun_nope")
        assert missing.value.status_code == 404

        automation_actions.register_action(
            "retry.inscope",
            lambda p: None,
            policy=automation_actions.ActionPolicy(capability="retry.inscope", tier="T2"),
        )
        run = automation_runs.begin_run(
            automation_id="a", action="retry.inscope", trigger_kind="manual"
        )
        with pytest.raises(HTTPException) as running:
            await automations_routes.retry_automation_run(run["id"])
        assert running.value.status_code == 409


# ── 3. Image retry_job ─────────────────────────────────────────────────────


class TestImageRetryJob:
    def test_retry_failed_job_creates_lineaged_child(self, image_db):
        from gateway import image_jobs as jobs

        parent = jobs.create_job(
            provider="comfyui",
            operation="txt2img",
            prompt="a cat",
            negative_prompt="no dog",
            seed=42,
            model_id="sd15",
            width=512,
            height=512,
            steps=20,
            guidance=7.0,
            max_retries=2,
            plan_id="plan_abc",
            intent_json=json.dumps({"content_lane": "private_adult", "character": "kiki"}),
        )
        jobs.transition(parent.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(parent.job_id, ImageJobStatus.RUNNING)
        jobs.transition(parent.job_id, ImageJobStatus.FAILED)

        child = jobs.retry_job(parent.job_id)

        assert child.job_id != parent.job_id
        assert child.status == ImageJobStatus.CREATED
        assert child.parent_id == parent.job_id
        # Intent preservation: lane + character ride on plan_id/intent_json.
        assert child.plan_id == parent.plan_id == "plan_abc"
        assert json.loads(child.intent_json or "{}")["content_lane"] == "private_adult"
        assert child.provider == parent.provider
        assert child.operation == parent.operation
        assert child.prompt == parent.prompt
        assert child.seed == parent.seed
        assert child.model_id == parent.model_id
        assert child.width == parent.width
        assert child.guidance == parent.guidance
        assert child.max_retries == parent.max_retries

    def test_retry_lineage_list_children(self, image_db):
        from gateway import image_jobs as jobs

        parent = jobs.create_job(provider="comfyui", operation="txt2img", prompt="a cat")
        jobs.transition(parent.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(parent.job_id, ImageJobStatus.RUNNING)
        jobs.transition(parent.job_id, ImageJobStatus.FAILED)

        child = jobs.retry_job(parent.job_id)
        children = jobs.list_children(parent.job_id)
        assert [c.job_id for c in children] == [child.job_id]

    def test_retry_non_terminal_raises(self, image_db):
        from gateway import image_jobs as jobs

        job = jobs.create_job(provider="comfyui", operation="txt2img", prompt="a cat")
        with pytest.raises(ImageJobError, match="terminal"):
            jobs.retry_job(job.job_id)

    def test_retry_succeeded_raises(self, image_db):
        from gateway import image_jobs as jobs

        job = jobs.create_job(provider="comfyui", operation="txt2img", prompt="a cat")
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        jobs.update_job(job.job_id, output_path="/tmp/x.png")
        jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
        with pytest.raises(ImageJobError, match="terminal"):
            jobs.retry_job(job.job_id)

    def test_retry_missing_raises(self, image_db):
        from gateway import image_jobs as jobs

        with pytest.raises(JobNotFoundError):
            jobs.retry_job("job_nope")
