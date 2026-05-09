#!/usr/bin/env python3
"""
Build file index cache for fast searches.
Run: python scripts/build_file_index.py
Then search with: python scripts/build_file_index.py --search <pattern>
"""

import json
import os
import sys
from pathlib import Path

INDEX_FILE = Path("data/cache/file_index.json")
IGNORES = {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache", "data/chroma"}

def build_index(root: Path = Path(".")) -> dict:
    index = {"py": [], "md": [], "json": [], "sh": [], "yaml": []}
    IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache", 
                  "data/chroma", "evals/artifacts", "garage-ui/.next"}
    for ext, paths in index.items():
        for f in root.rglob(f"*.{ext}"):
            rel = f.relative_to(root)
            # Skip ignored dirs and evals artifacts
            if any(ig in rel.parts for ig in IGNORE_DIRS):
                continue
            paths.append(str(rel))
    return index

def main():
    if "--search" in sys.argv:
        idx = 0
        if INDEX_FILE.exists():
            with open(INDEX_FILE) as f:
                data = json.load(f)
        else:
            print("No index. Run: python scripts/build_file_index.py")
            return
        pattern = sys.argv[sys.argv.index("--search") + 1]
        # Filter out evals artifacts + garage-ui
        for ext, files in data.items():
            for f in files:
                if "evals/" in f or "garage-ui/" in f:
                    continue
                if pattern.lower() in f.lower():
                    print(f)
                    idx += 1
        print(f"Found {idx} matches")
        return
    data = build_index()
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w") as f:
        json.dump(data, f, indent=2)
    total = sum(len(v) for v in data.values())
    print(f"✓ Indexed {total} files → {INDEX_FILE}")

if __name__ == "__main__":
    main()