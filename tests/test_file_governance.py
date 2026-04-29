from pathlib import Path

from scripts.check_file_governance import build_report, run


def write_minimal_project(root: Path) -> None:
    for directory in [
        "docs",
        "specs",
        "src",
        "tests",
        "scripts",
        "data",
        "garage-ui",
        "src/static",
        "src/templates",
    ]:
        (root / directory).mkdir(parents=True, exist_ok=True)
    for file_path in [
        "web.py",
        "CURRENT_FOCUS.md",
        "TASKS.md",
        "SESSION_SUMMARY.md",
        "KITTY_CONTEXT.md",
        "docs/DECISIONS.md",
        "docs/PARKED_FEATURES.md",
        "docs/FILE_GOVERNANCE.md",
        "docs/FILE_MANIFEST.md",
        "docs/CLEANUP_CANDIDATES.md",
        "docs/MEMORY_MODEL.md",
        "docs/PROJECT_FACTS.md",
        "docs/USER_PREFS.md",
        "docs/OPEN_LOOPS.md",
        "docs/SKILL_CANDIDATES.md",
        "docs/SOUL_LEARNED_RULES.md",
        "docs/CHAT_LOG_CONSOLIDATION_REPORT.md",
        "docs/GEMINI_CHAT_LOG_INTAKE.md",
        "docs/DELEGATION_BOARD.md",
        "docs/BUILDER_INTAKE.md",
        "docs/BUILDER_DIRECTIVE.md",
        "docs/WORKSPACE_SEPARATION_MOVE_MAP.md",
        "specs/_template.md",
        "specs/physical-workspace-separation.spec.md",
        "kittyintake",
        "kittybuilder",
        "scripts/builder_intake.py",
        "scripts/context_pack_generator.py",
        "scripts/kitty_builder.py",
        "scripts/plan_workspace_separation.py",
    ]:
        (root / file_path).write_text("placeholder\n", encoding="utf-8")


def test_governance_report_confirms_required_and_protected_files(tmp_path: Path):
    write_minimal_project(tmp_path)

    report = build_report(tmp_path)

    assert report.ok
    assert report.missing_required == []
    assert report.missing_protected == []


def test_governance_report_lists_missing_required_file(tmp_path: Path):
    write_minimal_project(tmp_path)
    (tmp_path / "docs" / "DECISIONS.md").unlink()

    report = build_report(tmp_path)

    assert not report.ok
    assert "docs/DECISIONS.md" in report.missing_required
    assert "docs/DECISIONS.md" in report.missing_protected


def test_dry_run_exits_zero_when_required_files_are_missing(tmp_path: Path, capsys):
    assert run(["--project", str(tmp_path), "--dry-run"]) == 0

    output = capsys.readouterr().out
    assert "File governance dry-run" in output
    assert "missing required:" in output


def test_strict_check_exits_nonzero_when_required_files_are_missing(tmp_path: Path):
    assert run(["--project", str(tmp_path)]) == 1


def test_metadata_candidates_include_macos_artifacts(tmp_path: Path):
    write_minimal_project(tmp_path)
    (tmp_path / ".DS_Store").write_text("", encoding="utf-8")
    (tmp_path / "src" / "Icon\r").write_text("", encoding="utf-8")

    report = build_report(tmp_path)

    assert ".DS_Store" in report.metadata_candidates
    assert "src/Icon\r" in report.metadata_candidates


def test_list_prints_protected_paths(capsys):
    assert run(["--list"]) == 0

    output = capsys.readouterr().out
    assert "CURRENT_FOCUS.md" in output
    assert "data" in output
