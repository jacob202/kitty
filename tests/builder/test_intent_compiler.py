from src.builder.contracts import BuilderBrief
from src.builder.intent_compiler import compile_intent


def test_builder_brief_round_trips_to_dict():
    brief = BuilderBrief(
        raw_input="fix command stuff and make sure it works",
        normalized_goal="Consolidate command handling behind CommandEngine.",
        non_goals=["Do not change UI styling."],
        success_criteria=["/api/command handles /stuck."],
        validation_commands=["venv/bin/python -m pytest tests/test_command_engine.py -q"],
        allowed_files=["src/core/command_engine.py"],
        forbidden_files=["garage-ui/"],
        assumptions=["Use existing Flask route contracts."],
        ambiguities=[],
        blocking_question="",
        context_targets=["CURRENT_FOCUS.md", "specs/unified-command-system-candidate-c.spec.md"],
        risk_level="medium",
        recommended_execution_mode="single_worker",
        handoff_prompt="Implement the approved CommandEngine spec.",
        confidence=0.82,
    )

    data = brief.to_dict()
    assert data["normalized_goal"] == "Consolidate command handling behind CommandEngine."
    assert data["risk_level"] == "medium"
    assert data["recommended_execution_mode"] == "single_worker"
    assert "next_agent_packet" in data


def test_compile_intent_turns_brain_dump_into_contract(tmp_path):
    (tmp_path / "CURRENT_FOCUS.md").write_text(
        "# Current Focus\n\n## Forbidden Work\n\n- MCP expansion\n- QLoRA\n",
        encoding="utf-8",
    )
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "unified-command-system-candidate-c.spec.md").write_text(
        "# Unified Command System Candidate C\n",
        encoding="utf-8",
    )

    brief = compile_intent(
        tmp_path,
        "continue the command system thing through kittybuilder, verify it works, do not do UI polish",
    )

    assert "command" in brief.normalized_goal.lower()
    assert "garage-ui/" in brief.forbidden_files
    assert "specs/unified-command-system-candidate-c.spec.md" in brief.context_targets
    assert brief.recommended_execution_mode in {"single_worker", "review_gate", "intake_only"}
    assert brief.blocking_question == ""
    assert brief.next_agent_packet["schema_version"] == "builder_handoff.v1"
    assert brief.next_agent_packet["objective"] == brief.normalized_goal
    assert "output_contract" in brief.next_agent_packet


def test_compile_intent_asks_one_question_for_vague_cleanup(tmp_path):
    (tmp_path / "CURRENT_FOCUS.md").write_text("# Current Focus\n", encoding="utf-8")
    brief = compile_intent(tmp_path, "clean up everything and make it better")
    assert brief.recommended_execution_mode == "human_question"
    assert brief.blocking_question
    assert len(brief.ambiguities) >= 1
    assert brief.next_agent_packet["recommended_mode"] == "human_question"
    assert brief.next_agent_packet["blocking_question"] == brief.blocking_question
