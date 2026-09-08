from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from gateway import automation_actions, builder_loop, memory_mission, mission_runtime
from gateway import builder_initiative as bi
from gateway import paid_review_admission as pra
from mcp.builder import repo_tools


@pytest.fixture()
def mission_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "kitty.db"
    monkeypatch.setattr(memory_mission, "MISSION_DB_FILE", db_path)
    return db_path


def _plan_review_mission(db_path: Path, *, mission_id: str = "mission-review") -> dict:
    memory_mission.create_mission(
        mission_id=mission_id,
        objective="Ship the reviewed plan safely",
        definition_of_done=["The plan is independently reviewed before execution."],
        supervisor_id="kitty",
        db_path=db_path,
    )
    return memory_mission.set_plan(
        mission_id,
        plan_ref="docs/superpowers/plans/review-proof.md@" + "a" * 40,
        plan_digest="b" * 64,
        db_path=db_path,
    )


def test_register_action_uses_existing_automation_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    registered: list[tuple[str, object, object]] = []

    def register(name, fn, *, policy=None):
        registered.append((name, fn, policy))

    monkeypatch.setattr(automation_actions, "register_action", register)
    mission_runtime.register_action()

    assert len(registered) == 1
    name, fn, policy = registered[0]
    assert name == "mission.review_pending"
    assert fn is mission_runtime.review_pending_action
    assert policy.capability == "mission.plan.review"
    assert policy.tier == "T0"


def test_review_plan_records_exact_independent_approval(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mission = _plan_review_mission(mission_db)
    monkeypatch.setattr(
        mission_runtime,
        "run_plan_verifier",
        lambda current: {
            "verdict": "approve",
            "reviewer_id": "dsh:openrouter/nvidia/nemotron-3-super-120b-a12b:free",
            "provider": "openrouter",
            "model": "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
            "summary": "Plan matches the objective and current repository state.",
            "findings": [],
            "review_head": "c" * 40,
        },
    )

    reviewed = mission_runtime.review_plan(mission["mission_id"])

    assert reviewed["status"] == "PLAN_REVIEW"
    assert reviewed["plan"]["review_state"] == "approved"
    assert reviewed["plan"]["reviewer_id"].startswith("dsh:")
    assert reviewed["plan"]["digest"] == "b" * 64
    assert reviewed["plan"]["review_evidence"]["plan_digest"] == "b" * 64
    assert reviewed["plan"]["review_evidence"]["model"].endswith(":free")


def test_review_plan_rejection_returns_to_planning_without_execution(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mission = _plan_review_mission(mission_db, mission_id="mission-reject")
    monkeypatch.setattr(
        mission_runtime,
        "run_plan_verifier",
        lambda current: {
            "verdict": "reject",
            "reviewer_id": "dsh:free-reviewer",
            "provider": "openrouter",
            "model": "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
            "summary": "The plan misses a required recovery path.",
            "findings": [{"severity": "major", "note": "Add restart recovery evidence."}],
            "review_head": "c" * 40,
        },
    )

    reviewed = mission_runtime.review_plan(mission["mission_id"])
    assert reviewed["status"] == "PLANNING"
    assert reviewed["plan"]["review_state"] == "rejected"


def test_review_provider_unavailable_leaves_plan_unreviewed(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mission = _plan_review_mission(mission_db, mission_id="mission-unavailable")

    def unavailable(_current):
        raise mission_runtime.PlanVerifierUnavailable("no healthy zero-cost review route")

    monkeypatch.setattr(mission_runtime, "run_plan_verifier", unavailable)
    with pytest.raises(automation_actions.SourceUnavailable, match="zero-cost"):
        mission_runtime.review_plan(mission["mission_id"])

    current = memory_mission.get_mission(mission["mission_id"], db_path=mission_db)
    assert current["status"] == "PLAN_REVIEW"
    assert current["plan"]["review_state"] == "unreviewed"


@pytest.mark.asyncio
async def test_review_pending_action_reviews_only_unreviewed_plan(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pending = _plan_review_mission(mission_db, mission_id="mission-pending")
    memory_mission.create_mission(
        mission_id="mission-planning",
        objective="Not ready",
        definition_of_done=["Still planning"],
        supervisor_id="kitty",
        db_path=mission_db,
    )
    seen: list[str] = []

    def review(mission_id: str):
        seen.append(mission_id)
        return memory_mission.get_mission(mission_id, db_path=mission_db)

    monkeypatch.setattr(mission_runtime, "review_plan", review)
    result = await mission_runtime.review_pending_action({})

    assert seen == [pending["mission_id"]]
    assert result.status == "completed"
    assert result.result_pointer == f"mission://{pending['mission_id']}"


@pytest.mark.asyncio
async def test_request_plan_review_uses_one_durable_automation_run_per_live_review(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mission = _plan_review_mission(mission_db, mission_id="mission-request")
    from gateway import automation_runs

    monkeypatch.setattr(automation_runs, "DB_FILE", mission_db)
    mission_runtime.register_action()
    started = automation_runs.begin_run(
        automation_id="mission-plan-review:mission-request",
        action=mission_runtime.ACTION_NAME,
        trigger_kind="signal",
        trigger_ref=mission["plan"]["digest"],
    )
    called = False

    async def should_not_run(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(automation_actions, "run_action", should_not_run)
    result = await mission_runtime.request_plan_review("mission-request")

    assert result["id"] == started["id"]
    assert result["status"] == "running"
    assert called is False


@pytest.mark.asyncio
async def test_request_plan_review_runs_through_automation_authority(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mission = _plan_review_mission(mission_db, mission_id="mission-dispatch")
    from gateway import automation_runs

    monkeypatch.setattr(automation_runs, "DB_FILE", mission_db)
    captured = {}

    async def run_action(name, **kwargs):
        captured.update(name=name, **kwargs)
        return {"id": "arun-proof", "status": "completed"}

    monkeypatch.setattr(automation_actions, "run_action", run_action)
    result = await mission_runtime.request_plan_review("mission-dispatch")

    assert result == {"id": "arun-proof", "status": "completed"}
    assert captured["name"] == mission_runtime.ACTION_NAME
    assert captured["trigger_kind"] == "signal"
    assert captured["automation_id"] == "mission-plan-review:mission-dispatch"
    assert captured["trigger_ref"] == mission["plan"]["digest"]
    assert captured["payload"] == {"mission_id": "mission-dispatch"}



def test_run_plan_verifier_delegates_execution_to_builder_owned_reviewer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from gateway import builder_initiative as bi
    from gateway import builder_loop
    from mcp.builder import repo_tools

    payload = {
        "manifest_version": 1,
        "initiative_id": "review-fixture",
        "title": "Review fixture",
        "description": "inspect exact plan",
        "packets": [{
            "id": "P1",
            "title": "Review fixture",
            "objective": "review safely",
            "depends_on": [],
            "acceptance_criteria": ["contained"],
            "allowed_paths": ["gateway/example.py"],
            "validation_commands": [],
        }],
    }
    mission = {
        "mission_id": "review-fixture",
        "objective": "review safely",
        "definition_of_done": ["contained"],
        "supervisor": {"id": "kitty", "epoch": 1},
        "plan": {
            "ref": "docs/superpowers/plans/exact.md@" + "a" * 40,
            "digest": bi.manifest_sha256(payload),
            "payload": payload,
        },
    }
    monkeypatch.setattr(repo_tools, "repo_root", lambda: tmp_path)
    seen: dict = {}

    def review(prompt: str, *, root: Path, timeout: int, review_checkout_sha=None):
        seen.update(prompt=prompt, root=root, timeout=timeout, review_checkout_sha=review_checkout_sha)
        return {
            "provider": "openrouter",
            "model": "openrouter/example/reviewer:free",
            "review_head": "c" * 40,
            "review_origin_main": "d" * 40,
            "probes": [{"status": "healthy"}],
            "output": '{"contract_version":1,"verdict":"approve","summary":"contained","findings":[]}',
        }

    monkeypatch.setattr(builder_loop, "run_independent_readonly_review", review)
    result = mission_runtime.run_plan_verifier(mission)

    assert seen["root"] == tmp_path.resolve()
    assert seen["timeout"] == mission_runtime._REVIEW_TIMEOUT_SECONDS
    assert '"initiative_id": "review-fixture"' in seen["prompt"]
    assert result["verdict"] == "approve"
    assert result["reviewer_id"] == "dsh:openrouter/example/reviewer:free"
    assert result["review_head"] == "c" * 40
    assert result["review_origin_main"] == "d" * 40
    assert result["route_probes"] == [{"status": "healthy"}]


def test_run_plan_verifier_fails_closed_when_builder_reviewer_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from gateway import builder_initiative as bi
    from gateway import builder_loop
    from mcp.builder import repo_tools

    payload = {
        "manifest_version": 1, "initiative_id": "i", "title": "T",
        "description": "d", "packets": [{
            "id": "P1", "title": "T", "objective": "o", "depends_on": [],
            "acceptance_criteria": ["a"], "allowed_paths": ["gateway/x.py"],
            "validation_commands": [],
        }],
    }
    mission = {
        "mission_id": "m", "objective": "o", "definition_of_done": ["a"],
        "supervisor": {"id": "kitty", "epoch": 1},
        "plan": {
            "ref": "docs/superpowers/plans/x.md@" + "a" * 40,
            "digest": bi.manifest_sha256(payload), "payload": payload,
        },
    }
    monkeypatch.setattr(repo_tools, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        builder_loop, "run_independent_readonly_review",
        lambda *_a, **_k: (_ for _ in ()).throw(builder_loop.LoopError("no healthy zero-cost reviewer route")),
    )

    with pytest.raises(mission_runtime.PlanVerifierUnavailable, match="zero-cost"):
        mission_runtime.run_plan_verifier(mission)


def test_plan_verifier_prompt_exposes_exact_prepared_manifest_semantics() -> None:
    mission = {
        "mission_id": "m",
        "objective": "Fix exact thing",
        "definition_of_done": ["verified"],
        "supervisor": {"id": "kitty", "epoch": 1},
        "plan": {
            "ref": "docs/superpowers/plans/x.md@" + "a" * 40,
            "digest": "d" * 64,
            "payload": {
                "manifest_version": 1,
                "initiative_id": "i",
                "title": "Exact",
                "description": "instructions",
                "packets": [{
                    "id": "P1",
                    "title": "Exact",
                    "objective": "Fix exact thing",
                    "depends_on": [],
                    "acceptance_criteria": ["verified"],
                    "allowed_paths": ["gateway/example.py"],
                    "validation_commands": ["python -m pytest tests/test_example.py -q"],
                }],
            },
        },
    }

    prompt = mission_runtime._plan_review_prompt(mission)

    assert "python -m pytest tests/test_example.py -q" in prompt
    assert '"allowed_paths": ["gateway/example.py"]' in prompt
    assert '"initiative_id": "i"' in prompt

def test_request_plan_review_does_not_reuse_running_review_for_old_plan_digest(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def exercise() -> None:
        mission = _plan_review_mission(mission_db, mission_id="mission-new-digest")
        from gateway import automation_runs

        monkeypatch.setattr(automation_runs, "DB_FILE", mission_db)
        old = automation_runs.begin_run(
            automation_id="mission-plan-review:mission-new-digest",
            action=mission_runtime.ACTION_NAME,
            trigger_kind="signal",
            trigger_ref="old-plan-digest",
        )
        captured: list[dict] = []

        async def run_action(name, **kwargs):
            captured.append({"name": name, **kwargs})
            return {"id": "arun-new-plan", "status": "completed"}

        monkeypatch.setattr(automation_actions, "run_action", run_action)

        result = await mission_runtime.request_plan_review(mission["mission_id"])

        assert old["status"] == "running"
        assert result["id"] == "arun-new-plan"
        assert len(captured) == 1
        assert captured[0]["trigger_ref"] == mission["plan"]["digest"]

    asyncio.run(exercise())


# ---------------------------------------------------------------------------
# Paid Mission-review admission guard — fail-closed by default.
#
# All three real entry paths (startup recovery, the Automation/runtime action,
# and a direct internal call) funnel through
# builder_loop.run_independent_readonly_review. These tests exercise the real
# chain (no mocking of run_plan_verifier/run_independent_readonly_review) and
# prove zero dispatch: no subprocess is spawned, so no paid model call and no
# credential exposure can happen, regardless of whether a provider key is
# present in the environment.
# ---------------------------------------------------------------------------


def _plan_review_mission_with_matching_payload(
    db_path: Path, *, mission_id: str = "mission-guard"
) -> dict:
    payload = {
        "manifest_version": 1,
        "initiative_id": mission_id,
        "title": "Guard fixture",
        "description": "prove the paid review admission guard",
        "packets": [{
            "id": "P1",
            "title": "Guard fixture",
            "objective": "prove the guard",
            "depends_on": [],
            "acceptance_criteria": ["contained"],
            "allowed_paths": ["gateway/example.py"],
            "validation_commands": [],
        }],
    }
    memory_mission.create_mission(
        mission_id=mission_id,
        objective="Ship the reviewed plan safely",
        definition_of_done=["The plan is independently reviewed before execution."],
        supervisor_id="kitty",
        db_path=db_path,
    )
    return memory_mission.set_plan(
        mission_id,
        plan_ref="docs/superpowers/plans/review-proof.md@" + "a" * 40,
        plan_digest=bi.manifest_sha256(payload),
        plan_payload=payload,
        db_path=db_path,
    )


@pytest.mark.asyncio
async def test_startup_recovery_dispatches_zero_paid_provider_calls_when_not_admitted(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gateway/app.py calls request_pending_reviews() on startup; the real
    chain must reach the admission guard and dispatch nothing."""
    from gateway import action_grants, automation_runs

    mission = _plan_review_mission_with_matching_payload(
        mission_db, mission_id="mission-startup-guard"
    )
    monkeypatch.setattr(automation_runs, "DB_FILE", mission_db)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", mission_db)
    monkeypatch.setattr(repo_tools, "repo_root", lambda: mission_db.parent)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-value-must-not-be-read")
    monkeypatch.delenv(pra.ADMISSION_ENV_VAR, raising=False)
    spawned: list[object] = []
    monkeypatch.setattr(builder_loop.subprocess, "run", lambda *a, **k: spawned.append((a, k)))
    mission_runtime.register_action()

    receipts = await mission_runtime.request_pending_reviews()

    assert len(receipts) == 1
    assert receipts[0]["status"] == "source_unavailable"
    assert "awaiting authorization" in receipts[0]["error"]
    assert spawned == []
    current = memory_mission.get_mission(mission["mission_id"], db_path=mission_db)
    assert current["status"] == "PLAN_REVIEW"
    assert current["plan"]["review_state"] == "unreviewed"


@pytest.mark.asyncio
async def test_review_pending_action_dispatches_zero_paid_provider_calls_when_not_admitted(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Automation/runtime action handler must hit the same chokepoint."""
    mission = _plan_review_mission_with_matching_payload(
        mission_db, mission_id="mission-pending-guard"
    )
    monkeypatch.setattr(repo_tools, "repo_root", lambda: mission_db.parent)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-value-must-not-be-read")
    monkeypatch.delenv(pra.ADMISSION_ENV_VAR, raising=False)
    spawned: list[object] = []
    monkeypatch.setattr(builder_loop.subprocess, "run", lambda *a, **k: spawned.append((a, k)))

    with pytest.raises(automation_actions.SourceUnavailable, match="awaiting authorization"):
        await mission_runtime.review_pending_action({"mission_id": mission["mission_id"]})

    assert spawned == []
    current = memory_mission.get_mission(mission["mission_id"], db_path=mission_db)
    assert current["status"] == "PLAN_REVIEW"
    assert current["plan"]["review_state"] == "unreviewed"


def test_review_plan_direct_call_cannot_bypass_admission_zero_dispatch(
    mission_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A direct internal review_plan()/run_plan_verifier() call must not be
    able to reach dispatch either — there is only one chokepoint."""
    mission = _plan_review_mission_with_matching_payload(
        mission_db, mission_id="mission-direct-guard"
    )
    monkeypatch.setattr(repo_tools, "repo_root", lambda: mission_db.parent)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-value-must-not-be-read")
    monkeypatch.delenv(pra.ADMISSION_ENV_VAR, raising=False)
    spawned: list[object] = []
    monkeypatch.setattr(builder_loop.subprocess, "run", lambda *a, **k: spawned.append((a, k)))

    with pytest.raises(automation_actions.SourceUnavailable, match="awaiting authorization"):
        mission_runtime.review_plan(mission["mission_id"])

    assert spawned == []
    current = memory_mission.get_mission(mission["mission_id"], db_path=mission_db)
    assert current["status"] == "PLAN_REVIEW"
    assert current["plan"]["review_state"] == "unreviewed"


def test_paid_review_guard_refuses_on_policy_even_with_valid_provider_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard is a policy refusal, not an accident of a missing key: it
    must refuse even when OPENROUTER_API_KEY is present in the environment."""
    monkeypatch.delenv(pra.ADMISSION_ENV_VAR, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-value-present-in-env")
    spawned: list[object] = []
    monkeypatch.setattr(builder_loop.subprocess, "run", lambda *a, **k: spawned.append((a, k)))

    with pytest.raises(builder_loop.LoopError, match="awaiting authorization"):
        builder_loop.run_independent_readonly_review("Review this exact plan.", root=tmp_path)

    assert spawned == []
