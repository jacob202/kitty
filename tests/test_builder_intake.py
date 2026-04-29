import subprocess
import sys
from pathlib import Path

from scripts.builder_intake import classify, classify_request, run_intake


ROOT = Path(__file__).resolve().parents[1]


def write_project(tmp_path: Path, focus: str | None = None) -> Path:
    project = tmp_path / "kitty-app"
    project.mkdir()
    (project / "docs").mkdir()
    if focus is not None:
        (project / "CURRENT_FOCUS.md").write_text(focus, encoding="utf-8")
    (project / "docs" / "FILE_GOVERNANCE.md").write_text(
        "\n".join(
            [
                "# File Governance",
                "Protected files:",
                "- `src/space_kitty/SOUL.md`",
                "- `data/kitty.db`",
                "- `src/core/orchestrator.py`",
            ]
        ),
        encoding="utf-8",
    )
    return project


def test_project_is_required():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "builder_intake.py"), "--text", "Add /stuck"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "--project" in result.stderr


def test_simple_build_request_classified_ready(tmp_path: Path):
    project = write_project(tmp_path)

    result = classify_request(project, "Add a /stuck command but do not modify UI")

    assert result.classification == "ready"
    assert "stuck" in result.recommended_action.lower()


def test_legacy_classify_returns_dict_for_callers(tmp_path: Path):
    project = write_project(tmp_path)

    result = classify(project, "Add a /stuck command but do not modify UI")

    assert result["classification"] == "ready"
    assert result["destination"] == "ready_specs"


def test_vague_cleanup_classified_needs_verification(tmp_path: Path):
    project = write_project(tmp_path)

    result = classify_request(project, "Clean up the repo and make it better")

    assert result.classification == "needs_verification"
    assert "specific" in result.missing_context.lower()


def test_future_feature_classified_park(tmp_path: Path):
    project = write_project(tmp_path)

    result = classify_request(project, "Build QLoRA specialist fine tuning")

    assert result.classification == "park"
    assert "parked" in result.recommended_action.lower()


def test_multi_feature_request_classified_split(tmp_path: Path):
    project = write_project(tmp_path)

    result = classify_request(project, "Add /stuck and migrate memory and polish the UI")

    assert result.classification == "split"
    assert "one spec" in result.recommended_action.lower()


def test_protected_file_edit_classified_reject(tmp_path: Path):
    project = write_project(tmp_path)

    result = classify_request(project, "Edit src/space_kitty/SOUL.md automatically")

    assert result.classification == "reject"
    assert "protected" in result.recommended_action.lower()


def test_protected_directory_edit_classified_reject(tmp_path: Path):
    project = write_project(tmp_path)
    (project / "docs" / "FILE_GOVERNANCE.md").write_text(
        "\n".join(
            [
                "# File Governance",
                "Protected runtime files:",
                "- `src/`",
                "- `data/`",
                "- `garage-ui/`",
            ]
        ),
        encoding="utf-8",
    )

    result = classify_request(project, "Refactor src/ and data/ now")

    assert result.classification == "reject"
    assert "src/" in result.forbidden_files
    assert "data/" in result.forbidden_files


def test_current_focus_is_read_and_enforced(tmp_path: Path):
    project = write_project(
        tmp_path,
        "Allowed work:\n- builder intake design\nForbidden work:\n- memory migration\n",
    )

    result = classify_request(project, "Start memory migration now")

    assert result.classification == "park"
    assert "current focus" in result.recommended_action.lower()


def test_current_focus_stop_conditions_are_enforced(tmp_path: Path):
    project = write_project(
        tmp_path,
        "## Stop Conditions\n\nStop before touching:\n\n- `src/`\n- `web.py`\n- UI files\n",
    )

    result = classify_request(project, "Touch src/ to add a new route")

    assert result.classification == "reject"
    assert "protected" in result.recommended_action.lower()


def test_dry_run_writes_nothing_and_prints_output(tmp_path: Path, capsys):
    project = write_project(tmp_path)

    result = run_intake(project, "Add a /stuck command but do not modify UI", write=False)
    output = capsys.readouterr().out

    assert result.classification == "ready"
    assert "Classification: ready" in output
    assert "Proposed output path:" in output
    assert not (project / "intake").exists()


def test_write_creates_markdown_intake_result(tmp_path: Path):
    project = write_project(tmp_path)

    result = run_intake(project, "Add a /stuck command but do not modify UI", write=True)

    assert result.output_path is not None
    assert result.output_path.exists()
    assert result.output_path.parent == project / "intake" / "ready_specs"
    assert result.output_path.suffix == ".md"
    written = result.output_path.read_text(encoding="utf-8")
    assert written.startswith("# Builder Intake Result")
    assert "## Allowed files" in written
    assert "## Acceptance tests" in written
    assert "## Smoke test" in written
    assert "## Validation commands" in written
    assert "## Rollback plan" in written
    assert "## Completion report required" in written


def test_cli_accepts_explicit_dry_run(tmp_path: Path):
    project = write_project(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "builder_intake.py"),
            "--project",
            str(project),
            "--text",
            "Add a /stuck command but do not modify UI",
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Classification: ready" in result.stdout
    assert not (project / "intake").exists()


def test_cli_rejects_write_and_dry_run_together(tmp_path: Path):
    project = write_project(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "builder_intake.py"),
            "--project",
            str(project),
            "--text",
            "Add a /stuck command but do not modify UI",
            "--write",
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "cannot be combined" in result.stderr
    assert not (project / "intake").exists()
