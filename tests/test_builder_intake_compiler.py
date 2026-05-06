from scripts.builder_intake import compile_builder_brief


def test_compile_builder_brief_returns_dict(tmp_path):
    (tmp_path / "CURRENT_FOCUS.md").write_text("# Current Focus\n", encoding="utf-8")
    data = compile_builder_brief(tmp_path, "continue command system and verify")
    assert data["raw_input"] == "continue command system and verify"
    assert "normalized_goal" in data
    assert "recommended_execution_mode" in data
    assert "next_agent_packet" in data
    assert data["next_agent_packet"]["schema_version"] == "builder_handoff.v1"
