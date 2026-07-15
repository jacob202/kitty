from pathlib import Path

from scripts import docs_lint

FRONTMATTER = """---
type: architecture
title: Test document
status: canonical
owner: jacob
primary_purpose: Test documentation governance
derives_from:
  - AGENTS.md
implements:
  - gateway/example.py
review_cycle: quarterly
---

# Test document
"""


def test_collect_docs_limits_governance_to_canonical_surfaces(tmp_path: Path):
    docs = tmp_path / "docs"
    (docs / "architecture").mkdir(parents=True)
    (docs / "plans").mkdir()
    (docs / "README.md").write_text(FRONTMATTER)
    (docs / "architecture" / "MODEL.md").write_text(FRONTMATTER)
    (docs / "plans" / "working-note.md").write_text("# Working note\n")

    collected = {path.relative_to(docs).as_posix() for path in docs_lint.collect_docs(docs)}

    assert collected == {"README.md", "architecture/MODEL.md"}


def test_repository_references_are_resolved_from_repository_root(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "AGENTS.md").write_text("# Agents\n")
    (tmp_path / "gateway").mkdir()
    (tmp_path / "gateway" / "example.py").write_text("")

    assert docs_lint.reference_exists("AGENTS.md", tmp_path, docs)
    assert docs_lint.reference_exists("gateway/example.py", tmp_path, docs)
    assert not docs_lint.reference_exists("gateway/missing.py", tmp_path, docs)


def test_lint_ignores_legacy_notes_but_checks_governed_docs(tmp_path: Path):
    docs = tmp_path / "docs"
    (docs / "architecture").mkdir(parents=True)
    (docs / "plans").mkdir()
    (docs / "architecture" / "MODEL.md").write_text("# Missing frontmatter\n")
    (docs / "plans" / "legacy.md").write_text("# Historical note\n")

    errors = docs_lint.lint_docs(tmp_path, check_system_map=False)

    assert errors == [
        "architecture/MODEL.md: [missing-frontmatter] No valid YAML frontmatter found"
    ]


def test_lint_accepts_valid_repo_relative_traceability(tmp_path: Path):
    docs = tmp_path / "docs"
    (docs / "architecture").mkdir(parents=True)
    (tmp_path / "gateway").mkdir()
    (tmp_path / "AGENTS.md").write_text("# Agents\n")
    (tmp_path / "gateway" / "example.py").write_text("")
    (docs / "architecture" / "MODEL.md").write_text(FRONTMATTER)

    assert docs_lint.lint_docs(tmp_path, check_system_map=False) == []
