from pathlib import Path

from scripts.plan_workspace_separation import (
    build_plan,
    is_mcp_blocker,
    parse_git_status,
    run,
)


def test_parse_git_status_handles_untracked_and_modified_paths():
    entries = parse_git_status(" M TASKS.md\n?? src/agents/knowledge_getter.py\n")

    assert entries[0].status == "M"
    assert entries[0].path == "TASKS.md"
    assert entries[1].status == "??"
    assert entries[1].path == "src/agents/knowledge_getter.py"


def test_mcp_blocker_matches_knowledge_getter_paths():
    assert is_mcp_blocker("src/agents/knowledge_getter.py")
    assert is_mcp_blocker("knowledge_db/metadata.db")
    assert not is_mcp_blocker("src/core/orchestrator.py")


def test_build_plan_contains_required_move_buckets(tmp_path: Path):
    (tmp_path / "CURRENT_FOCUS.md").write_text("## Forbidden Work\n- MCP expansion\n", encoding="utf-8")

    plan = build_plan(tmp_path)

    assert "web.py" in plan.app_candidates
    assert "scripts/kitty_builder.py" in plan.workbench_candidates
    assert "docs/archive/" in plan.archive_candidates
    assert "knowledge_db/" in plan.excluded_generated


def test_cli_prints_preflight(tmp_path: Path, capsys):
    assert run(["--project", str(tmp_path), "--allow-dirty-readonly"]) == 0

    output = capsys.readouterr().out
    assert "Physical workspace separation preflight" in output
    assert "kitty-app candidates:" in output
