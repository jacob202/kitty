"""
Tests for unified project state reader (CURRENT_FOCUS.md source of truth).
Regression tests to ensure brief output is always non-empty and properly formatted.
"""

import sys, os, pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.project_state_reader import (
    read_current_focus,
    read_tasks_md,
    format_control_docs_brief,
    get_current_phase_details,
)


class TestReadCurrentFocus:
    """Tests for reading CURRENT_FOCUS.md"""
    
    def test_reads_active_phase(self, tmp_path):
        focus_file = tmp_path / "CURRENT_FOCUS.md"
        focus_file.write_text(
            "# Current Focus\n"
            "Last updated: 2026-05-08\n\n"
            "## Active Phase\n\n"
            "Phase 4 — Jacob-Only Build\n"
        )
        result = read_current_focus(tmp_path)
        assert result.get("active_phase") == "Phase 4 — Jacob-Only Build"
        assert result.get("date") == "2026-05-08"
    
    def test_reads_working_commands(self, tmp_path):
        focus_file = tmp_path / "CURRENT_FOCUS.md"
        focus_file.write_text(
            "# Current Focus\n\n"
            "## Working Commands\n"
            "- /optimize, /cleanup, /onboarding\n"
            "- ./kitty backup, ./kitty status\n"
        )
        result = read_current_focus(tmp_path)
        commands = result.get("working_commands", [])
        assert len(commands) >= 2
        assert any("optimize" in str(c) for c in commands)
    
    def test_reads_forbidden_work(self, tmp_path):
        focus_file = tmp_path / "CURRENT_FOCUS.md"
        focus_file.write_text(
            "# Current Focus\n\n"
            "## Forbidden work\n"
            "- MCP expansion\n"
            "- QLoRA\n"
        )
        result = read_current_focus(tmp_path)
        forbidden = result.get("forbidden_work", [])
        assert "MCP expansion" in forbidden
        assert "QLoRA" in forbidden
    
    def test_reads_today_progress(self, tmp_path):
        focus_file = tmp_path / "CURRENT_FOCUS.md"
        focus_file.write_text(
            "# Current Focus\n\n"
            "## Today's Progress\n"
            "- ✅ Fixed bug X\n"
            "- ✅ Added feature Y\n"
        )
        result = read_current_focus(tmp_path)
        progress = result.get("progress_items", [])
        assert len(progress) >= 2
        assert any("bug" in str(p).lower() for p in progress)


class TestReadTasksMd:
    """Tests for reading TASKS.md"""
    
    def test_reads_next_action(self, tmp_path):
        tasks_file = tmp_path / "TASKS.md"
        tasks_file.write_text(
            "# Tasks\n\n"
            "## Next Action\n"
            "- [ ] Deploy to production\n"
        )
        result = read_tasks_md(tmp_path)
        assert "Deploy to production" in result.get("next_action", "")
    
    def test_reads_open_tasks(self, tmp_path):
        tasks_file = tmp_path / "TASKS.md"
        tasks_file.write_text(
            "# Tasks\n\n"
            "- [ ] Fix bug A\n"
            "- [ ] Add feature B\n"
            "- [x] Done task\n"
        )
        result = read_tasks_md(tmp_path)
        assert len(result.get("open_tasks", [])) >= 2
        assert len(result.get("recent_completed", [])) >= 1


class TestFormatControlDocsBrief:
    """Regression tests for brief output"""
    
    def test_brief_is_non_empty(self, tmp_path):
        """REGRESSION: Brief must always produce non-empty output"""
        focus_file = tmp_path / "CURRENT_FOCUS.md"
        focus_file.write_text(
            "# Current Focus\n"
            "Last updated: 2026-05-08\n\n"
            "## Active Phase\n\nPhase 4 Test\n"
        )
        brief = format_control_docs_brief(tmp_path)
        assert brief
        assert len(brief.strip()) > 0
        assert "Phase 4 Test" in brief
    
    def test_brief_includes_all_sections_when_available(self, tmp_path):
        """REGRESSION: Brief must include phase, progress, commands, skills, tests"""
        focus_file = tmp_path / "CURRENT_FOCUS.md"
        focus_file.write_text(
            "# Current Focus\n"
            "Last updated: 2026-05-08\n\n"
            "## Active Phase\n\nPhase 4\n\n"
            "## Today's Progress\n"
            "- ✅ Fixed issue\n\n"
            "## Working Commands\n"
            "- /optimize, /cleanup\n\n"
            "## Skills\n"
            "- build, test\n\n"
            "## Tests: 500 passed ✓\n"
        )
        brief = format_control_docs_brief(tmp_path)
        assert "Phase 4" in brief
        assert "Today's Progress" in brief
        assert "Working Commands" in brief or "optimize" in brief
        assert "Skills" in brief or "build" in brief
        assert "500 passed" in brief
    
    def test_brief_includes_scope_guards(self, tmp_path):
        """REGRESSION: Brief must show forbidden work (scope guards)"""
        focus_file = tmp_path / "CURRENT_FOCUS.md"
        focus_file.write_text(
            "# Current Focus\n"
            "## Forbidden work\n"
            "- MCP expansion\n"
            "- QLoRA\n"
        )
        brief = format_control_docs_brief(tmp_path)
        assert "Scope Guard" in brief or "Forbidden" in brief
        assert "MCP expansion" in brief
    
    def test_brief_handles_missing_files(self, tmp_path):
        """Brief should still work even if files are missing"""
        brief = format_control_docs_brief(tmp_path)
        assert brief
        # Should have at least the header
        assert "PROJECT STATE" in brief


class TestCurrentPhaseDetails:
    """Tests for /phase command helper"""
    
    def test_phase_shows_active_and_date(self, tmp_path):
        focus_file = tmp_path / "CURRENT_FOCUS.md"
        focus_file.write_text(
            "# Current Focus\n"
            "Last updated: 2026-05-08\n\n"
            "## Active Phase\n\nPhase 4\n"
        )
        details = get_current_phase_details(tmp_path)
        assert "Phase 4" in details
        assert "2026-05-08" in details


class TestIntegrationWithKittyBuilder:
    """Integration test: ensure kittybuilder --brief works"""
    
    def test_generate_project_brief_imports_successfully(self):
        """smoke test: can we import the function?"""
        # This would be run in integration test environment
        try:
            from scripts.kitty_builder import generate_project_brief
            assert callable(generate_project_brief)
        except ImportError:
            pytest.skip("kitty_builder not importable in test environment")
