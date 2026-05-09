#!/usr/bin/env python3
"""Phase 9 CLI — ingest one or more PDFs into Kitty's ChromaDB knowledge base.

Usage:
    python scripts/ingest_pdf.py path/to/file.pdf
    python scripts/ingest_pdf.py path/to/docs_folder/
"""
from __future__ import annotations
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_pdf.py <pdf_file_or_dir>")
        sys.exit(1)

    target = Path(sys.argv[1])
    if not target.exists():
        print(f"Error: {target} does not exist")
        sys.exit(1)

    pdfs = sorted(target.rglob("*.pdf")) if target.is_dir() else [target]
    if not pdfs:
        print(f"No PDFs found in {target}")
        sys.exit(0)

    from gateway.knowledge import ingest_file

    total = 0
    for pdf in pdfs:
        try:
            n = ingest_file(pdf, sensitivity="low")
            print(f"  ✓ {pdf.name} — {n} chunks")
            total += n
        except Exception as exc:
            print(f"  ✗ {pdf.name} — {exc}")

    print(f"\nDone. Total chunks ingested: {total}")


if __name__ == "__main__":
    main()
