from pathlib import Path

from scripts.copy_workspace_separation import EXCLUDES, build_plan, rsync_command, run


def test_build_plan_defaults_to_sibling_kitty_system(tmp_path: Path):
    source = tmp_path / "kitty"
    source.mkdir()

    plan = build_plan(source)

    assert plan.target_root == tmp_path / "kitty-system"
    assert plan.kitty_app == tmp_path / "kitty-system" / "kitty-app"
    assert plan.kitty_workbench == tmp_path / "kitty-system" / "kitty-workbench"
    assert plan.kitty_archives == tmp_path / "kitty-system" / "kitty-archives"


def test_rsync_command_includes_excludes(tmp_path: Path):
    command = rsync_command(tmp_path / "src", tmp_path / "dest", excludes=("venv/", "node_modules/"))

    assert command[:2] == ["rsync", "-a"]
    assert "--exclude" in command
    assert "venv/" in command
    assert "node_modules/" in command


def test_rsync_command_preserves_trailing_slash_for_copying_contents(tmp_path: Path):
    command = rsync_command(f"{tmp_path}/", tmp_path / "dest")

    assert command[-2].endswith("/")


def test_default_excludes_generated_and_tool_local_paths():
    assert "venv/" in EXCLUDES
    assert "garage-ui/node_modules/" in EXCLUDES
    assert "knowledge_db/" in EXCLUDES
    assert "librarian_db/" in EXCLUDES
    assert "outputs/" in EXCLUDES
    assert "refactor_reports/" in EXCLUDES
    assert ".cache/" in EXCLUDES
    assert ".agents/" in EXCLUDES


def test_dry_run_writes_nothing(tmp_path: Path, capsys):
    source = tmp_path / "kitty"
    source.mkdir()

    assert run(["--project", str(source), "--dry-run"]) == 0

    output = capsys.readouterr().out
    assert "Copy-first workspace separation" in output
    assert "Dry-run only" in output
    assert not (tmp_path / "kitty-system").exists()
