#!/usr/bin/env python3.12
"""Migration script: split gateway/ flat modules into subpackages.

Sequence: builder → memory → image → voice → stores.
One subpackage per commit. Run with --package=<name> and --dry-run.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATEWAY = REPO / "gateway"

# File groupings: package_name → {file_stem: source_filename}
PACKAGES = {
    "builder": {
        f.stem.replace("builder_", ""): f.name
        for f in sorted(GATEWAY.glob("builder_*.py"))
    },
    "memory": {
        f.stem.replace("memory_", "").lstrip("_") or "core": f.name
        for f in sorted(GATEWAY.glob("memory*.py"))
    },
    "image": {
        f.stem.replace("image_", "").lstrip("_") or "core": f.name
        for f in sorted(GATEWAY.glob("image*.py"))
    },
    "voice": {
        f.stem.replace("voice_", "").lstrip("_") or "core": f.name
        for f in sorted(GATEWAY.glob("voice*.py"))
    },
    "stores": {
        f.stem.replace("_store", ""): f.name
        for f in sorted(GATEWAY.glob("*_store.py"))
    },
}


def find_imports_to_rewrite(pkg: str, dry: bool) -> list[tuple[Path, str, str]]:
    """Find all import lines that reference the old flat module paths."""
    stems = [f.replace(".py", "") for f in sorted(PACKAGES[pkg].values())]

    rewrites = []
    for py_file in (list(GATEWAY.rglob("*.py")) + list((REPO / "tests").rglob("*.py"))
                    + list((REPO / "mcp").rglob("*.py"))):
        try:
            content = py_file.read_text()
        except Exception:
            continue

        for stem in stems:
            new_stem = stem.replace("builder_", "").replace("memory_", "").replace("image_", "").replace("voice_", "").replace("_store", "")
            if not new_stem:
                new_stem = "core"

            patterns = [
                (f"from gateway.{stem}", f"from gateway.{pkg}.{new_stem}"),
                (f"import gateway.{stem}", f"import gateway.{pkg}.{new_stem}"),
            ]

            for old, new in patterns:
                if old in content and old != new:
                    rewrites.append((py_file, old, new))

    return rewrites


def git_mv(src: str, dst: str, dry: bool) -> None:
    cmd = ["git", "mv", src, dst]
    if dry:
        print(f"  DRY: {' '.join(cmd)}")
    else:
        subprocess.run(cmd, check=True, cwd=REPO)


def rewrite_imports(rewrites: list[tuple[Path, str, str]], dry: bool) -> None:
    if not rewrites:
        return
    by_file: dict[Path, list[tuple[str, str]]] = {}
    for path, old, new in rewrites:
        if old == new:
            continue
        by_file.setdefault(path, []).append((old, new))

    for path, pairs in by_file.items():
        content = path.read_text()
        for old, new in pairs:
            content = content.replace(old, new)
        if dry:
            print(f"  DRY: rewrite {len(pairs)} imports in {path.relative_to(REPO)}")
        else:
            path.write_text(content)
            print(f"  Rewrote {len(pairs)} imports in {path.relative_to(REPO)}")


def migrate_package(pkg: str, dry: bool) -> None:
    print(f"\n{'='*60}\nMigrating gateway/{pkg}/\n{'='*60}")

    pkg_dir = GATEWAY / pkg
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").touch()

    # Move files
    for new_stem, src_filename in PACKAGES[pkg].items():
        src = f"gateway/{src_filename}"
        dst = f"gateway/{pkg}/{new_stem}.py" if new_stem else f"gateway/{pkg}/core.py"
        git_mv(src, dst, dry)

    # Find and rewrite imports
    rewrites = find_imports_to_rewrite(pkg, dry)
    rewrite_imports(rewrites, dry)

    # Verify: check that no old imports remain
    old_imports = []
    for py_file in (list(GATEWAY.rglob("*.py")) + list((REPO / "tests").rglob("*.py"))
                    + list((REPO / "mcp").rglob("*.py"))):
        try:
            content = py_file.read_text()
        except Exception:
            continue
        for stem in PACKAGES[pkg].keys():
            if f"gateway.{stem}" in content:
                old_imports.append(f"{py_file.relative_to(REPO)}: gateway.{stem}")

    if old_imports:
        print(f"\n  WARNING: {len(old_imports)} old imports still found:")
        for imp in old_imports[:10]:
            print(f"    {imp}")
        if len(old_imports) > 10:
            print(f"    ... and {len(old_imports) - 10} more")

    print(f"\n  Done: {len(PACKAGES[pkg])} files moved to gateway/{pkg}/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True, choices=list(PACKAGES))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--all", action="store_true", help="Migrate all packages sequentially")
    args = ap.parse_args()

    if args.all:
        for pkg in PACKAGES:
            migrate_package(pkg, args.dry_run)
    else:
        migrate_package(args.package, args.dry_run)

    print(f"\nAll done. Check with: git status")


if __name__ == "__main__":
    main()
