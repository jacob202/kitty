from datetime import date

from scripts import check_continuity_state as linter


def _write_required(root, *, updated="2026-05-09"):
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "CURRENT_FOCUS.md").write_text(f"# Current Focus\nLast updated: {updated}\n", encoding="utf-8")
    (root / "TASKS.md").write_text(f"# Tasks\nLast updated: {updated}\n", encoding="utf-8")
    (root / "SESSION_SUMMARY.md").write_text(f"# Session Summary\nLast updated: {updated}\n", encoding="utf-8")
    (root / "docs" / "LAYER0_CONTROL_PLANE.md").write_text(
        f"# Layer 0\nLast updated: {updated}\nCanonical: /Users/jacobbrizinski/Projects/kitty\n",
        encoding="utf-8",
    )
    (root / "docs" / "README.md").write_text(
        f"# Docs\nLast updated: {updated}\nRunnable git checkout: /Users/jacobbrizinski/Projects/kitty\n",
        encoding="utf-8",
    )


def test_build_report_clean(tmp_path):
    _write_required(tmp_path)
    report = linter.build_report(tmp_path, today=date(2026, 5, 9), max_age_days=14)
    assert report.errors == []
    assert report.warnings == []


def test_build_report_flags_escaped_newline_corruption(tmp_path):
    _write_required(tmp_path)
    (tmp_path / "TASKS.md").write_text("# Tasks\nLast updated: 2026-05-09\n---\\n\\n## Corrupt\n", encoding="utf-8")
    report = linter.build_report(tmp_path, today=date(2026, 5, 9))
    assert any("escaped newline duplicate-block marker" in err for err in report.errors)


def test_build_report_flags_future_date(tmp_path):
    _write_required(tmp_path, updated="2026-05-12")
    report = linter.build_report(tmp_path, today=date(2026, 5, 9))
    assert any("in the future" in err for err in report.errors)


def test_build_report_warns_on_stale_doc(tmp_path):
    _write_required(tmp_path, updated="2026-04-01")
    report = linter.build_report(tmp_path, today=date(2026, 5, 9), max_age_days=14)
    assert report.errors == []
    assert any("stale" in warn for warn in report.warnings)


def test_build_report_flags_stale_path_when_marked_active(tmp_path):
    _write_required(tmp_path)
    (tmp_path / "docs" / "README.md").write_text(
        "# Docs\nLast updated: 2026-05-09\nActive runtime: /Users/jacobbrizinski/Projects/kitty-system/kitty-app\n",
        encoding="utf-8",
    )
    report = linter.build_report(tmp_path, today=date(2026, 5, 9))
    assert any("stale runtime path appears in active/canonical context" in err for err in report.errors)
