from pathlib import Path

from scripts.context_pack_generator import build_context_pack, run, write_context_pack


def write_project(root: Path) -> None:
    (root / "docs").mkdir()
    (root / "CURRENT_FOCUS.md").write_text(
        """# Current Focus

## Allowed Phase 1 work is limited to:

- builder intake
- context-pack generation

## Forbidden Work

- memory migration
- UI polish
""",
        encoding="utf-8",
    )
    (root / "docs" / "DECISIONS.md").write_text("Decision: use intake first\n", encoding="utf-8")
    (root / "docs" / "PARKED_FEATURES.md").write_text("Parked: QLoRA\n", encoding="utf-8")
    (root / "docs" / "TASKS.md").write_text("Next concrete action\n", encoding="utf-8")
    (root / "docs" / "KITTY_CONTEXT.md").write_text("Be direct and practical.\n", encoding="utf-8")


def test_context_pack_contains_required_runtime_sections(tmp_path: Path):
    write_project(tmp_path)

    pack = build_context_pack(tmp_path)

    assert "# Kitty Runtime Context Pack" in pack
    assert "## Current Focus" in pack
    assert "## Next Action" in pack
    assert "## Forbidden Work" in pack
    assert "- memory migration" in pack
    assert "## Recent Decisions" in pack
    assert "## Parked Items Not To Build" in pack
    assert "## User Interaction Rules" in pack


def test_context_pack_uses_docs_fallbacks(tmp_path: Path):
    write_project(tmp_path)

    pack = build_context_pack(tmp_path)

    assert "Source: docs/TASKS.md" in pack
    assert "Source: docs/KITTY_CONTEXT.md" in pack


def test_write_context_pack_defaults_to_cache(tmp_path: Path):
    write_project(tmp_path)

    output = write_context_pack(tmp_path, None)

    assert output == tmp_path / ".cache" / "kitty_context_pack.md"
    assert output.exists()
    assert "Forbidden Work" in output.read_text(encoding="utf-8")


def test_cli_prints_without_writing_default_cache(tmp_path: Path, capsys):
    write_project(tmp_path)

    assert run(["--project", str(tmp_path), "--print"]) == 0

    output = capsys.readouterr().out
    assert "Kitty Runtime Context Pack" in output
    assert not (tmp_path / ".cache" / "kitty_context_pack.md").exists()


def test_cli_writes_explicit_output(tmp_path: Path):
    write_project(tmp_path)

    assert run(["--project", str(tmp_path), "--out", "tmp/context.md"]) == 0

    assert (tmp_path / "tmp" / "context.md").exists()
