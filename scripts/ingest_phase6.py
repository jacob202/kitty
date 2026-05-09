#!/usr/bin/env python3
"""Phase 6 full ingestion sweep — Claude sessions, ChatGPT export, Claude.ai export, journal.db."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.knowledge import ingest_file, _extract_sqlite_journal

CLAUDE_CODE_DIR = Path.home() / ".claude/projects/-Users-jacobbrizinski-Projects-kitty"
CHATGPT_DIR = Path("/Users/jacobbrizinski/Projects/kitty/data/imports/chatgpt/2026-03-10-openai-export")
CLAUDE_AI_EXPORT_DIR = Path("/Users/jacobbrizinski/Projects/kitty/data/imports/claude")
JOURNAL_DB = Path("/Users/jacobbrizinski/Projects/kitty/data/journal.db")


def sweep(label: str, files: list, sensitivity: str = "low") -> int:
    total = 0
    for f in files:
        print(f"  [{label}] {f.name}...", end=" ", flush=True)
        try:
            n = ingest_file(f, sensitivity=sensitivity, source_label=f"{label}::{f.name}")
            if n == 0:
                print("already ingested")
            else:
                print(f"{n} chunks")
            total += n
        except Exception as e:
            print(f"ERROR: {e}")
    return total


def main():
    grand_total = 0

    # 1 — Claude Code session transcripts
    if CLAUDE_CODE_DIR.exists():
        files = sorted(CLAUDE_CODE_DIR.glob("*.jsonl"))
        print(f"\n=== Claude Code sessions ({len(files)} files) ===")
        grand_total += sweep("claude_session", files, "low")
    else:
        print(f"WARNING: Claude Code sessions dir not found: {CLAUDE_CODE_DIR}")

    # 2 — ChatGPT export
    if CHATGPT_DIR.exists():
        files = sorted(CHATGPT_DIR.glob("conversations-*.json"))
        print(f"\n=== ChatGPT export ({len(files)} files) ===")
        grand_total += sweep("chatgpt", files, "low")
    else:
        print(f"INFO: No ChatGPT export at {CHATGPT_DIR}")

    # 3 — Claude.ai export (if present)
    if CLAUDE_AI_EXPORT_DIR.exists():
        # Claude.ai exports conversations as JSON
        files = sorted(CLAUDE_AI_EXPORT_DIR.glob("**/*.json"))
        print(f"\n=== Claude.ai export ({len(files)} files) ===")
        grand_total += sweep("claude_ai", files, "low")
    else:
        print(f"INFO: No Claude.ai export at {CLAUDE_AI_EXPORT_DIR} — add files there when ready")

    # 4 — journal.db (SQLite → temp text → ingest)
    if JOURNAL_DB.exists():
        print(f"\n=== journal.db ===")
        import tempfile
        text = _extract_sqlite_journal(JOURNAL_DB)
        if text.strip():
            with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, prefix="journal_") as f:
                f.write(text)
                tmp = Path(f.name)
            n = ingest_file(tmp, sensitivity="low", source_label="journal.db", doc_type="session_log")
            tmp.unlink()
            print(f"  journal.db -> {n} chunks")
            grand_total += n
        else:
            print("  journal.db: empty or no journal table")
    else:
        print(f"INFO: journal.db not found at {JOURNAL_DB}")

    print(f"\n=== Phase 6 ingestion complete. Total new chunks: {grand_total} ===")

    # Report ChromaDB state
    try:
        import chromadb
        client = chromadb.PersistentClient(path="data/knowledge_db")
        col = client.get_or_create_collection("kitty_knowledge")
        print(f"ChromaDB total chunks: {col.count()}")
    except Exception as e:
        print(f"Could not query ChromaDB: {e}")


if __name__ == "__main__":
    main()
