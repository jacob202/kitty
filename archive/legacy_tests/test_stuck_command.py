"""
Tests for /stuck command (src/core/stuck.py)
"""
import sys, os, pytest, tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.stuck import get_stuck_action


class TestGetStuckAction:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.project = tmp_path / "proj"
        self.project.mkdir()
        
        # Create CURRENT_FOCUS.md
        (self.project / "CURRENT_FOCUS.md").write_text(
            "# Current Focus\n"
            "Active phase: Phase 3 — Core Runtime Utility\n"
            "Current task: Build /stuck command\n"
            "Allowed work:\n- morning brief\n- /stuck command\n- task tracker\n"
            "Forbidden work:\n- MCP expansion\n- QLoRA\n- UI polish\n"
        )
        
        # Create TASKS.md
        (self.project / "TASKS.md").write_text(
            "# Tasks\n"
            "## Open\n"
            "- [ ] Build morning brief\n"
            "- [ ] Build /stuck command\n"
            "- [ ] Build task tracker\n"
            "## Done\n"
            "- [x] Phase 0 structural separation\n"
        )
        
        # Create SESSION_SUMMARY.md
        (self.project / "SESSION_SUMMARY.md").write_text(
            "# Session Summary\nLast completed: Phase 0 structural separation\n"
        )
        
        # Create KITTY_CONTEXT.md
        (self.project / "KITTY_CONTEXT.md").write_text("# Kitty Context\n")
        
        self.original_cwd = os.getcwd()
        os.chdir(str(self.project))
        yield
        os.chdir(self.original_cwd)

    def test_returns_expected_keys(self):
        result = get_stuck_action()
        assert "current_focus" in result
        assert "next_action" in result
        assert "do_not" in result
        assert "report_back" in result

    def test_next_action_under_200_chars(self):
        result = get_stuck_action()
        assert len(result["next_action"]) < 200

    def test_next_action_is_concrete(self):
        result = get_stuck_action()
        action = result["next_action"].lower()
        assert "research" not in action
        assert "redesign" not in action
        assert "new tool" not in action
        assert "change architecture" not in action

    def test_do_not_not_empty_when_focus_has_forbidden(self):
        result = get_stuck_action()
        assert isinstance(result["do_not"], list)
        assert len(result["do_not"]) > 0

    def test_report_back_format(self):
        result = get_stuck_action()
        report = result["report_back"]
        assert "done " in report.lower() or "still stuck" in report.lower()

    def test_fallback_when_files_missing(self, tmp_path):
        os.chdir(str(tmp_path))
        result = get_stuck_action(tmp_path)
        assert (
            "no active task" in result["current_focus"].lower()
            or "unknown" in result["current_focus"].lower()
            or "no current_focus.md" in result["current_focus"].lower()
        )

    def test_reads_markdown_heading_style_current_focus(self, tmp_path):
        project = tmp_path / "heading_proj"
        project.mkdir()
        (project / "CURRENT_FOCUS.md").write_text(
            "# Current Focus\n\n"
            "## Active Phase\n\nPhase 4 — Consolidation and Cleanup\n\n"
            "## Current Task\n\nBuild chat log consolidation pipeline.\n\n"
            "## Forbidden Work\n\n- memory migration\n- UI polish\n",
            encoding="utf-8",
        )
        (project / "TASKS.md").write_text(
            "# Tasks\n\n## Next Smallest Action\n\n1. Run route smoke tests.\n",
            encoding="utf-8",
        )

        result = get_stuck_action(project)

        assert result["current_focus"] == "Build chat log consolidation pipeline."
        assert result["next_action"] == "Run route smoke tests."
        assert result["do_not"] == ["memory migration", "UI polish"]
