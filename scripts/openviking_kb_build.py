#!/usr/bin/env python3
"""Build one immutable OpenViking shadow generation from the engineering ~/kb allowlist."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ALLOWED_DIRS = ("wiki", "decisions", "projects", "corrections", "skills")
ALLOWED_ROOT_FILES = ("INDEX.md", "NOW.md", "SETUP.md", "CLAUDE.md", "models.md")
DEFAULT_PREFIX = "viking://resources/kitty-kb"


def target_for_generation(generation: str, prefix: str = DEFAULT_PREFIX) -> str:
    clean = generation.strip().replace("/", "-")
    if not clean or clean in {".", ".."}:
        raise ValueError("generation must be non-empty")
    return f"{prefix.rstrip('/')}-{clean}"


def build_plan(kb_root: Path, target: str) -> list[tuple[Path, str]]:
    plan: list[tuple[Path, str]] = []
    for name in ALLOWED_DIRS:
        source = kb_root / name
        if source.exists():
            plan.append((source, f"{target}/{name}"))
    for name in ALLOWED_ROOT_FILES:
        source = kb_root / name
        if source.exists():
            plan.append((source, f"{target}/root/{name}"))
    return plan


def git_head(path: Path) -> str | None:
    proc = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], text=True, capture_output=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def command_for(source: Path, target_uri: str, ov_bin: str) -> list[str]:
    return [ov_bin, "add-resource", str(source), "--to", target_uri,
            "--processing-mode", "vectors_only", "--wait", "--output", "json"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation", required=True, help="Immutable generation label")
    parser.add_argument("--kb-root", type=Path, default=Path.home() / "kb")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--ov-bin", default="ov")
    parser.add_argument("--apply", action="store_true", help="Actually create the new generation")
    args = parser.parse_args()

    kb_root = args.kb_root.expanduser().resolve()
    if not kb_root.is_dir():
        parser.error(f"KB root does not exist: {kb_root}")
    try:
        target = target_for_generation(args.generation, args.prefix)
    except ValueError as exc:
        parser.error(str(exc))

    plan = build_plan(kb_root, target)
    print(json.dumps({"kb_root": str(kb_root), "kb_git_head": git_head(kb_root),
                      "target": target, "items": len(plan), "apply": args.apply}))
    for source, target_uri in plan:
        cmd = command_for(source, target_uri, args.ov_bin)
        if not args.apply:
            print(json.dumps({"source": str(source), "target": target_uri, "command": cmd}))
            continue
        proc = subprocess.run(cmd, text=True, capture_output=True)
        print(json.dumps({"source": str(source), "target": target_uri,
                          "returncode": proc.returncode, "stdout": proc.stdout.strip(),
                          "stderr": proc.stderr.strip()}))
        if proc.returncode != 0:
            return proc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
