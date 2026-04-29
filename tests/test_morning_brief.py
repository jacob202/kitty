"""
Tests for morning brief generator.
"""
import sys, os, pytest, tempfile, shutil
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.morning_brief import generate_brief, brief_to_text


def _create_project(tmp_path):
    p = tmp_path / "proj"
    p.mkdir()
    (p / "CURRENT_FOCUS.md").write_text(
        "# Current Focus\nActive phase: Phase 3\nCurrent task: Build brief\nForbidden work:\n- MCP\n- QLoRA\n"
    )
    (p / "TASKS.md").write_text(
        "# Tasks\n## Open\n- [ ] Build morning brief\n- [ ] Build /stuck\n## Done\n- [x] Phase 0\n"
    )
    (p / "SESSION_SUMMARY.md").write_text("# Summary\nLast completed: Phase 0 setup\n")
    (p / "KITTY_CONTEXT.md").write_text("# Context\n")
    return p


class TestGenerateBrief:
    def test_returns_expected_keys(self):
        b = generate_brief()
        for k in ("date", "active_focus", "last_completed", "next_action", "forbidden_distractions"):
            assert k in b, f"Missing key: {k}"

    def test_date_is_today(self):
        b = generate_brief()
        assert b["date"] == datetime.now().strftime("%Y-%m-%d")

    def test_brief_to_text_contains_focus(self):
        b = generate_brief()
        text = brief_to_text(b)
        assert "Active focus:" in text

    def test_fallback_when_files_missing(self, tmp_path):
        os.chdir(str(tmp_path))
        b = generate_brief(str(tmp_path))
        assert b["active_focus"] in ("unknown", "")
        assert b["last_completed"] in ("nothing yet", "")

    def test_forbidden_list(self):
        b = generate_brief()
        assert isinstance(b["forbidden_distractions"], list)

    def test_brief_structure_all_sections(self):
        b = generate_brief()
        text = brief_to_text(b)
        assert "Today:" in text
        assert "Active focus:" in text
        assert "Last completed:" in text
        assert "Next concrete action:" in text


class TestBriefWithFiles:
    def test_active_focus_from_file(self, tmp_path):
        p = _create_project(tmp_path)
        b = generate_brief(str(p))
        assert "Phase 3" in b["active_focus"] or "Build brief" in b["active_focus"]

    def test_next_action_from_tasks(self, tmp_path):
        p = _create_project(tmp_path)
        b = generate_brief(str(p))
        assert "morning brief" in b["next_action"].lower() or "Build" in b["next_action"]

    def test_last_completed_from_session(self, tmp_path):
        p = _create_project(tmp_path)
        b = generate_brief(str(p))
        assert "Phase 0" in b["last_completed"] or "setup" in b["last_completed"].lower()

    def test_reads_markdown_heading_style_current_focus(self, tmp_path):
        p = tmp_path / "proj"
        p.mkdir()
        (p / "CURRENT_FOCUS.md").write_text(
            "# Current Focus\n\n"
            "## Active Phase\n\nPhase 4 — Consolidation and Cleanup\n\n"
            "## Current Task\n\nBuild chat log consolidation pipeline.\n\n"
            "## Forbidden Work\n\n- MCP expansion\n- UI polish\n",
            encoding="utf-8",
        )
        (p / "TASKS.md").write_text(
            "# Tasks\n\n## Next Smallest Action\n\n1. Run route smoke tests.\n",
            encoding="utf-8",
        )
        (p / "SESSION_SUMMARY.md").write_text("# Summary\n", encoding="utf-8")

        b = generate_brief(str(p))

        assert b["active_focus"] == "Build chat log consolidation pipeline."
        assert b["next_action"] == "Run route smoke tests."
        assert b["forbidden_distractions"] == ["MCP expansion", "UI polish"]
