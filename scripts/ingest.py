#!/usr/bin/env python3
"""CLI to ingest files from a folder into Kitty's knowledge base (Chroma).

This script does NOT reimplement the pipeline. Every file is passed to
``gateway.knowledge.ingest``, which runs Clerk (extract) → Librarian (judgment)
→ Archivist (chunk, embed, store).

To drain the SQLite queue (after ``enqueue_books.py``), run:
  python scripts/ingest.py --worker

Selective ingest (recommended for large Books trees):
  python scripts/audit_books_folder.py ~/Desktop/Books --emit-manifest data/books_ingest_manifest.txt
  python scripts/ingest.py --manifest data/books_ingest_manifest.txt

Usage:
    python scripts/ingest.py <folder_path> [--sensitivity low|medium|high] [--verify]
    python scripts/ingest.py --manifest paths.txt
"""
import asyncio
import argparse
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gateway.knowledge import ingest, search

CLAUDE_CODE_DIR = Path.home() / ".claude/projects/-Users-jacobbrizinski-Projects-kitty"
CHATGPT_DIR = ROOT / "data/imports/chatgpt/2026-03-10-openai-export"
CLAUDE_AI_EXPORT_DIR = ROOT / "data/imports/claude"
BOOKS_DIR = Path.home() / "Desktop" / "Books"
JOURNAL_DB = ROOT / "data/journal.db"
BOOK_MIN_BYTES = 1024
SUPPORTED = {
    ".txt",
    ".md",
    ".pdf",
    ".rst",
    ".csv",
    ".json",
    ".jsonl",
    ".jpg",
    ".jpeg",
    ".png",
    ".epub",
    ".mobi",
    ".azw3",
}


async def verify_latest(source_name: str):
    """Search for the source we just ingested to confirm it's there."""
    try:
        results = await search(source_name, limit=1)
        if results:
            print(f"  [Verification: {source_name}]")
            print(f"  Type: {results[0]['doc_type']}")
            print(f"  Sample: \"{results[0]['text'][:60]}...\"")
        else:
            print(f"  !! Verification failed: {source_name} not found in search results.")
    except Exception as e:
        print(f"  !! Verification error: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Ingest files into Kitty's knowledge base")
    parser.add_argument("folder", nargs="?", help="Folder to ingest (ignored if --manifest is set)")
    parser.add_argument(
        "--sensitivity",
        default="low",
        choices=["low", "medium", "high", "medical", "financial"],
    )
    parser.add_argument("--doc-type", help="Force a specific document type")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore content hash and re-ingest")
    parser.add_argument("--verify", action="store_true", help="Verify ingestion by searching for the file")
    parser.add_argument("--worker", action="store_true", help="Run as background queue worker")
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Only ingest files listed (one absolute or relative path per line; # comments ok).",
    )

    args = parser.parse_args()

    if args.worker:
        from gateway.ingestion_queue import process_queue

        await process_queue()
        return

    if args.manifest:
        if not args.manifest.is_file():
            print(f"Error: manifest not found: {args.manifest}")
            return
        raw = args.manifest.read_text(encoding="utf-8").splitlines()
        files = []
        root = Path(__file__).resolve().parent.parent
        for line in raw:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = Path(line).expanduser()
            if not p.is_absolute():
                p = (ROOT / p).resolve()
            else:
                p = p.resolve()
            if p.is_file() and p.suffix.lower() in SUPPORTED:
                files.append(p)
            elif p.is_file():
                print(f"Skip unsupported type: {p}", flush=True)
            else:
                print(f"Missing (skipped): {p}", flush=True)
        files = sorted(set(files))
    else:
        if not args.folder:
            parser.print_help()
            return

        path = Path(args.folder)
        if not path.exists():
            print(f"Error: folder not found: {args.folder}")
            return

        files = sorted([f for f in path.rglob("*") if f.is_file() and f.suffix.lower() in SUPPORTED])

    if not files:
        print("No files to process.")
        return

    print(f"Processing {len(files)} files...\n")
    total = 0
    skipped = 0

    for f in files:
        print(f"Processing: {f.name}...", end=" ", flush=True)
        try:
            result = await ingest(
                f,
                sensitivity=args.sensitivity,
                doc_type=args.doc_type,
                force_refresh=args.force_refresh,
            )
            if result.status == "success":
                print(f"{result.chunks_count} chunks ingested.")
                total += result.chunks_count
                if args.verify:
                    await verify_latest(f.name)
            elif result.status == "skipped":
                print("Skipped (already ingested or empty).")
                skipped += 1
            else:
                print(f"Failed: {result.error_message}")
        except Exception as e:
            print(f"Failed: {e}")

    print(f"\nIngestion Complete:")
    print(f" - New chunks stored: {total}")
    print(f" - Files skipped: {skipped}")
    print(f" - Total files processed: {len(files)}")


if __name__ == "__main__":
    asyncio.run(main())
