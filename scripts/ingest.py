#!/usr/bin/env python3
"""Ingest files from a folder into Kitty's knowledge base.

Usage:
    python scripts/ingest.py <folder_path> [--sensitivity low|medium|high]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.knowledge import ingest_file

SUPPORTED = {".txt", ".md", ".pdf", ".rst"}


def main():
    parser = argparse.ArgumentParser(description="Ingest files into Kitty's knowledge base")
    parser.add_argument("folder", help="Folder to ingest")
    parser.add_argument("--sensitivity", default="low", choices=["low", "medium", "high", "medical", "financial"])
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"Error: folder not found: {folder}")
        sys.exit(1)

    files = [f for f in folder.rglob("*") if f.is_file() and f.suffix.lower() in SUPPORTED]
    if not files:
        print(f"No supported files found in {folder}")
        sys.exit(0)

    total = 0
    for f in files:
        print(f"Ingesting: {f.name}...", end=" ")
        n = ingest_file(f, sensitivity=args.sensitivity)
        print(f"{n} chunks")
        total += n

    print(f"\nDone. Total chunks stored: {total}")


if __name__ == "__main__":
    main()
