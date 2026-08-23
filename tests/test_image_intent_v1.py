from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from gateway import image_plans
from gateway import image_sessions as sessions
from gateway.image_plan import build_image_plan


def test_build_plan_emits_versioned_character_intent(monkeypatch) -> None:
    from gateway import image_characters as characters

    character = SimpleNamespace(
        character_id="char_james",
        name="James",
        description="adult male",
    )
    reference = SimpleNamespace(
        ref_id="ref_primary",
        storage_path="/tmp/james.png",
        is_primary=True,
        soft_deleted=False,
    )
    monkeypatch.setattr(characters, "get_character", lambda _cid: character)
    monkeypatch.setattr(characters, "list_character_refs", lambda _cid: [reference])

    plan = build_image_plan("James in window light", character_id="char_james")
    payload = plan.to_dict()

    assert payload["intent"] == {
        "intent_version": 1,
        "operation": "txt2img",
        "cast": [
            {
                "slot_id": "subject_1",
                "character_id": "char_james",
                "display_name": "James",
            }
        ],
        "references": [
            {
                "reference_id": "ref_primary",
                "role": "identity",
                "cast_slot": "subject_1",
                "weight": None,
            }
        ],
        "scene": {},
        "target": {},
        "requested_changes": [],
        "protected_traits": [],
        "content_lane": "safe",
        "consent_basis": None,
        "adult_confirmed": False,
        "privacy_required": False,
        "quality_request": {},
        "budget_request": {},
    }
    assert payload["references"][0]["reference_id"] == "ref_primary"


@pytest.fixture
def isolated_plan_db(tmp_path: Path, monkeypatch):
    import gateway.paths as gp

    db = tmp_path / "kitty.db"
    monkeypatch.setattr(gp, "KITTY_DB_FILE", db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    image_plans._ensure_db(conn)
    conn.commit()
    conn.close()
    return db


def test_persisted_intent_round_trips_across_store_reopen(isolated_plan_db) -> None:
    session = sessions.create_session(title="intent")
    stored = image_plans.persist_plan(
        session.session_id,
        build_image_plan("portrait in window light"),
    )

    assert stored.intent["intent_version"] == 1
    assert stored.intent["operation"] == "txt2img"
    resumed = image_plans.require_plan(stored.plan_id)
    assert resumed.intent == stored.intent

    with sqlite3.connect(isolated_plan_db) as conn:
        row = conn.execute(
            "SELECT intent_json FROM image_plans WHERE plan_id = ?",
            (stored.plan_id,),
        ).fetchone()
    assert row is not None
    assert row[0]


def test_build_plan_carries_edit_contract_in_intent() -> None:
    plan = build_image_plan(
        "change only the shirt",
        operation="img2img",
        requested_changes=["shirt: black"],
        protected_traits=["face", "body", "pose", "background"],
        target={"region": "shirt"},
    )

    intent = plan.to_dict()["intent"]
    assert intent["operation"] == "img2img"
    assert intent["requested_changes"] == ["shirt: black"]
    assert intent["protected_traits"] == ["face", "body", "pose", "background"]
    assert intent["target"] == {"region": "shirt"}


def test_corrupt_persisted_intent_fails_loud(isolated_plan_db) -> None:
    session = sessions.create_session(title="intent corruption")
    stored = image_plans.persist_plan(
        session.session_id,
        build_image_plan("portrait"),
    )

    with sqlite3.connect(isolated_plan_db) as conn:
        conn.execute(
            "UPDATE image_plans SET intent_json = ? WHERE plan_id = ?",
            ('{"intent_version":999,"operation":"txt2img"}', stored.plan_id),
        )
        conn.commit()

    with pytest.raises(image_plans.PlanMalformedError, match="intent_version"):
        image_plans.require_plan(stored.plan_id)


@pytest.mark.asyncio
async def test_stored_intent_not_mutable_session_drives_flux2_compiler(
    isolated_plan_db, monkeypatch
) -> None:
    from types import SimpleNamespace

    from gateway import image_jobs
    from gateway.routes import extended

    session = sessions.create_session(title="immutable edit contract")
    plan = build_image_plan(
        "portrait",
        requested_changes=["approved change"],
        protected_traits=["approved face"],
    )
    stored = image_plans.persist_plan(session.session_id, plan)
    sessions.update_session(
        session.session_id,
        requested_changes=["MUTATED change"],
        protected_traits=["MUTATED face"],
    )

    recipe = SimpleNamespace(
        recipe_id="flux2_test",
        provider="flux2",
        execution_target="flux2_test_target",
        default_width=1024,
        default_height=1024,
        workflow_template_id=None,
    )
    monkeypatch.setattr(
        "gateway.image_recipes.auto_route",
        lambda **_: SimpleNamespace(recipe=recipe, recipe_id=recipe.recipe_id, reason="test"),
    )
    target = SimpleNamespace(
        model_id="test-model",
        estimate_cost_usd=lambda *_args: 0.0,
    )
    monkeypatch.setattr("gateway.flux2_targets.resolve_flux2_target", lambda _name: target)

    captured = {}

    async def fake_run(engine, prompt, **kwargs):
        captured.update(kwargs)
        job = image_jobs.create_job(provider=engine, operation="txt2img", prompt=prompt)
        from gateway.image_runner import JobResult

        return JobResult(job_id=job.job_id, filename="/tmp/test.png", engine=engine)

    monkeypatch.setattr("gateway.image_runner.run", fake_run)

    await extended.studio_generate(
        extended.StudioGenerateRequest(
            prompt="ignored mutable request",
            plan_id=stored.plan_id,
            session_id=session.session_id,
        )
    )

    compiled = captured["compiled_request"]
    assert compiled.requested_changes == ("approved change",)
    assert compiled.protected_traits == ("approved face",)
    assert captured["plan_id"] == stored.plan_id
    assert json.loads(captured["intent_json"]) == stored.intent


@pytest.mark.asyncio
async def test_flux2_compiler_uses_typed_reference_roles_and_order(
    isolated_plan_db, tmp_path: Path, monkeypatch
) -> None:
    from types import SimpleNamespace

    from gateway import image_jobs
    from gateway.routes import extended

    session = sessions.create_session(title="reference roles")
    identity_path = tmp_path / "identity.png"
    pose_path = tmp_path / "pose.png"
    identity_path.write_bytes(b"identity")
    pose_path.write_bytes(b"pose")

    plan = {
        "original_prompt": "James in this pose",
        "refined_prompt": "James in this pose",
        "character_id": "char_james",
        "character_ref_path": str(identity_path),
        "recipe_id": "flux2_test",
        "guidance_tags": [],
        "references": [
            {
                "character_id": "char_james",
                "name": "James",
                "path": str(identity_path),
                "reason": "identity",
                "reference_id": "ref_identity",
            },
            {
                "character_id": "char_james",
                "name": "James pose",
                "path": str(pose_path),
                "reason": "pose",
                "reference_id": "ref_pose",
            },
        ],
        "content_lane": "safe",
        "consent_basis": None,
        "adult_confirmed": False,
        "intent": {
            "intent_version": 1,
            "operation": "txt2img",
            "cast": [
                {
                    "slot_id": "subject_1",
                    "character_id": "char_james",
                    "display_name": "James",
                }
            ],
            "references": [
                {
                    "reference_id": "ref_pose",
                    "role": "pose",
                    "cast_slot": "subject_1",
                    "weight": None,
                },
                {
                    "reference_id": "ref_identity",
                    "role": "identity",
                    "cast_slot": "subject_1",
                    "weight": None,
                },
            ],
            "scene": {},
            "target": {},
            "requested_changes": [],
            "protected_traits": [],
            "content_lane": "safe",
            "consent_basis": None,
            "adult_confirmed": False,
            "privacy_required": False,
            "quality_request": {},
            "budget_request": {},
        },
    }
    stored = image_plans.persist_plan(session.session_id, plan)

    recipe = SimpleNamespace(
        recipe_id="flux2_test",
        provider="flux2",
        execution_target="flux2_test_target",
        default_width=1024,
        default_height=1024,
        workflow_template_id=None,
    )
    monkeypatch.setattr(
        "gateway.image_recipes.auto_route",
        lambda **_: SimpleNamespace(recipe=recipe, recipe_id=recipe.recipe_id, reason="test"),
    )
    target = SimpleNamespace(
        model_id="test-model",
        estimate_cost_usd=lambda *_args: 0.0,
    )
    monkeypatch.setattr("gateway.flux2_targets.resolve_flux2_target", lambda _name: target)

    captured = {}

    async def fake_run(engine, prompt, **kwargs):
        captured.update(kwargs)
        job = image_jobs.create_job(provider=engine, operation="txt2img", prompt=prompt)
        from gateway.image_runner import JobResult

        return JobResult(job_id=job.job_id, filename="/tmp/test.png", engine=engine)

    monkeypatch.setattr("gateway.image_runner.run", fake_run)

    await extended.studio_generate(
        extended.StudioGenerateRequest(
            prompt="ignored",
            plan_id=stored.plan_id,
            session_id=session.session_id,
        )
    )

    compiled = captured["compiled_request"]
    assert [(ref.reference_id, ref.role, ref.order) for ref in compiled.references] == [
        ("ref_pose", "pose", 1),
        ("ref_identity", "identity", 2),
    ]
    assert captured["reference_bytes"] == (b"pose", b"identity")


def test_image_job_persists_plan_and_intent_provenance(isolated_plan_db) -> None:
    from gateway import image_jobs

    intent = {
        "intent_version": 1,
        "operation": "txt2img",
        "cast": [],
        "references": [],
        "scene": {},
        "target": {},
        "requested_changes": [],
        "protected_traits": [],
        "content_lane": "safe",
        "consent_basis": None,
        "adult_confirmed": False,
        "privacy_required": False,
        "quality_request": {},
        "budget_request": {},
    }
    job = image_jobs.create_job(
        provider="comfyui",
        operation="txt2img",
        prompt="portrait",
        plan_id="imgplan_123",
        intent_json=json.dumps(intent),
    )

    resumed = image_jobs.get_job(job.job_id)
    assert resumed is not None
    assert resumed.plan_id == "imgplan_123"
    assert json.loads(resumed.intent_json) == intent


def test_image_jobs_ensure_db_without_connection_adds_plan_provenance_columns(tmp_path: Path, monkeypatch) -> None:
    import gateway.paths as gp
    from gateway import image_jobs

    db = tmp_path / "standalone-image-jobs.db"
    monkeypatch.setattr(gp, "KITTY_DB_FILE", db)

    image_jobs._ensure_db()

    with sqlite3.connect(db) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(image_jobs)")}
    assert {"plan_id", "intent_json"}.issubset(cols)


def test_persist_plan_rejects_unknown_reference_role(isolated_plan_db) -> None:
    session = sessions.create_session(title="invalid role")
    plan = build_image_plan("portrait")
    payload = plan.to_dict()
    payload["intent"]["cast"] = [
        {"slot_id": "subject_1", "character_id": "char_james", "display_name": "James"}
    ]
    payload["intent"]["references"] = [
        {
            "reference_id": "ref_identity",
            "role": "nonsense_role",
            "cast_slot": "subject_1",
            "weight": 0.5,
        }
    ]

    with pytest.raises(image_plans.PlanStoreError, match="unsupported role"):
        image_plans.persist_plan(session.session_id, payload)


@pytest.mark.parametrize("weight", [True, -0.1, 0.0, 1.01, 999.0, float("inf"), float("nan")])
def test_persist_plan_rejects_invalid_reference_weight(isolated_plan_db, weight) -> None:
    session = sessions.create_session(title="invalid weight")
    plan = build_image_plan("portrait")
    payload = plan.to_dict()
    payload["intent"]["cast"] = [
        {"slot_id": "subject_1", "character_id": "char_james", "display_name": "James"}
    ]
    payload["intent"]["references"] = [
        {
            "reference_id": "ref_identity",
            "role": "identity",
            "cast_slot": "subject_1",
            "weight": weight,
        }
    ]

    with pytest.raises(image_plans.PlanStoreError, match="weight"):
        image_plans.persist_plan(session.session_id, payload)
