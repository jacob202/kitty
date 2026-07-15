#!/usr/bin/env python3
"""docs_lint.py — Validate documentation governance.

Checks:
- All .md files in docs/ have valid YAML frontmatter with required fields.
- Referenced documents exist (derives_from, implements, referenced_by, superseded_by).
- No orphan foundational documents.
- SYSTEM_MAP.md is current (checked separately via --check).

Usage:
    python3 scripts/docs_lint.py
    python3 scripts/docs_lint.py --check-system-map
"""

import os
import sys
import yaml
from pathlib import Path

REQUIRED_FIELDS = {"type", "title", "status", "owner", "primary_purpose", "derives_from", "review_cycle"}
FOUNDATIONAL_TYPES = {"vision", "constitution", "architecture", "governance", "model", "methodology", "roadmap", "index"}
SKIP_DIRS = {"codemap", "archive", "retired", "examples", "fable-context", "packets", "evidence", "initiatives", ".DS_Store"}
errors = []


def read_frontmatter(path: Path):
    with open(path) as f:
        content = f.read()
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    try:
        return yaml.safe_load(content[3:end]) or {}
    except yaml.YAMLError:
        return None


def collect_docs(root: Path):
    docs = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            if fname.endswith(".md"):
                docs.append(Path(dirpath) / fname)
    return docs


def main():
    docs_root = Path(__file__).parent.parent / "docs"
    all_docs = collect_docs(docs_root)
    doc_paths = {str(d.relative_to(docs_root)) for d in all_docs}
    doc_paths |= {f"docs/{p}" for p in doc_paths}

    for doc in all_docs:
        rel = str(doc.relative_to(docs_root))
        fm = read_frontmatter(doc)
        if fm is None:
            errors.append(f"{rel}: [missing-frontmatter] No valid YAML frontmatter found")
            continue

        missing = REQUIRED_FIELDS - set(fm.keys())
        if missing:
            errors.append(f"{rel}: [missing-fields] Missing required fields: {missing}")

        for field in ("derives_from", "implements", "referenced_by", "supersedes", "superseded_by"):
            refs = fm.get(field, [])
            if isinstance(refs, str):
                refs = [refs]
            for ref in refs:
                if ref == "docs/adr/*":
                    continue
                if ref not in doc_paths:
                    errors.append(f"{rel}: [broken-reference] {field} references '{ref}' which does not exist")

        doc_type = fm.get("type", "")
        status = fm.get("status", "")
        if doc_type in FOUNDATIONAL_TYPES and status not in ("canonical", "draft", "deprecated", "superseded"):
            errors.append(f"{rel}: [invalid-status] Foundational doc has status '{status}' (expected canonical, draft, deprecated, or superseded)")

    # Check for orphan foundational documents
    foundational = []
    for doc in all_docs:
        rel = str(doc.relative_to(docs_root))
        fm = read_frontmatter(doc)
        if fm and fm.get("type") in FOUNDATIONAL_TYPES and fm.get("status") in ("canonical", "draft"):
            foundational.append((rel, fm))

    for rel, fm in foundational:
        has_derives = bool(fm.get("derives_from"))
        has_refs = bool(fm.get("referenced_by"))
        has_implements = bool(fm.get("implements"))
        if not has_derives and not has_refs and not has_implements:
            errors.append(f"{rel}: [orphan] Foundational document has no derives_from, referenced_by, or implements")

    # Check SYSTEM_MAP freshness
    system_map = docs_root / "SYSTEM_MAP.md"
    if system_map.exists():
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "docs_system_map.py"), "--check"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            errors.append("docs/SYSTEM_MAP.md: [stale-system-map] SYSTEM_MAP.md is stale. Run: python3 scripts/docs_system_map.py")

    if errors:
        print(f"Documentation lint failed with {len(errors)} error(s):\n")
        for e in sorted(errors):
            print(f"  {e}")
        sys.exit(1)

    print("Documentation lint passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
