from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from gateway import image_plan_store
from gateway import image_sessions as sessions
from gateway.image_plan_types import (
    CastSlot,
    ImagePlanError,
    ReferenceBinding,
    build_image_plan,
)


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
    image_plan_store._ensure_db(conn)
    conn.commit()
    conn.close()
    return db


def test_persisted_intent_round_trips_across_store_reopen(isolated_plan_db) -> None:
    session = sessions.create_session(title="intent")
    stored = image_plan_store.persist_plan(
        session.session_id,
        build_image_plan("portrait in window light"),
    )

    assert stored.intent["intent_version"] == 1
    assert stored.intent["operation"] == "txt2img"
    resumed = image_plan_store.require_plan(stored.plan_id)
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
    stored = image_plan_store.persist_plan(
        session.session_id,
        build_image_plan("portrait"),
    )

    with sqlite3.connect(isolated_plan_db) as conn:
        conn.execute(
            "UPDATE image_plans SET intent_json = ? WHERE plan_id = ?",
            ('{"intent_version":999,"operation":"txt2img"}', stored.plan_id),
        )
        conn.commit()

    with pytest.raises(image_plan_store.PlanMalformedError, match="intent_version"):
        image_plan_store.require_plan(stored.plan_id)


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
    stored = image_plan_store.persist_plan(session.session_id, plan)
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
    stored = image_plan_store.persist_plan(session.session_id, plan)

    recipe = SimpleNamespace(
        recipe_id="flux2_test",
        provider="flux2",
        execution_target="flux2_test_target",
        default_width=1024,
        default_height=1024,
        workflow_template_id=None,
        supports_characters=True,
        supports_pose_refs=True,
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
    # Role-aware selection reorders identity references ahead of optional
    # references (identity anchors the subject), so ref_identity now precedes
    # ref_pose even though the plan stored pose first.
    assert [(ref.reference_id, ref.role, ref.order) for ref in compiled.references] == [
        ("ref_identity", "identity", 1),
        ("ref_pose", "pose", 2),
    ]
    assert captured["reference_bytes"] == (b"identity", b"pose")


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

    with pytest.raises(image_plan_store.PlanStoreError, match="unsupported role"):
        image_plan_store.persist_plan(session.session_id, payload)


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

    with pytest.raises(image_plan_store.PlanStoreError, match="weight"):
        image_plan_store.persist_plan(session.session_id, payload)

def test_build_plan_emits_two_character_cast_with_independent_primary_refs(monkeypatch) -> None:
    from gateway import image_characters as characters

    chars = {
        "char_a": SimpleNamespace(character_id="char_a", name="Alex", description="adult man A"),
        "char_b": SimpleNamespace(character_id="char_b", name="Ben", description="adult man B"),
    }
    refs = {
        "char_a": [SimpleNamespace(ref_id="ref_a", storage_path="/tmp/a.png", is_primary=True, soft_deleted=False)],
        "char_b": [SimpleNamespace(ref_id="ref_b", storage_path="/tmp/b.png", is_primary=True, soft_deleted=False)],
    }
    monkeypatch.setattr(characters, "get_character", lambda cid: chars[cid])
    monkeypatch.setattr(characters, "list_character_refs", lambda cid: refs[cid])

    plan = build_image_plan(
        "Alex and Ben standing together",
        cast=[
            CastSlot("subject_1", "char_a", "Alex", position="left", depth_order=1),
            CastSlot("subject_2", "char_b", "Ben", position="right", depth_order=2),
        ],
    )
    payload = plan.to_dict()

    assert payload["character_id"] is None
    assert payload["character_ref_path"] is None
    assert payload["intent"]["cast"] == [
        {
            "slot_id": "subject_1",
            "character_id": "char_a",
            "display_name": "Alex",
            "position": "left",
            "depth_order": 1,
        },
        {
            "slot_id": "subject_2",
            "character_id": "char_b",
            "display_name": "Ben",
            "position": "right",
            "depth_order": 2,
        },
    ]
    assert payload["intent"]["references"] == [
        {"reference_id": "ref_a", "role": "identity", "cast_slot": "subject_1", "weight": None},
        {"reference_id": "ref_b", "role": "identity", "cast_slot": "subject_2", "weight": None},
    ]
    assert {(r["reference_id"], r["character_id"]) for r in payload["references"]} == {
        ("ref_a", "char_a"),
        ("ref_b", "char_b"),
    }


def test_build_plan_rejects_cross_character_reference_binding(monkeypatch) -> None:
    from gateway import image_characters as characters

    chars = {
        "char_a": SimpleNamespace(character_id="char_a", name="Alex", description="adult man A"),
        "char_b": SimpleNamespace(character_id="char_b", name="Ben", description="adult man B"),
    }
    refs = {
        "char_a": [SimpleNamespace(ref_id="ref_a", storage_path="/tmp/a.png", is_primary=True, soft_deleted=False)],
        "char_b": [SimpleNamespace(ref_id="ref_b", storage_path="/tmp/b.png", is_primary=True, soft_deleted=False)],
    }
    monkeypatch.setattr(characters, "get_character", lambda cid: chars[cid])
    monkeypatch.setattr(characters, "list_character_refs", lambda cid: refs[cid])

    with pytest.raises(ImagePlanError, match="belongs to character 'char_b'.*subject_1.*char_a"):
        build_image_plan(
            "Alex and Ben",
            cast=[CastSlot("subject_1", "char_a"), CastSlot("subject_2", "char_b")],
            reference_bindings=[
                ReferenceBinding("ref_b", "identity", "subject_1"),
                ReferenceBinding("ref_a", "identity", "subject_2"),
            ],
        )


def test_persist_plan_rejects_cross_character_reference_binding(isolated_plan_db) -> None:
    session = sessions.create_session(title="cross-bound references")
    plan = build_image_plan("two people")
    payload = plan.to_dict()
    payload["references"] = [
        {
            "character_id": "char_a",
            "name": "Alex",
            "path": "/tmp/a.png",
            "reason": "identity",
            "reference_id": "ref_a",
        },
        {
            "character_id": "char_b",
            "name": "Ben",
            "path": "/tmp/b.png",
            "reason": "identity",
            "reference_id": "ref_b",
        },
    ]
    payload["intent"]["cast"] = [
        {"slot_id": "subject_1", "character_id": "char_a", "display_name": "Alex", "position": "left", "depth_order": 1},
        {"slot_id": "subject_2", "character_id": "char_b", "display_name": "Ben", "position": "right", "depth_order": 2},
    ]
    payload["intent"]["references"] = [
        {"reference_id": "ref_b", "role": "identity", "cast_slot": "subject_1", "weight": None},
        {"reference_id": "ref_a", "role": "identity", "cast_slot": "subject_2", "weight": None},
    ]

    with pytest.raises(image_plan_store.PlanStoreError, match="belongs to character 'char_b'.*subject_1.*char_a"):
        image_plan_store.persist_plan(session.session_id, payload)


def test_persist_plan_rejects_invalid_cast_placement(isolated_plan_db) -> None:
    session = sessions.create_session(title="invalid placement")
    plan = build_image_plan("portrait")
    payload = plan.to_dict()
    payload["intent"]["cast"] = [
        {
            "slot_id": "subject_1",
            "character_id": "char_a",
            "display_name": "Alex",
            "position": "   ",
            "depth_order": True,
        }
    ]

    with pytest.raises(image_plan_store.PlanStoreError, match="position|depth_order"):
        image_plan_store.persist_plan(session.session_id, payload)


@pytest.mark.asyncio
async def test_dispatch_fails_closed_on_unsupported_reference_capability(
    isolated_plan_db, tmp_path: Path, monkeypatch
) -> None:
    """A recipe that cannot carry a bound reference role must fail the dispatch.

    This proves the role-aware ReferenceSelector is enforced at the route:
    a pose reference against a recipe without ``supports_pose_refs`` raises a
    400 instead of silently dropping the reference.
    """
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from gateway import image_jobs
    from gateway.routes import extended

    session = sessions.create_session(title="fail-closed capability")
    pose_path = tmp_path / "pose.png"
    pose_path.write_bytes(b"pose")

    plan = {
        "original_prompt": "James in this pose",
        "refined_prompt": "James in this pose",
        "character_id": "char_james",
        "character_ref_path": str(pose_path),
        "recipe_id": "flux2_test",
        "guidance_tags": [],
        "references": [
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
    stored = image_plan_store.persist_plan(session.session_id, plan)

    recipe = SimpleNamespace(
        recipe_id="flux2_test",
        provider="flux2",
        execution_target="flux2_test_target",
        default_width=1024,
        default_height=1024,
        workflow_template_id=None,
        supports_characters=True,
        supports_pose_refs=False,
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

    with pytest.raises(StarletteHTTPException) as exc_info:
        await extended.studio_generate(
            extended.StudioGenerateRequest(
                prompt="ignored",
                plan_id=stored.plan_id,
                session_id=session.session_id,
            )
        )

    assert exc_info.value.status_code == 400
    assert "supports_pose_refs" in str(exc_info.value.detail)
    assert captured == {}  # no spend, no run, no silent drop
