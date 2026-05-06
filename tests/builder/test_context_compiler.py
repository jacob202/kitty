from src.builder.context_compiler import build_context_pack
from src.builder.contracts import BuilderBrief


def test_context_pack_keeps_static_rules_first_and_acceptance_last(tmp_path):
    (tmp_path / "CURRENT_FOCUS.md").write_text("focus text\n" * 20, encoding="utf-8")

    brief = BuilderBrief(
        raw_input="do command work",
        normalized_goal="Advance command system.",
        success_criteria=["focused tests pass"],
        context_targets=["CURRENT_FOCUS.md"],
        recommended_execution_mode="single_worker",
        next_agent_packet={"schema_version": "builder_handoff.v1", "objective": "Advance command system."},
    )

    pack = build_context_pack(tmp_path, brief, max_chars_per_file=80)
    assert pack.startswith("# KittyBuilder Context Pack")
    assert "## Static Rules" in pack
    assert "## Selected Context" in pack
    assert "## Next-Agent Packet" in pack
    assert "## Final Acceptance Checklist" in pack
    assert "focused tests pass" in pack
    assert "[truncated]" in pack
