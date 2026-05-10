# Phase 16 — AI Model Digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch the OpenRouter model catalog daily, diff it against yesterday's snapshot, detect new models and price changes, store deltas in SQLite, and surface the top 3 changes in the morning brief so Jacob always knows when a better/cheaper model drops.

**Architecture:** `gateway/model_digest.py` owns all logic: fetch → parse → diff → store → summarize. It writes to `data/model_digest.db` (SQLite, two tables: `model_snapshots` for current state, `digest_log` for detected events). `gateway/brief.py`'s `generate_brief()` calls `get_model_digest_section()` to append a "Model News" block. A launchd plist runs the fetch daily at 6:55am (before the 7am brief).

**Tech Stack:** requests (existing), sqlite3 (stdlib), feedparser (existing — not used here), Python 3.11+

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `gateway/model_digest.py` | Create | Fetch, diff, store, summarize model catalog |
| `tests/test_model_digest.py` | Create | Tests for digest logic (mocked HTTP) |
| `gateway/brief.py` | Modify | Inject `get_model_digest_section()` into brief |
| `kitty_gateway/com.kitty.model-digest.plist` | Create | launchd plist — runs daily at 6:55am |
| `scripts/setup/gate-check.sh` | Modify | Phase 16 gate |

---

### Task 1: model_digest.py

**Files:**
- Create: `gateway/model_digest.py`
- Test: `tests/test_model_digest.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_model_digest.py
"""Tests for AI model digest — mocked HTTP, real SQLite (in-memory)."""
import os
import sqlite3
from unittest.mock import patch, MagicMock
import gateway.model_digest as digest_module


FAKE_MODELS_RESPONSE = {
    "data": [
        {
            "id": "openai/gpt-4o",
            "name": "GPT-4o",
            "pricing": {"prompt": "0.0000025", "completion": "0.000010"},
            "context_length": 128000,
        },
        {
            "id": "google/gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "pricing": {"prompt": "0.000000075", "completion": "0.0000003"},
            "context_length": 1048576,
        },
    ]
}


def _mock_openrouter(response_data):
    mock_resp = MagicMock()
    mock_resp.json.return_value = response_data
    mock_resp.raise_for_status = MagicMock()
    return patch("requests.get", return_value=mock_resp)


def test_fetch_models_returns_list():
    with _mock_openrouter(FAKE_MODELS_RESPONSE):
        models = digest_module.fetch_models()
    assert len(models) == 2
    assert models[0]["id"] == "openai/gpt-4o"


def test_parse_model_extracts_fields():
    raw = FAKE_MODELS_RESPONSE["data"][0]
    parsed = digest_module._parse_model(raw)
    assert parsed["id"] == "openai/gpt-4o"
    assert parsed["name"] == "GPT-4o"
    assert parsed["prompt_price"] == 0.0000025
    assert parsed["completion_price"] == 0.000010
    assert parsed["context_length"] == 128000


def test_detect_new_model():
    previous = {}
    current = {"openai/gpt-4o": {"id": "openai/gpt-4o", "name": "GPT-4o",
                                   "prompt_price": 0.0000025, "completion_price": 0.000010,
                                   "context_length": 128000}}
    events = digest_module.diff_models(previous, current)
    assert len(events) == 1
    assert events[0]["event_type"] == "new_model"
    assert events[0]["model_id"] == "openai/gpt-4o"


def test_detect_price_drop():
    prev = {"openai/gpt-4o": {"id": "openai/gpt-4o", "name": "GPT-4o",
                               "prompt_price": 0.000005, "completion_price": 0.000015,
                               "context_length": 128000}}
    curr = {"openai/gpt-4o": {"id": "openai/gpt-4o", "name": "GPT-4o",
                               "prompt_price": 0.0000025, "completion_price": 0.000010,
                               "context_length": 128000}}
    events = digest_module.diff_models(prev, curr)
    assert len(events) == 1
    assert events[0]["event_type"] == "price_drop"


def test_detect_price_increase():
    prev = {"qwen/qwen3-235b": {"id": "qwen/qwen3-235b", "name": "Qwen3 235B",
                                 "prompt_price": 0.00005, "completion_price": 0.0001,
                                 "context_length": 32768}}
    curr = {"qwen/qwen3-235b": {"id": "qwen/qwen3-235b", "name": "Qwen3 235B",
                                 "prompt_price": 0.0001, "completion_price": 0.0002,
                                 "context_length": 32768}}
    events = digest_module.diff_models(prev, curr)
    assert len(events) == 1
    assert events[0]["event_type"] == "price_increase"


def test_no_change_produces_no_events():
    snap = {"openai/gpt-4o": {"id": "openai/gpt-4o", "name": "GPT-4o",
                               "prompt_price": 0.0000025, "completion_price": 0.000010,
                               "context_length": 128000}}
    events = digest_module.diff_models(snap, snap)
    assert events == []


def test_get_model_digest_section_returns_string():
    with patch.object(digest_module, "_load_recent_events", return_value=[
        {"event_type": "new_model", "model_id": "fake/model", "details": "New model added"},
        {"event_type": "price_drop", "model_id": "openai/gpt-4o", "details": "Prompt: $5 → $2.50/M"},
    ]):
        section = digest_module.get_model_digest_section()
    assert "Model News" in section or "model" in section.lower()
    assert len(section) > 0


def test_get_model_digest_section_empty_when_no_events():
    with patch.object(digest_module, "_load_recent_events", return_value=[]):
        section = digest_module.get_model_digest_section()
    assert section == ""
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/jacobbrizinski/Projects/kitty
venv/bin/pytest tests/test_model_digest.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'gateway.model_digest'`

- [ ] **Step 3: Create gateway/model_digest.py**

```python
# gateway/model_digest.py
"""AI Model Digest — fetch OpenRouter catalog, diff, store, summarize."""
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger("kitty.model_digest")

DB_PATH = Path("/Users/jacobbrizinski/Projects/kitty/data/model_digest.db")
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
PRICE_CHANGE_THRESHOLD = 0.10  # 10% change triggers an event


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS model_snapshots (
            id TEXT PRIMARY KEY,
            name TEXT,
            prompt_price REAL,
            completion_price REAL,
            context_length INTEGER,
            last_seen TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS digest_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            logged_at TEXT,
            event_type TEXT,
            model_id TEXT,
            details TEXT
        )
    """)
    conn.commit()
    return conn


def _parse_model(raw: dict) -> dict:
    pricing = raw.get("pricing", {})
    return {
        "id": raw["id"],
        "name": raw.get("name", raw["id"]),
        "prompt_price": float(pricing.get("prompt", 0) or 0),
        "completion_price": float(pricing.get("completion", 0) or 0),
        "context_length": int(raw.get("context_length", 0) or 0),
    }


def fetch_models() -> list[dict]:
    """Fetch current model catalog from OpenRouter."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = requests.get(OPENROUTER_MODELS_URL, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json().get("data", [])


def _load_snapshot() -> dict[str, dict]:
    """Load the last known model state from SQLite."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM model_snapshots").fetchall()
    conn.close()
    return {r["id"]: dict(r) for r in rows}


def _save_snapshot(models: dict[str, dict]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    for m in models.values():
        conn.execute("""
            INSERT INTO model_snapshots (id, name, prompt_price, completion_price, context_length, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                prompt_price=excluded.prompt_price,
                completion_price=excluded.completion_price,
                context_length=excluded.context_length,
                last_seen=excluded.last_seen
        """, (m["id"], m["name"], m["prompt_price"], m["completion_price"], m["context_length"], now))
    conn.commit()
    conn.close()


def _save_events(events: list[dict]) -> None:
    if not events:
        return
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    conn.executemany(
        "INSERT INTO digest_log (logged_at, event_type, model_id, details) VALUES (?, ?, ?, ?)",
        [(now, e["event_type"], e["model_id"], e["details"]) for e in events],
    )
    conn.commit()
    conn.close()


def diff_models(previous: dict[str, dict], current: dict[str, dict]) -> list[dict]:
    """Compare two model snapshots. Returns list of change events."""
    events = []

    for model_id, curr in current.items():
        if model_id not in previous:
            events.append({
                "event_type": "new_model",
                "model_id": model_id,
                "details": f"New model: {curr['name']}",
            })
            continue

        prev = previous[model_id]
        for price_key, label in [("prompt_price", "Prompt"), ("completion_price", "Completion")]:
            old_price = prev.get(price_key, 0) or 0
            new_price = curr.get(price_key, 0) or 0
            if old_price == 0:
                continue
            change = (new_price - old_price) / old_price
            if change < -PRICE_CHANGE_THRESHOLD:
                per_m_old = round(old_price * 1_000_000, 4)
                per_m_new = round(new_price * 1_000_000, 4)
                events.append({
                    "event_type": "price_drop",
                    "model_id": model_id,
                    "details": f"{curr['name']} {label}: ${per_m_old} → ${per_m_new}/M ({round(change*100)}%)",
                })
            elif change > PRICE_CHANGE_THRESHOLD:
                per_m_old = round(old_price * 1_000_000, 4)
                per_m_new = round(new_price * 1_000_000, 4)
                events.append({
                    "event_type": "price_increase",
                    "model_id": model_id,
                    "details": f"{curr['name']} {label}: ${per_m_old} → ${per_m_new}/M (+{round(change*100)}%)",
                })

    return events


def run_digest() -> list[dict]:
    """Fetch, diff, save. Returns detected events. Called by launchd daily."""
    try:
        raw_models = fetch_models()
        current = {m["id"]: _parse_model(m) for m in raw_models}
        previous = _load_snapshot()
        events = diff_models(previous, current)
        _save_snapshot(current)
        _save_events(events)
        logger.info("Model digest: %d models, %d events", len(current), len(events))
        return events
    except Exception as e:
        logger.error("Model digest failed: %s", e)
        return []


def _load_recent_events(limit: int = 10) -> list[dict]:
    """Load the most recent digest events from SQLite."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM digest_log ORDER BY logged_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_model_digest_section(limit: int = 3) -> str:
    """Returns a brief text block of recent model changes for the morning brief."""
    events = _load_recent_events(limit=limit)
    if not events:
        return ""
    lines = ["## Model News"]
    for e in events:
        icon = {"new_model": "✦", "price_drop": "↓", "price_increase": "↑"}.get(e["event_type"], "•")
        lines.append(f"- {icon} {e['details']}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
venv/bin/pytest tests/test_model_digest.py -v
```
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add gateway/model_digest.py tests/test_model_digest.py
git commit -m "feat: Phase 16 — model digest fetch/diff/store"
```

---

### Task 2: Wire into morning brief

**Files:**
- Modify: `gateway/brief.py`

`generate_brief()` is at line 116. It builds a `BriefItem`, calls `.model_dump()`, and returns the dict.

- [ ] **Step 1: Add model_digest import to gateway/brief.py**

At line 1, after `import feedparser`, add:

```python
from gateway.model_digest import get_model_digest_section
```

- [ ] **Step 2: Extend generate_brief() to include model_news**

The current `generate_brief()` ends with:

```python
    item = BriefItem(
        date=today,
        headlines=headlines,
        memory_snippet=memory[:500] if memory else "",
        intention=brief_text,
    )
    return item.model_dump(mode="json")
```

Replace the return statement with:

```python
    item = BriefItem(
        date=today,
        headlines=headlines,
        memory_snippet=memory[:500] if memory else "",
        intention=brief_text,
    )
    result = item.model_dump(mode="json")
    model_news = get_model_digest_section(limit=3)
    if model_news:
        result["model_news"] = model_news
    return result
```

- [ ] **Step 3: Verify brief tests still pass**

```bash
venv/bin/pytest tests/ -k "brief" -v
```
Expected: all brief tests pass (no regressions)

- [ ] **Step 4: Commit**

```bash
git add gateway/brief.py
git commit -m "feat: Phase 16 — inject model news into morning brief"
```

---

### Task 3: launchd plist for daily digest

**Files:**
- Create: `kitty_gateway/com.kitty.model-digest.plist`

- [ ] **Step 1: Write the plist**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.kitty.model-digest</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/jacobbrizinski/Projects/kitty/venv/bin/python</string>
        <string>-c</string>
        <string>import sys; sys.path.insert(0, '/Users/jacobbrizinski/Projects/kitty'); from gateway.model_digest import run_digest; events = run_digest(); print(f'Digest complete: {len(events)} events')</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>55</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/jacobbrizinski/Projects/kitty</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/jacobbrizinski/Projects/kitty/logs/model_digest.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/jacobbrizinski/Projects/kitty/logs/model_digest.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

- [ ] **Step 2: Validate plist syntax**

```bash
plutil /Users/jacobbrizinski/Projects/kitty/kitty_gateway/com.kitty.model-digest.plist
```
Expected: `/path/to/file.plist: OK`

- [ ] **Step 3: Document how to install**

To activate the daily digest job:

```bash
cp /Users/jacobbrizinski/Projects/kitty/kitty_gateway/com.kitty.model-digest.plist \
   ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.kitty.model-digest.plist
# Verify it's loaded:
launchctl list | grep kitty.model-digest
```

- [ ] **Step 4: Run a manual digest to verify end-to-end**

```bash
cd /Users/jacobbrizinski/Projects/kitty
set -a && source .env && set +a
venv/bin/python -c "
from gateway.model_digest import run_digest, get_model_digest_section
events = run_digest()
print(f'Events detected: {len(events)}')
print(get_model_digest_section())
"
```
Expected: prints event count (likely 200+ "new_model" events on first run since no snapshot exists yet) and a "Model News" section.

- [ ] **Step 5: Commit**

```bash
git add kitty_gateway/com.kitty.model-digest.plist
git commit -m "feat: Phase 16 — launchd plist for daily model digest at 6:55am"
```

---

### Task 4: Gate check

**Files:**
- Modify: `scripts/setup/gate-check.sh`

- [ ] **Step 1: Add Phase 16 gate**

Add this block before the final `echo "Results..."` line:

```bash
if [ "$PHASE" = "16" ]; then
    echo "[ AI Model Digest ]"
    check "gateway/model_digest.py exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/gateway/model_digest.py"
    check "model digest tests pass" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/test_model_digest.py -q --tb=no 2>/dev/null | grep -q 'passed'"
    check "model_digest imported in brief.py" \
        "grep -q 'model_digest' /Users/jacobbrizinski/Projects/kitty/gateway/brief.py"
    check "launchd plist exists" \
        "test -f /Users/jacobbrizinski/Projects/kitty/kitty_gateway/com.kitty.model-digest.plist"
    check "data/model_digest.db created after run" \
        "cd /Users/jacobbrizinski/Projects/kitty && set -a && source .env 2>/dev/null && set +a && venv/bin/python -c 'from gateway.model_digest import run_digest; run_digest()' && test -f data/model_digest.db"
    check "full test suite passes" \
        "cd /Users/jacobbrizinski/Projects/kitty && venv/bin/pytest tests/ -q --tb=no 2>/dev/null | grep -q 'passed'"
fi
```

- [ ] **Step 2: Run gate check**

```bash
bash /Users/jacobbrizinski/Projects/kitty/scripts/setup/gate-check.sh 16
```
Expected: Phase 16 COMPLETE ✓

- [ ] **Step 3: Commit**

```bash
git add scripts/setup/gate-check.sh
git commit -m "feat: Phase 16 complete — gate check added"
```
