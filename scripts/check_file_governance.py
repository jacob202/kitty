#!/usr/bin/env python3
"""Validate Kitty file-governance control rules without mutating the tree."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


PROTECTED_PATHS = (
    "web.py",
    "src",
    "tests",
    "scripts",
    "data",
    "garage-ui",
    "src/static",
    "src/templates",
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
    "specs/_template.md",
)

REQUIRED_CONTROL_FILES = (
    "CURRENT_FOCUS.md",
    "docs/DECISIONS.md",
    "docs/PARKED_FEATURES.md",
    "docs/FILE_GOVERNANCE.md",
    "docs/FILE_MANIFEST.md",
    "docs/BUILDER_INTAKE.md",
    "docs/BUILDER_DIRECTIVE.md",
    "specs/_template.md",
    "kittyintake",
    "kittybuilder",
    "scripts/builder_intake.py",
    "scripts/context_pack_generator.py",
    "scripts/kitty_builder.py",
)

TOP_LEVEL_CATEGORIES = {
    ".cache": "scratch",
    ".claude": "tool",
    ".crush": "tool",
    ".firecrawl": "tool",
    ".git": "tool",
    ".pytest_cache": "scratch",
    ".worktrees": "scratch",
    "benchmarks": "benchmark",
    "config": "specialist_config",
    "consolidated-skills": "skill",
    "data": "data",
    "docs": "canonical_doc",
    "evals": "test",
    "garage-ui": "runtime_source",
    "intake": "spec",
    "logs": "archive",
    "scripts": "script",
    "skills": "skill",
    "specs": "spec",
    "src": "runtime_source",
    "static": "runtime_source",
    "templates": "runtime_source",
    "tests": "test",
}

METADATA_NAMES = {".DS_Store", "Icon\r"}
METADATA_PRUNE_DIRS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".worktrees",
    "__pycache__",
    "node_modules",
    "venv",
}


@dataclass(frozen=True)
class GovernanceReport:
    missing_required: list[str]
    missing_protected: list[str]
    unknown_top_level: list[str]
    metadata_candidates: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing_required and not self.missing_protected


def build_report(project: str | Path) -> GovernanceReport:
    root = Path(project).expanduser().resolve()
    missing_required = [path for path in REQUIRED_CONTROL_FILES if not (root / path).exists()]
    missing_protected = [path for path in PROTECTED_PATHS if not (root / path).exists()]
    unknown_top_level = unknown_top_level_paths(root)
    metadata_candidates = metadata_paths(root)
    return GovernanceReport(
        missing_required=missing_required,
        missing_protected=missing_protected,
        unknown_top_level=unknown_top_level,
        metadata_candidates=metadata_candidates,
    )


def unknown_top_level_paths(root: Path) -> list[str]:
    if not root.exists():
        return ["."]
    unknown: list[str] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if child.name.startswith(".") and child.name not in TOP_LEVEL_CATEGORIES:
            continue
        if child.name in METADATA_NAMES:
            continue
        if child.name not in TOP_LEVEL_CATEGORIES and child.is_dir():
            unknown.append(child.name)
    return unknown


def metadata_paths(root: Path) -> list[str]:
    if not root.exists():
        return []
    candidates: list[str] = []
    for path in walk_metadata_scope(root):
        if path.name in METADATA_NAMES:
            candidates.append(path.relative_to(root).as_posix())
    return sorted(candidates)


def walk_metadata_scope(root: Path) -> list[Path]:
    paths: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            children = list(current.iterdir())
        except OSError:
            continue
        for child in children:
            paths.append(child)
            if child.is_dir() and child.name not in METADATA_PRUNE_DIRS:
                stack.append(child)
    return paths


def print_report(report: GovernanceReport, *, dry_run: bool) -> None:
    mode = "dry-run" if dry_run else "check"
    print(f"File governance {mode}")
    print("Required control files:", "ok" if not report.missing_required else "missing")
    for path in report.missing_required:
        print(f"  missing required: {path}")
    print("Protected paths:", "ok" if not report.missing_protected else "missing")
    for path in report.missing_protected:
        print(f"  missing protected: {path}")
    print("Unknown top-level directories:")
    if report.unknown_top_level:
        for path in report.unknown_top_level:
            print(f"  unknown: {path}")
    else:
        print("  none")
    print("Generated metadata candidates:")
    if report.metadata_candidates:
        for path in report.metadata_candidates:
            print(f"  candidate: {path}")
    else:
        print("  none")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        default=".",
        help="Kitty project root to check. Defaults to the current directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the report without requiring a perfectly clean tree.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List protected paths and exit.",
    )
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list:
        for path in PROTECTED_PATHS:
            print(path)
        return 0
    report = build_report(args.project)
    print_report(report, dry_run=args.dry_run)
    if args.dry_run:
        return 0
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(run())
