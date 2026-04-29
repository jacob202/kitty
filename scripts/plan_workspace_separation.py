#!/usr/bin/env python3
"""Print a read-only preflight for the future Kitty workspace separation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


APP_CANDIDATES = (
    "web.py",
    "kitty",
    "supervisor.py",
    "src/",
    "config/",
    "tests/",
    "evals/",
    "garage-ui/",
    "requirements.txt",
)

WORKBENCH_CANDIDATES = (
    "CURRENT_FOCUS.md",
    "TASKS.md",
    "SESSION_SUMMARY.md",
    "KITTY_CONTEXT.md",
    "docs/DECISIONS.md",
    "docs/FILE_GOVERNANCE.md",
    "docs/FILE_MANIFEST.md",
    "docs/DELEGATION_BOARD.md",
    "docs/BUILDER_INTAKE.md",
    "docs/BUILDER_DIRECTIVE.md",
    "docs/GATES.md",
    "docs/WORKSPACE_SEPARATION_MOVE_MAP.md",
    "specs/",
    "intake/",
    "kittyintake",
    "kittybuilder",
    "scripts/builder_intake.py",
    "scripts/context_pack_generator.py",
    "scripts/kitty_builder.py",
    "scripts/check_file_governance.py",
    "scripts/plan_workspace_separation.py",
)

ARCHIVE_CANDIDATES = (
    "docs/archive/",
    "docs/imports/",
    "kitty-archives/chat_exports/",
    "benchmarks/",
)

EXCLUDED_GENERATED = (
    ".env",
    ".env.*",
    ".kitty.log",
    ".kitty.pid",
    ".crush/crush.db",
    ".pytest_cache/",
    ".worktrees/",
    "**/__pycache__/",
    "**/*.pyc",
    "**/.DS_Store",
    "garage-ui/.next/",
    "garage-ui/node_modules/",
    "venv/",
    "data/",
    "knowledge_db/",
    "eval_snapshots/",
    "evals/artifacts/*.json",
    "logs/",
)

MCP_BLOCKER_PATHS = (
    "specs/knowledge-getter.spec.md",
    "src/agents/knowledge_getter.py",
    "src/agents/knowledge_getter_config.json",
    "knowledge_db/",
)


@dataclass(frozen=True)
class DirtyEntry:
    status: str
    path: str


@dataclass(frozen=True)
class SeparationPlan:
    project: str
    target_root: str
    status: str
    blockers: list[str]
    dirty_entries: list[DirtyEntry]
    app_candidates: tuple[str, ...]
    workbench_candidates: tuple[str, ...]
    archive_candidates: tuple[str, ...]
    excluded_generated: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        return self.status == "BLOCKED"


def parse_git_status(output: str) -> list[DirtyEntry]:
    entries: list[DirtyEntry] = []
    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        status = raw_line[:2].strip() or raw_line[:2]
        path = raw_line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append(DirtyEntry(status=status, path=path))
    return entries


def git_status(project: Path) -> list[DirtyEntry]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=project,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return parse_git_status(result.stdout)


def focus_forbids_mcp(project: Path) -> bool:
    focus = project / "CURRENT_FOCUS.md"
    if not focus.exists():
        return False
    text = focus.read_text(encoding="utf-8", errors="replace").lower()
    return "mcp expansion" in text and "forbidden work" in text


def is_mcp_blocker(path: str) -> bool:
    return any(path == blocked.rstrip("/") or path.startswith(blocked) for blocked in MCP_BLOCKER_PATHS)


def build_plan(project: str | Path, target_root: str | Path | None = None) -> SeparationPlan:
    root = Path(project).expanduser().resolve()
    target = Path(target_root).expanduser().resolve() if target_root else root.parent / "kitty-system"
    dirty_entries = git_status(root)
    blockers: list[str] = []

    if dirty_entries:
        blockers.append("working tree has uncommitted changes")

    mcp_dirty = [entry.path for entry in dirty_entries if is_mcp_blocker(entry.path)]
    if mcp_dirty and focus_forbids_mcp(root):
        blockers.append("MCP / KnowledgeGetter work is dirty while CURRENT_FOCUS.md forbids MCP expansion")

    if any(entry.path.startswith("knowledge_db/") for entry in dirty_entries):
        blockers.append("knowledge_db/ is generated runtime data and must not be migrated as source")

    return SeparationPlan(
        project=str(root),
        target_root=str(target),
        status="BLOCKED" if blockers else "READY",
        blockers=blockers,
        dirty_entries=dirty_entries,
        app_candidates=APP_CANDIDATES,
        workbench_candidates=WORKBENCH_CANDIDATES,
        archive_candidates=ARCHIVE_CANDIDATES,
        excluded_generated=EXCLUDED_GENERATED,
    )


def print_plan(plan: SeparationPlan) -> None:
    print("Physical workspace separation preflight")
    print(f"Project: {plan.project}")
    print(f"Target root: {plan.target_root}")
    print(f"Status: {plan.status}")
    print()
    print("Blockers:")
    if plan.blockers:
        for blocker in plan.blockers:
            print(f"  - {blocker}")
    else:
        print("  none")
    print()
    print("Dirty entries:")
    if plan.dirty_entries:
        for entry in plan.dirty_entries:
            print(f"  - {entry.status} {entry.path}")
    else:
        print("  none")
    print()
    print("kitty-app candidates:")
    for path in plan.app_candidates:
        print(f"  - {path}")
    print()
    print("kitty-workbench candidates:")
    for path in plan.workbench_candidates:
        print(f"  - {path}")
    print()
    print("kitty-archives candidates:")
    for path in plan.archive_candidates:
        print(f"  - {path}")
    print()
    print("excluded generated/local paths:")
    for path in plan.excluded_generated:
        print(f"  - {path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Current Kitty project root.")
    parser.add_argument("--target-root", default=None, help="Future kitty-system parent path.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--allow-dirty-readonly",
        action="store_true",
        help="Exit zero even when blockers are found. The command still writes nothing.",
    )
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = build_plan(args.project, args.target_root)
    if args.json:
        print(json.dumps(asdict(plan), indent=2))
    else:
        print_plan(plan)
    if plan.blocked and not args.allow_dirty_readonly:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(run())
