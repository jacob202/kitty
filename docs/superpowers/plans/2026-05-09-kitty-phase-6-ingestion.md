# Phase 6 — Full Ingestion Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest all existing data sources — 63 Claude Code session transcripts, 130 MB ChatGPT export, and journal.db — into Kitty's ChromaDB knowledge base so she can recall decisions and conversations from months ago.

**Architecture:** Add two new extractors to `gateway/knowledge.py` (ChatGPT JSON format + SQLite journal). Create `scripts/ingest_phase6.py` as the orchestrator. TDD throughout — write failing tests first.

**Tech Stack:** Python 3.12, ChromaDB (existing), SQLite3 (stdlib), existing `ingest_file()` pipeline, nomic-embed-text via Ollama.

---

## Data Sources

| Source | Location | Count | Format |
|---|---|---|---|
| Claude Code sessions | `~/.claude/projects/-Users-jacobbrizinski-Projects-kitty/*.jsonl` | 63 files | JSONL (one JSON per line) — already handled |
| ChatGPT export | `data/imports/chatgpt/2026-03-10-openai-export/conversations-*.json` | 7 files, 130 MB | Single JSON array of conversations |
| journal.db | `data/journal.db` | 1 file | SQLite `journal(id, timestamp, role, content)` |

---

## File Map

| File | Change |
|---|---|
| `gateway/knowledge.py` | Add `_extract_chatgpt_json()`, `_extract_sqlite_journal()`, update `_extract_text()` dispatch |
| `tests/test_knowledge.py` | Add 4 new tests for ChatGPT and journal extractors |
| `scripts/ingest_phase6.py` | New — orchestrates full sweep with progress reporting |
| `scripts/setup/gate-check.sh` | Add Phase 6 gate (chunk count ≥ 100 in ChromaDB) |

---

## Task 1: Write failing tests for new extractors

**Files:**
- Modify: `tests/test_knowledge.py`

- [ ] **Step 1: Add 4 tests**

```python
# At bottom of tests/test_knowledge.py

import json, sqlite3, tempfile
from pathlib import Path

def test_extract_chatgpt_json_returns_text():
    from gateway.knowledge import _extract_chatgpt_json
    conv = {
        "title": "Test Chat",
        "id": "abc",
        "mapping": {
            "node1": {"id": "node1", "parent": None, "children": ["node2"],
                      "message": {"author": {"role": "user"}, "create_time": 1.0,
                                  "content": {"content_type": "text", "parts": ["Hello Kitty"]}}},
            "node2": {"id": "node2", "parent": "node1", "children": [],
                      "message": {"author": {"role": "assistant"}, "create_time": 2.0,
                                  "content": {"content_type": "text", "parts": ["Hi Jacob!"]}}}
        }
    }
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump([conv], f)
        tmp = Path(f.name)
    text = _extract_chatgpt_json(tmp)
    assert "Hello Kitty" in text
    assert "Hi Jacob!" in text
    assert "USER:" in text
    assert "ASSISTANT:" in text


def test_extract_chatgpt_json_skips_empty_parts():
    from gateway.knowledge import _extract_chatgpt_json
    conv = {
        "title": "Empty",
        "id": "xyz",
        "mapping": {
            "n1": {"id": "n1", "parent": None, "children": [],
                   "message": {"author": {"role": "user"}, "create_time": 1.0,
                               "content": {"content_type": "text", "parts": [""]}}}
        }
    }
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump([conv], f)
        tmp = Path(f.name)
    text = _extract_chatgpt_json(tmp)
    assert text == ""


def test_extract_sqlite_journal_returns_text():
    from gateway.knowledge import _extract_sqlite_journal
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE journal (id INTEGER PRIMARY KEY, timestamp TEXT, role TEXT, content TEXT, content_hash TEXT)")
    conn.execute("INSERT INTO journal VALUES (1,'2026-01-01','user','What is up?','hash1')")
    conn.execute("INSERT INTO journal VALUES (2,'2026-01-01','assistant','Not much.','hash2')")
    conn.commit(); conn.close()
    text = _extract_sqlite_journal(db_path)
    assert "USER: What is up?" in text
    assert "ASSISTANT: Not much." in text


def test_extract_text_dispatches_chatgpt_json():
    from gateway.knowledge import _extract_text
    conv = {
        "title": "Dispatch test",
        "id": "d1",
        "mapping": {
            "n1": {"id": "n1", "parent": None, "children": [],
                   "message": {"author": {"role": "user"}, "create_time": 1.0,
                               "content": {"content_type": "text", "parts": ["dispatch works"]}}}
        }
    }
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump([conv], f)
        tmp = Path(f.name)
    text = _extract_text(tmp)
    assert "dispatch works" in text
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/jacobbrizinski/Projects/kitty
venv/bin/pytest tests/test_knowledge.py::test_extract_chatgpt_json_returns_text tests/test_knowledge.py::test_extract_sqlite_journal_returns_text -v 2>&1 | tail -10
```

Expected: ImportError or AttributeError (functions don't exist yet)

---

## Task 2: Add extractors to gateway/knowledge.py

**Files:**
- Modify: `gateway/knowledge.py`

- [ ] **Step 1: Add `_extract_chatgpt_json` and `_extract_sqlite_journal` functions**

Add after `_extract_jsonl_session()` (around line 236):

```python
def _extract_chatgpt_json(path: Path) -> str:
    """Extract text from OpenAI ChatGPT export JSON (list of conversations)."""
    try:
        data = json.loads(path.read_text(errors="ignore"))
    except Exception as e:
        logger.warning("ChatGPT JSON parse failed for %s: %s", path.name, e)
        return ""
    if not isinstance(data, list):
        return ""
    blocks = []
    for conv in data:
        title = conv.get("title", "Untitled")
        mapping = conv.get("mapping", {})
        # Collect messages sorted by create_time
        messages = []
        for node in mapping.values():
            msg = node.get("message")
            if not msg:
                continue
            role = msg.get("author", {}).get("role", "")
            if role not in {"user", "assistant"}:
                continue
            content = msg.get("content", {})
            parts = content.get("parts", []) if isinstance(content, dict) else []
            text = " ".join(str(p) for p in parts if isinstance(p, str) and p.strip())
            if not text:
                continue
            create_time = msg.get("create_time") or 0
            messages.append((create_time, role.upper(), text[:600]))
        messages.sort(key=lambda x: x[0])
        if messages:
            lines = [f"CONVERSATION: {title}"]
            lines += [f"{role}: {text}" for _, role, text in messages]
            blocks.append("\n".join(lines))
    return "\n\n---\n\n".join(blocks)


def _extract_sqlite_journal(path: Path) -> str:
    """Extract role/content pairs from a SQLite journal table."""
    import sqlite3
    try:
        conn = sqlite3.connect(str(path))
        rows = conn.execute(
            "SELECT role, content FROM journal ORDER BY timestamp, id"
        ).fetchall()
        conn.close()
        lines = [f"{role.upper()}: {content[:600]}" for role, content in rows if content]
        return "\n\n".join(lines)
    except Exception as e:
        logger.warning("SQLite journal extract failed for %s: %s", path.name, e)
        return ""
```

- [ ] **Step 2: Update `_extract_text` to dispatch ChatGPT JSON**

Replace the `.json` branch in `_extract_text`:

```python
elif suffix == ".jsonl":
    return _extract_jsonl_session(path)
elif suffix == ".json":
    # Distinguish ChatGPT export (JSON array) from Claude JSONL-as-JSON
    try:
        first_char = path.read_text(errors="ignore").lstrip()[:1]
    except Exception:
        first_char = ""
    if first_char == "[":
        return _extract_chatgpt_json(path)
    return _extract_jsonl_session(path)
```

- [ ] **Step 3: Run all tests**

```bash
cd /Users/jacobbrizinski/Projects/kitty
venv/bin/pytest tests/test_knowledge.py -v 2>&1 | tail -20
```

Expected: all tests pass (including the 4 new ones)

- [ ] **Step 4: Commit**

```bash
git add gateway/knowledge.py tests/test_knowledge.py
git commit -m "feat: Phase 6 — ChatGPT + journal extractors in knowledge.py"
```

---

## Task 3: Create scripts/ingest_phase6.py

**Files:**
- Create: `scripts/ingest_phase6.py`

- [ ] **Step 1: Create the orchestrator**

```python
#!/usr/bin/env python3
"""Phase 6 full ingestion sweep — Claude sessions, ChatGPT export, journal.db."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.knowledge import ingest_file, _extract_sqlite_journal

CLAUDE_SESSIONS_DIR = Path.home() / ".claude/projects/-Users-jacobbrizinski-Projects-kitty"
CHATGPT_DIR = Path("/Users/jacobbrizinski/Projects/kitty/data/imports/chatgpt/2026-03-10-openai-export")
JOURNAL_DB = Path("/Users/jacobbrizinski/Projects/kitty/data/journal.db")


def sweep(label: str, files: list, sensitivity: str = "low") -> int:
    total = 0
    for f in files:
        print(f"  [{label}] {f.name}...", end=" ", flush=True)
        try:
            n = ingest_file(f, sensitivity=sensitivity, source_label=f"{label}::{f.name}")
            print(f"{n} chunks")
            total += n
        except Exception as e:
            print(f"ERROR: {e}")
    return total


def main():
    grand_total = 0

    # 1 — Claude Code sessions
    if CLAUDE_SESSIONS_DIR.exists():
        files = sorted(CLAUDE_SESSIONS_DIR.glob("*.jsonl"))
        print(f"\n=== Claude Code sessions ({len(files)} files) ===")
        grand_total += sweep("claude_session", files, "low")
    else:
        print(f"WARNING: Claude sessions dir not found: {CLAUDE_SESSIONS_DIR}")

    # 2 — ChatGPT export
    if CHATGPT_DIR.exists():
        files = sorted(CHATGPT_DIR.glob("conversations-*.json"))
        print(f"\n=== ChatGPT export ({len(files)} files) ===")
        grand_total += sweep("chatgpt", files, "low")
    else:
        print(f"WARNING: ChatGPT dir not found: {CHATGPT_DIR}")

    # 3 — journal.db (SQLite → temp text file → ingest)
    if JOURNAL_DB.exists():
        print(f"\n=== journal.db ===")
        import tempfile
        text = _extract_sqlite_journal(JOURNAL_DB)
        if text.strip():
            with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, prefix="journal_") as f:
                f.write(text)
                tmp = Path(f.name)
            n = ingest_file(tmp, sensitivity="low", source_label="journal.db",
                            doc_type="session_log")
            tmp.unlink()
            print(f"  journal.db → {n} chunks")
            grand_total += n
        else:
            print("  journal.db: empty or parse failed")
    else:
        print(f"WARNING: journal.db not found: {JOURNAL_DB}")

    print(f"\n✓ Phase 6 ingestion complete. Total new chunks: {grand_total}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make executable and test dry-run (no Ollama needed — just import check)**

```bash
cd /Users/jacobbrizinski/Projects/kitty
python scripts/ingest_phase6.py --help 2>&1 || python -c "import scripts.ingest_phase6" 2>&1 | head -5
```

- [ ] **Step 3: Commit**

```bash
git add scripts/ingest_phase6.py
git commit -m "feat: Phase 6 — ingest_phase6.py orchestrates full sweep"
```

---

## Task 4: Update gate-check.sh with Phase 6 gate

**Files:**
- Modify: `scripts/setup/gate-check.sh`

- [ ] **Step 1: Append Phase 6 gate**

Add at end of gate-check.sh:

```bash
if [[ "$1" == "6" ]]; then
  echo "=== Phase 6: Full Ingestion Sweep ==="
  check "ingest_phase6.py exists" "test -f scripts/ingest_phase6.py"
  check "ChatGPT extractor in knowledge.py" "grep -q '_extract_chatgpt_json' gateway/knowledge.py"
  check "journal extractor in knowledge.py" "grep -q '_extract_sqlite_journal' gateway/knowledge.py"
  check "knowledge tests pass" "venv/bin/pytest tests/test_knowledge.py -q --tb=no 2>/dev/null | grep -q 'passed'"
  echo ""
  echo "PASS=$PASS FAIL=$FAIL"
  [[ $FAIL -eq 0 ]] && echo "Gate 6 PASSED" || { echo "Gate 6 FAILED"; exit 1; }
fi
```

- [ ] **Step 2: Run gate**

```bash
cd /Users/jacobbrizinski/Projects/kitty
bash scripts/setup/gate-check.sh 6
```

Expected: Gate 6 PASSED

- [ ] **Step 3: Commit**

```bash
git add scripts/setup/gate-check.sh
git commit -m "chore: Phase 6 gate check"
```

---

## Task 5: Run the actual ingestion

- [ ] **Step 1: Verify Ollama is running (required for embeddings)**

```bash
curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; models=[m['name'] for m in json.load(sys.stdin)['models']]; print('nomic-embed-text present:', any('nomic' in m for m in models))"
```

If not running: `ollama serve &`
If nomic-embed-text missing: `ollama pull nomic-embed-text`

- [ ] **Step 2: Run Phase 6 ingestion**

```bash
cd /Users/jacobbrizinski/Projects/kitty
set -a && source .env && set +a
python scripts/ingest_phase6.py 2>&1 | tee logs/phase6_ingestion.log
```

- [ ] **Step 3: Verify chunk count in ChromaDB**

```bash
python3 -c "
import chromadb
client = chromadb.PersistentClient(path='data/knowledge_db')
col = client.get_or_create_collection('kitty_knowledge')
print('Total chunks:', col.count())
sources = set(m['source'] for m in col.get()['metadatas'])
print('Unique sources:', len(sources))
print('Sample sources:', list(sources)[:5])
"
```

Expected: >100 chunks, sources include `claude_session::*` and `chatgpt::conversations-*`

- [ ] **Step 4: Test a real query**

```bash
python3 -c "
import sys; sys.path.insert(0,'.')
from gateway.knowledge import get_knowledge_block
result = get_knowledge_block('Kitty architecture decisions')
print(result[:800] if result else 'NO RESULTS — check Ollama is running')
"
```

- [ ] **Step 5: Update SESSION_HANDOFF.md phase table to mark Phase 6 complete**

- [ ] **Step 6: Final commit**

```bash
git add logs/phase6_ingestion.log SESSION_HANDOFF.md
git commit -m "feat: Phase 6 complete — full ingestion sweep"
```

---

## Verification

Gate command: `bash scripts/setup/gate-check.sh 6`
All tests: `venv/bin/pytest tests/ -q`
Spot check: Query ChromaDB for a past decision and confirm relevant chunks surface.
