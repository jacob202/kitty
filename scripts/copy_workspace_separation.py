#!/usr/bin/env python3
"""Copy the current Kitty checkout into the planned kitty-system layout."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


EXCLUDES = (
    ".git/",
    ".aider*",
    ".cache/",
    ".claude/",
    ".crush/",
    ".env",
    ".env.*",
    ".envrc",
    ".firecrawl/",
    ".kitty.log",
    ".kitty.pid",
    ".kittybuilder_session.json",
    ".crush/crush.db",
    ".pytest_cache/",
    ".worktrees/",
    "__pycache__/",
    "*.pyc",
    ".DS_Store",
    "venv/",
    "garage-ui/node_modules/",
    "garage-ui/.next/",
    "eval_snapshots/",
    "evals/artifacts/",
    "knowledge_db/",
    "librarian_db/",
    "logs/",
    "outputs/",
    "refactor_reports/",
    ".adal/",
    ".agents/",
    ".codebuddy/",
    ".commandcode/",
    ".factory/",
    ".goose/",
    ".iflow/",
    ".kilocode/",
    ".kiro/",
    ".kode/",
    ".pi/",
    ".qwen/",
    ".vibe/",
    ".zencoder/",
    ".claude/skills/",
    "skills/",
    "skills-lock.json",
)

WORKBENCH_PATHS = (
    "kittyintake",
    "kittybuilder",
    "CURRENT_FOCUS.md",
    "TASKS.md",
    "SESSION_SUMMARY.md",
    "KITTY_CONTEXT.md",
    "docs/DECISIONS.md",
    "docs/PARKED_FEATURES.md",
    "docs/FILE_GOVERNANCE.md",
    "docs/FILE_MANIFEST.md",
    "docs/WORKSPACE_SEPARATION_MOVE_MAP.md",
    "docs/MCP_AGENT_BUNDLE_REVIEW_2026-04-29.md",
    "docs/BUILDER_INTAKE.md",
    "docs/BUILDER_DIRECTIVE.md",
    "docs/GATES.md",
    "docs/OPEN_LOOPS.md",
    "docs/PROJECT_FACTS.md",
    "docs/USER_PREFS.md",
    "specs/",
    "intake/",
    "scripts/builder_intake.py",
    "scripts/context_pack_generator.py",
    "scripts/kitty_builder.py",
    "scripts/check_file_governance.py",
    "scripts/plan_workspace_separation.py",
    "scripts/copy_workspace_separation.py",
)

ARCHIVE_PATHS = (
    "docs/archive/",
    "docs/imports/",
    "benchmarks/",
)


@dataclass(frozen=True)
class CopyPlan:
    source: Path
    target_root: Path
    kitty_app: Path
    kitty_workbench: Path
    kitty_archives: Path


def build_plan(project: str | Path, target_root: str | Path | None = None) -> CopyPlan:
    source = Path(project).expanduser().resolve()
    target = Path(target_root).expanduser().resolve() if target_root else source.parent / "kitty-system"
    if source == target or target == source.parent:
        raise ValueError("target root must be outside the source checkout")
    return CopyPlan(
        source=source,
        target_root=target,
        kitty_app=target / "kitty-app",
        kitty_workbench=target / "kitty-workbench",
        kitty_archives=target / "kitty-archives",
    )


def rsync_command(src: str | Path, dest: str | Path, *, excludes: tuple[str, ...] = ()) -> list[str]:
    command = ["rsync", "-a"]
    for pattern in excludes:
        command.extend(["--exclude", pattern])
    command.extend([str(src), str(dest)])
    return command


def existing_paths(root: Path, paths: tuple[str, ...]) -> list[Path]:
    return [root / path for path in paths if (root / path).exists()]


def print_plan(plan: CopyPlan) -> None:
    print("Copy-first workspace separation")
    print(f"Source: {plan.source}")
    print(f"Target root: {plan.target_root}")
    print(f"kitty-app: {plan.kitty_app}")
    print(f"kitty-workbench: {plan.kitty_workbench}")
    print(f"kitty-archives: {plan.kitty_archives}")
    print()
    print("App copy: source checkout -> kitty-app with generated/tool-local excludes")
    print("Workbench paths:")
    for path in WORKBENCH_PATHS:
        print(f"  - {path}")
    print("Archive paths:")
    for path in ARCHIVE_PATHS:
        print(f"  - {path}")


def copy_path(source_path: Path, source_root: Path, dest_root: Path) -> None:
    rel = source_path.relative_to(source_root)
    dest = dest_root / rel
    if source_path.is_dir():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(rsync_command(source_path, dest.parent), check=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest)


def execute(plan: CopyPlan) -> None:
    plan.target_root.mkdir(parents=True, exist_ok=True)
    plan.kitty_app.mkdir(parents=True, exist_ok=True)
    plan.kitty_workbench.mkdir(parents=True, exist_ok=True)
    plan.kitty_archives.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        rsync_command(f"{plan.source}/", plan.kitty_app, excludes=EXCLUDES),
        check=True,
    )

    for path in existing_paths(plan.source, WORKBENCH_PATHS):
        copy_path(path, plan.source, plan.kitty_workbench)

    for dirname in ("chat_exports/raw", "chat_exports/processed", "backups", "tree-snapshots", "model-benchmark"):
        (plan.kitty_archives / dirname).mkdir(parents=True, exist_ok=True)
    for path in existing_paths(plan.source, ARCHIVE_PATHS):
        copy_path(path, plan.source, plan.kitty_archives)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Current Kitty project root.")
    parser.add_argument("--target-root", default=None, help="Destination kitty-system root.")
    parser.add_argument("--dry-run", action="store_true", help="Print the copy plan and write nothing.")
    parser.add_argument("--execute", action="store_true", help="Create/update the target workspace.")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.execute and args.dry_run:
        print("Choose only one: --dry-run or --execute", file=sys.stderr)
        return 2
    plan = build_plan(args.project, args.target_root)
    print_plan(plan)
    if args.execute:
        execute(plan)
        print()
        print("Copy complete.")
    else:
        print()
        print("Dry-run only. Pass --execute to copy.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
