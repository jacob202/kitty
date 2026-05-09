#!/usr/bin/env python3
"""Ingest files from a folder into Kitty's knowledge base.

Usage:
    python scripts/ingest.py <folder_path> [--sensitivity low|medium|high] [--verify]
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.knowledge import ingest_file, search_knowledge

SUPPORTED = {".txt", ".md", ".pdf", ".rst", ".csv", ".jpg", ".jpeg", ".png", ".epub", ".mobi", ".azw3"}

def verify_latest(source_name: str):
    """
    Query ChromaDB for the exact source name and print a sample chunk to verify quality.
    """
    print(f"  [Verification: {source_name}]")
    
    try:
        from gateway.knowledge import _get_collection
        collection = _get_collection()
        
        # Exact match on source metadata
        results = collection.get(
            where={"source": source_name},
            limit=1,
            include=["documents", "metadatas"]
        )
        
        if not results["ids"]:
            print(f"  !! FAILED: No chunks found for '{source_name}'.")
            return

        text = results["documents"][0]
        meta = results["metadatas"][0]
        
        print(f"  Type: {meta.get('doc_type', 'unknown')}")
        print(f"  Sample: \"{text[:150].replace('\\n', ' ')}...\"")
    except Exception as e:
        print(f"  !! Verification error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Ingest files into Kitty's knowledge base")
    parser.add_argument("folder", help="Folder to ingest")
    parser.add_argument("--sensitivity", default="low", choices=["low", "medium", "high", "medical", "financial"])
    parser.add_argument("--doc-type", help="Force a specific doc type (e.g. 'textbook', 'service_manual', 'general')")
    parser.add_argument("--force-refresh", action="store_true", help="Re-ingest even if content hash matches")
    parser.add_argument("--verify", action="store_true", help="Print sample chunks after each file to verify quality")
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
    skipped = 0
    for f in files:
        print(f"Processing: {f.name}...", end=" ", flush=True)
        try:
            n = ingest_file(f, sensitivity=args.sensitivity, doc_type=args.doc_type, force_refresh=args.force_refresh)
            if n > 0:
                print(f"{n} chunks ingested.")
                total += n
                if args.verify:
                    verify_latest(f.name)
            else:
                print("Skipped (already ingested or empty).")
                skipped += 1
        except Exception as e:
            print(f"Failed: {e}")

    print(f"\nIngestion Complete:")
    print(f" - New chunks stored: {total}")
    print(f" - Files skipped: {skipped}")
    print(f" - Total files processed: {len(files)}")

if __name__ == "__main__":
    main()
