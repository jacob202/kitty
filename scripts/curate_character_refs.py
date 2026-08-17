#!/usr/bin/env python3
"""Curate private character refs without modifying originals."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.imagen.characters import character_source_dir, curate_references  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("character")
    parser.add_argument("--min-dimension", type=int, default=256)
    parser.add_argument("--max-dimension", type=int, default=1536)
    args = parser.parse_args()

    source = character_source_dir(args.character)
    output = source / "curated"
    report = curate_references(
        source,
        output,
        min_dimension=args.min_dimension,
        max_dimension=args.max_dimension,
    )
    print(json.dumps({
        "character": args.character,
        "source": str(source),
        "output": str(output),
        "included": report["included_count"],
        "excluded": report["excluded_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
