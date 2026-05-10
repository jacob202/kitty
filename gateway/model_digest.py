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

DB_PATH = Path(__file__).parent.parent / "data" / "model_digest.db"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
PRICE_CHANGE_THRESHOLD = 0.10  # 10% change triggers an event


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
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
        # Collect per-field changes, then emit one event per model (largest change wins)
        model_changes = []
        for price_key, label in [("prompt_price", "Prompt"), ("completion_price", "Completion")]:
            old_price = prev.get(price_key, 0) or 0
            new_price = curr.get(price_key, 0) or 0
            if old_price == 0:
                if new_price > 0:
                    events.append({
                        "event_type": "price_increase",
                        "model_id": model_id,
                        "details": f"{curr['name']} {label}: was free → ${round(new_price * 1_000_000, 4)}/M",
                    })
                continue
            change = (new_price - old_price) / old_price
            if abs(change) > PRICE_CHANGE_THRESHOLD:
                model_changes.append((abs(change), change, old_price, new_price, label))

        if model_changes:
            # Pick the field with the largest absolute change as the representative
            model_changes.sort(reverse=True)
            _, change, old_price, new_price, label = model_changes[0]
            per_m_old = round(old_price * 1_000_000, 4)
            per_m_new = round(new_price * 1_000_000, 4)
            if change < 0:
                events.append({
                    "event_type": "price_drop",
                    "model_id": model_id,
                    "details": f"{curr['name']} {label}: ${per_m_old} → ${per_m_new}/M ({round(change*100)}%)",
                })
            else:
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
