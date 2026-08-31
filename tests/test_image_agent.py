"""Tests for the bounded image-specialist controller (issue #336, slice A3).

Covers A3's acceptance: strict output parsing, a hard loop bound, rejection of
ids the session does not own, budget refusal, and loud failure on malformed
model output. Also pins the capability boundary — an "edit" must fail while the
renderer has no image-to-image workflow, rather than downgrading to a reroll.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from gateway import image_agent, image_jobs, image_plan_store, image_recipes
from gateway import image_sessions as sessions
from gateway.image_agent import (
    AgentBudget,
    AgentLoopExhaustedError,
    AgentProtocolError,
    BudgetRefusedError,
    CapabilityError,
    ImageAgentError,
    UnknownReferenceError,
    UnsupportedOperationError,
    decide,
)


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path, monkeypatch):
    test_db = tmp_path / "kitty.db"
    test_db.parent.mkdir(parents=True, exist_ok=True)
    import gateway.paths as gp

    original = gp.KITTY_DB_FILE
    gp.KITTY_DB_FILE = test_db
    # image_recipes binds KITTY_DB_FILE at import, so the module-level name has
    # to be redirected too or the recipe table lands in the real database.
    monkeypatch.setattr("gateway.image_recipes.KITTY_DB_FILE", test_db)

    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    image_plan_store._ensure_db(conn)
    conn.commit()
    conn.close()

    image_recipes.seed_default_recipes()

    yield test_db

    gp.KITTY_DB_FILE = original


def _scripted(*responses: str):
    """An LLM stub that replays *responses* in order and records its prompts."""
    calls: list[list[dict[str, str]]] = []
    remaining = list(responses)

    def _call(messages: list[dict[str, str]]) -> str:
        calls.append(messages)
        if not remaining:
            raise AssertionError("scripted llm called more times than scripted")
        return remaining.pop(0)

    _call.calls = calls  # type: ignore[attr-defined]
    return _call


def _generate_action(**overrides) -> str:
    payload = {
        "action": "generate",
        "prompt": "a portrait in golden-hour light",
        "summary": "Rendering a golden-hour portrait.",
    }
    payload.update(overrides)
    return json.dumps(payload)


def _succeeded_job(session_id: str, tmp_path: Path) -> str:
    """A job that can legitimately serve as an anchor."""
    job = image_jobs.create_job(
        provider="comfyui", operation="txt2img", prompt="first render"
    )
    image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.SUBMITTED)
    image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.RUNNING)
    artifact = tmp_path / f"{job.job_id}.png"
    artifact.write_bytes(b"png")
    image_jobs.update_job(
        job.job_id, output_path=str(artifact), artifact_id=f"art_{job.job_id}"
    )
    image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.SUCCEEDED)
    sessions.attach_job(session_id, job.job_id)
    return job.job_id


class TestStrictParsing:
    def test_non_json_output_fails_loudly(self):
        s = sessions.create_session(title="parse")
        with pytest.raises(AgentProtocolError, match="not valid JSON"):
            decide(s.session_id, "make me a portrait", llm=_scripted("sure thing!"))

    def test_json_array_is_rejected(self):
        s = sessions.create_session(title="parse")
        with pytest.raises(AgentProtocolError, match="must be a JSON object"):
            decide(s.session_id, "make me a portrait", llm=_scripted('["generate"]'))

    def test_missing_action_is_rejected(self):
        s = sessions.create_session(title="parse")
        with pytest.raises(AgentProtocolError, match="no action"):
            decide(s.session_id, "portrait", llm=_scripted('{"prompt": "a cat"}'))

    def test_unknown_action_is_rejected(self):
        s = sessions.create_session(title="parse")
        with pytest.raises(AgentProtocolError, match="unknown action 'upscale'"):
            decide(s.session_id, "portrait", llm=_scripted('{"action": "upscale"}'))

    def test_missing_required_field_is_rejected(self):
        s = sessions.create_session(title="parse")
        raw = json.dumps({"action": "generate", "prompt": "a cat"})
        with pytest.raises(AgentProtocolError, match="missing required field"):
            decide(s.session_id, "portrait", llm=_scripted(raw))

    def test_unexpected_field_is_rejected(self):
        """A silently dropped field reads to the user as an honoured one."""
        s = sessions.create_session(title="parse")
        with pytest.raises(AgentProtocolError, match="unexpected field\\(s\\): denoise"):
            decide(
                s.session_id, "portrait", llm=_scripted(_generate_action(denoise=0.4))
            )

    def test_blank_required_string_is_rejected(self):
        s = sessions.create_session(title="parse")
        with pytest.raises(AgentProtocolError, match="must be a non-empty string"):
            decide(s.session_id, "portrait", llm=_scripted(_generate_action(prompt="  ")))

    def test_non_list_guidance_tags_rejected(self):
        s = sessions.create_session(title="parse")
        with pytest.raises(AgentProtocolError, match="must be a list"):
            decide(
                s.session_id,
                "portrait",
                llm=_scripted(_generate_action(guidance_tags="text_rendering")),
            )

    def test_repeated_list_entry_rejected(self):
        s = sessions.create_session(title="parse")
        raw = _generate_action(guidance_tags=["text_rendering", "text_rendering"])
        with pytest.raises(AgentProtocolError, match="repeats entry"):
            decide(s.session_id, "portrait", llm=_scripted(raw))

    def test_empty_request_is_refused_before_any_llm_call(self):
        s = sessions.create_session(title="parse")
        llm = _scripted()
        with pytest.raises(ImageAgentError, match="request must not be empty"):
            decide(s.session_id, "   ", llm=llm)
        assert llm.calls == []


class TestGenerate:
    def test_generate_persists_an_approved_plan(self):
        s = sessions.create_session(title="generate")
        decision = decide(
            s.session_id,
            "a portrait in golden-hour light",
            llm=_scripted(_generate_action(guidance_tags=["text_rendering"])),
        )

        assert decision.action == "generate"
        assert decision.operation == "txt2img"
        assert decision.rounds_used == 1
        assert decision.guidance_tags == ["text_rendering"]

        stored = image_plan_store.require_approved_plan(decision.plan_id, s.session_id)
        assert stored.original_prompt == "a portrait in golden-hour light"
        assert stored.guidance_tags == ["text_rendering"]

    def test_user_preferred_recipe_overrides_model_recipe_choice(self):
        s = sessions.create_session(title="generate")
        image_recipes.set_recipe_available("openai_gpt_image_2", True)
        decision = decide(
            s.session_id,
            "a portrait",
            preferred_recipe="openai_gpt_image_2",
            llm=_scripted(_generate_action(recipe_id="comfyui_sdxl_standard")),
        )

        assert decision.recipe_id == "openai_gpt_image_2"
        stored = image_plans.require_approved_plan(decision.plan_id, s.session_id)
        assert stored.recipe_id == "openai_gpt_image_2"

    def test_generate_records_the_turns_and_last_plan(self):
        s = sessions.create_session(title="generate")
        decision = decide(
            s.session_id, "a portrait", llm=_scripted(_generate_action())
        )

        turns = sessions.list_turns(s.session_id)
        assert [t.role.value for t in turns] == ["user", "assistant"]
        assert turns[0].content == "a portrait"
        assert turns[1].content == decision.summary

        refreshed = sessions.require_session(s.session_id)
        assert refreshed.last_plan["plan_id"] == decision.plan_id

    def test_unknown_guidance_tag_is_rejected(self):
        s = sessions.create_session(title="generate")
        raw = _generate_action(guidance_tags=["make_it_pop"])
        with pytest.raises(UnsupportedOperationError, match="unknown guidance tag"):
            decide(s.session_id, "a portrait", llm=_scripted(raw))

    def test_no_plan_is_persisted_when_the_action_is_rejected(self):
        """A rejected action must not leave a dispatchable plan behind."""
        s = sessions.create_session(title="generate")
        raw = _generate_action(guidance_tags=["make_it_pop"])
        with pytest.raises(UnsupportedOperationError):
            decide(s.session_id, "a portrait", llm=_scripted(raw))

        import gateway.paths as gp
        from gateway import db as kitty_db

        with kitty_db.connect(gp.KITTY_DB_FILE) as conn:
            rows = conn.execute("SELECT COUNT(*) AS n FROM image_plans").fetchone()
        assert rows["n"] == 0


class TestUnknownReferences:
    def test_character_outside_the_session_is_rejected(self):
        s = sessions.create_session(title="refs")
        raw = _generate_action(character_id="char_someone_else")
        with pytest.raises(UnknownReferenceError, match="char_someone_else"):
            decide(s.session_id, "a portrait", llm=_scripted(raw))

    def test_anchor_the_user_never_selected_is_rejected(self, tmp_path: Path):
        s = sessions.create_session(title="refs")
        anchor = _succeeded_job(s.session_id, tmp_path)
        other = _succeeded_job(s.session_id, tmp_path)
        sessions.set_anchor(s.session_id, anchor)

        raw = json.dumps(
            {
                "action": "edit",
                "prompt": "broader build",
                "summary": "Broadening the build.",
                "anchor_job_id": other,
            }
        )
        with pytest.raises(UnknownReferenceError, match="is not the current anchor"):
            decide(s.session_id, "broader build", llm=_scripted(raw))

    def test_unknown_guidance_tag_in_a_read_action_is_rejected(self):
        s = sessions.create_session(title="refs")
        raw = json.dumps({"action": "get_guidance", "tag": "not_a_real_tag"})
        with pytest.raises(UnknownReferenceError, match="unknown guidance tag"):
            decide(s.session_id, "a portrait", llm=_scripted(raw))


class TestEditCapability:
    def test_edit_without_an_anchor_is_refused(self):
        s = sessions.create_session(title="edit")
        raw = json.dumps(
            {
                "action": "edit",
                "prompt": "broader build",
                "summary": "Broadening the build.",
            }
        )
        with pytest.raises(UnsupportedOperationError, match="no selected result"):
            decide(s.session_id, "broader build", llm=_scripted(raw))

    def test_edit_is_refused_while_no_edit_workflow_is_installed(
        self, tmp_path: Path, monkeypatch
    ):
        """A prompt-only reroll is not an edit — issue #336's explicit fail case."""
        monkeypatch.setattr(image_agent, "_WORKFLOWS_DIR", tmp_path / "workflows")
        s = sessions.create_session(title="edit")
        sessions.set_anchor(s.session_id, _succeeded_job(s.session_id, tmp_path))

        raw = json.dumps(
            {
                "action": "edit",
                "prompt": "keep the face, broader build",
                "summary": "Keeping the face, broadening the build.",
                "protected_traits": ["face"],
                "requested_changes": ["broader build"],
            }
        )
        with pytest.raises(CapabilityError, match="image_to_image_v1"):
            decide(s.session_id, "broader build", llm=_scripted(raw))

    def test_hosted_openai_edit_does_not_depend_on_local_worker_bundle(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr(image_agent, "_WORKFLOWS_DIR", tmp_path / "missing-workflows")
        image_recipes.set_recipe_available("openai_gpt_image_2", True)
        s = sessions.create_session(title="hosted edit")
        anchor = _succeeded_job(s.session_id, tmp_path)
        sessions.set_anchor(s.session_id, anchor)
        raw = json.dumps({
            "action": "edit",
            "prompt": "keep the face, change only the jacket",
            "summary": "Changing only the jacket.",
            "protected_traits": ["face"],
            "requested_changes": ["jacket"],
        })

        decision = decide(
            s.session_id, "change the jacket",
            preferred_recipe="openai_gpt_image_2", llm=_scripted(raw),
        )

        assert decision.action == "edit"
        assert decision.recipe_id == "openai_gpt_image_2"
        assert decision.anchor_job_id == anchor

    def test_edit_succeeds_once_the_workflow_bundle_exists(
        self, tmp_path: Path, monkeypatch
    ):
        workflows = tmp_path / "workflows"
        (workflows / image_agent.EDIT_WORKFLOW_ID).mkdir(parents=True)
        monkeypatch.setattr(image_agent, "_WORKFLOWS_DIR", workflows)

        s = sessions.create_session(title="edit")
        anchor = _succeeded_job(s.session_id, tmp_path)
        sessions.set_anchor(s.session_id, anchor)

        raw = json.dumps(
            {
                "action": "edit",
                "prompt": "keep the face, broader build",
                "summary": "Keeping the face, broadening the build.",
                "protected_traits": ["face", "clothing"],
                "requested_changes": ["broader build"],
            }
        )
        decision = decide(s.session_id, "broader build", llm=_scripted(raw))

        assert decision.action == "edit"
        assert decision.operation == "img2img"
        assert decision.anchor_job_id == anchor
        assert decision.protected_traits == ["face", "clothing"]

        stored = image_plan_store.require_approved_plan(decision.plan_id, s.session_id)
        assert stored.intent["operation"] == "img2img"
        assert stored.intent["protected_traits"] == ["face", "clothing"]
        assert stored.intent["requested_changes"] == ["broader build"]

        refreshed = sessions.require_session(s.session_id)
        assert refreshed.protected_traits == ["face", "clothing"]
        assert refreshed.requested_changes == ["broader build"]

    def test_edit_is_refused_when_no_recipe_supports_img2img(
        self, tmp_path: Path, monkeypatch
    ):
        workflows = tmp_path / "workflows"
        (workflows / image_agent.EDIT_WORKFLOW_ID).mkdir(parents=True)
        monkeypatch.setattr(image_agent, "_WORKFLOWS_DIR", workflows)

        text_only = image_recipes.get_recipe("comfyui_sdxl_standard")
        text_only.supports_img2img = False
        monkeypatch.setattr(
            "gateway.image_recipes.auto_route",
            lambda **_: image_recipes.RoutingDecision(
                text_only.recipe_id, text_only, "forced text-only recipe"
            ),
        )

        s = sessions.create_session(title="edit")
        sessions.set_anchor(s.session_id, _succeeded_job(s.session_id, tmp_path))

        raw = json.dumps(
            {
                "action": "edit",
                "prompt": "broader build",
                "summary": "Broadening the build.",
            }
        )
        with pytest.raises(CapabilityError, match="img2img"):
            decide(s.session_id, "broader build", llm=_scripted(raw))


class TestLoopBound:
    def test_read_only_actions_exhaust_the_loop_and_raise(self):
        s = sessions.create_session(title="loop")
        llm = _scripted(*['{"action": "list_assets"}'] * image_agent.MAX_ROUNDS)

        with pytest.raises(AgentLoopExhaustedError, match="all 3 rounds"):
            decide(s.session_id, "a portrait", llm=llm)

        assert len(llm.calls) == image_agent.MAX_ROUNDS

    def test_read_action_observation_is_fed_back_and_decision_follows(self):
        s = sessions.create_session(title="loop")
        llm = _scripted('{"action": "list_assets"}', _generate_action())

        decision = decide(s.session_id, "a portrait", llm=llm)

        assert decision.rounds_used == 2
        assert decision.observations and decision.observations[0].startswith(
            "list_assets:"
        )
        second_call = llm.calls[1]
        assert any("Observation for list_assets" in m["content"] for m in second_call)

    def test_max_rounds_below_one_is_refused(self):
        s = sessions.create_session(title="loop")
        with pytest.raises(ImageAgentError, match="max_rounds must be at least 1"):
            decide(s.session_id, "a portrait", llm=_scripted(), max_rounds=0)


class TestBudget:
    def test_attempt_ceiling_refuses_generation(self):
        s = sessions.create_session(title="budget")
        sessions.record_attempt(s.session_id)
        sessions.record_attempt(s.session_id)

        with pytest.raises(BudgetRefusedError, match="2 of 2 allowed attempts"):
            decide(
                s.session_id,
                "a portrait",
                budget=AgentBudget(max_attempts=2),
                llm=_scripted(_generate_action()),
            )

    def test_spend_ceiling_refuses_generation(self):
        s = sessions.create_session(title="budget")
        sessions.record_attempt(s.session_id, cost_usd=1.50)

        with pytest.raises(BudgetRefusedError, match=r"\$1.50 of its \$1.00"):
            decide(
                s.session_id,
                "a portrait",
                budget=AgentBudget(max_spend_usd=1.00),
                llm=_scripted(_generate_action()),
            )

    def test_clarify_is_allowed_on_a_spent_budget(self):
        """Refusing to answer a question is not how a budget should be enforced."""
        s = sessions.create_session(title="budget")
        sessions.record_attempt(s.session_id, cost_usd=9.99)

        raw = json.dumps({"action": "clarify", "question": "Which reference?"})
        decision = decide(
            s.session_id,
            "make it better",
            budget=AgentBudget(max_spend_usd=1.00),
            llm=_scripted(raw),
        )
        assert decision.action == "clarify"
        assert decision.question == "Which reference?"


class TestTerminalActions:
    def test_cancel_carries_its_reason(self):
        s = sessions.create_session(title="terminal")
        raw = json.dumps({"action": "cancel", "reason": "no reference to work from"})
        decision = decide(s.session_id, "do the thing", llm=_scripted(raw))

        assert decision.action == "cancel"
        assert decision.reason == "no reference to work from"
        assert decision.plan_id is None

    def test_ended_session_cannot_be_driven(self):
        s = sessions.create_session(title="terminal")
        sessions.end_session(s.session_id)
        llm = _scripted()

        with pytest.raises(UnsupportedOperationError, match="open a new session"):
            decide(s.session_id, "a portrait", llm=llm)
        assert llm.calls == []

    def test_unknown_session_raises(self):
        with pytest.raises(sessions.SessionNotFoundError):
            decide("imgses_nope", "a portrait", llm=_scripted())


class TestRegistry:
    def test_registry_lists_only_ids_the_session_owns(self, tmp_path: Path):
        s = sessions.create_session(
            title="registry", character_id="char_james", reference_ids=["ref_1"]
        )
        job_id = _succeeded_job(s.session_id, tmp_path)
        sessions.set_anchor(s.session_id, job_id)

        registry = image_agent.session_registry(sessions.require_session(s.session_id))
        assert registry == {
            "characters": ["char_james"],
            "references": ["ref_1"],
            "jobs": [job_id],
            "anchor": [job_id],
        }

    def test_context_prompt_carries_the_registry_and_history(self):
        s = sessions.create_session(title="registry")
        llm = _scripted(_generate_action())
        decide(s.session_id, "a portrait", llm=llm)

        context = llm.calls[0][1]["content"]
        assert "registry" in context
        assert "available_guidance_tags" in context
        assert "a portrait" in context
