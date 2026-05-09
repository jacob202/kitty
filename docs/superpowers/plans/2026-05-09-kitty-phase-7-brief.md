# Phase 7 — Morning Brief & Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the "Morning Brief" — a 7am summary of calendar, news, and project status delivered to Jacob's phone via Pushover and available in the Kitty WebUI.

**Architecture:** 
1. `gateway/brief.py` handles the logic of gathering data and generating the brief text.
2. `gateway/notify.py` handles sending push notifications via Pushover.
3. `scripts/brief.py` is the CLI entry point.
4. `n8n` or `launchd` triggers the script at 7am daily.

**Tech Stack:** Python 3.12, Pushover API, RSS (feedparser), Google Calendar (via `gcsa` or `google-api-python-client`), n8n (for scheduling).

---

## File Map

| File | Change |
|---|---|
| `contracts/brief_item.py` | (Exists) Defines the structure of a brief item |
| `gateway/brief.py` | New — logic to gather news, calendar, and project status |
| `gateway/notify.py` | New — Pushover notification wrapper |
| `gateway/app.py` | Add `/api/brief` endpoint |
| `scripts/brief.py` | New — CLI to trigger the brief |
| `tests/test_brief.py` | New — unit tests for brief generation |
| `.env` | Add `PUSHOVER_USER_KEY`, `PUSHOVER_API_TOKEN` |

---

## Task 1: Environment Setup

- [ ] **Step 1: Add Pushover keys to `.env`**
```bash
# Add these to /Users/jacobbrizinski/Projects/kitty/.env
PUSHOVER_USER_KEY=your_user_key
PUSHOVER_API_TOKEN=your_app_token
```

- [ ] **Step 2: Install dependencies**
```bash
./venv/bin/pip install feedparser gcsa
```

---

## Task 2: Implement Notification Wrapper

**Files:**
- Create: `gateway/notify.py`

- [ ] **Step 1: Create `send_pushover` function**
```python
import os
import requests
from typing import Optional

def send_pushover(message: str, title: str = "Kitty Brief", url: Optional[str] = None):
    user_key = os.environ.get("PUSHOVER_USER_KEY")
    api_token = os.environ.get("PUSHOVER_API_TOKEN")
    if not user_key or not api_token:
        print("Pushover keys not found in environment.")
        return False
    
    data = {
        "token": api_token,
        "user": user_key,
        "message": message,
        "title": title
    }
    if url:
        data["url"] = url
        data["url_title"] = "Open Kitty WebUI"
        
    resp = requests.post("https://api.pushover.net/1/messages.json", data=data)
    return resp.status_code == 200
```

---

## Task 3: Implement Brief Generation

**Files:**
- Create: `gateway/brief.py`

- [ ] **Step 1: Implement `generate_brief` logic**
- Gather RSS feed items (TechCrunch, etc.)
- Gather Calendar events for today
- Fetch "Next Smallest Action" from `TASKS.md`
- Use LLM to summarize into a 90-second read.

---

## Task 4: Add API Endpoint

**Files:**
- Modify: `gateway/app.py`

- [ ] **Step 1: Add `/api/brief` route**
```python
@app.get("/api/brief")
async def get_brief():
    # Call generate_brief()
    # Return JSON
```

---

## Task 5: Scheduling

- [ ] **Step 1: Create `scripts/brief.py`**
- [ ] **Step 2: Setup `launchd` or `n8n` workflow**
- Trigger daily at 07:00.

---

## Verification

Gate command: `bash scripts/setup/gate-check.sh 7`
Tests: `venv/bin/pytest tests/test_brief.py`
Manual test: `python scripts/brief.py --notify`
