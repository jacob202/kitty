#!/usr/bin/env python3
"""Extract token/cost/elapsed measurements from OpenCode sessions.

Two modes:

  --live      (default) Query the live session DB for the current session's
              running totals. Fast, always available at session-end.

  --previous  Export the most recent COMPLETED session. Slower but gives
              exact final measurements. Use at session-start to record the
              previous session's data.

Outputs JSON to stdout with fields:
  session_id, total_tokens, estimated_cost_usd, elapsed_seconds, kb_tokens_loaded
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OPENCODE_DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"


def measure_live(db_path: Path = OPENCODE_DB) -> dict | None:
    """Query the live session DB for the current project's running session."""
    if not db_path.exists():
        return None

    conn = None
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT id, cost, tokens_input, tokens_output, tokens_reasoning,
                   tokens_cache_read, time_created, time_updated
            FROM session
            WHERE directory = ? AND time_archived IS NULL
            ORDER BY time_updated DESC
            LIMIT 1
            """,
            (str(REPO_ROOT),),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

    if row is None:
        return None

    total_tokens = (
        (row["tokens_input"] or 0)
        + (row["tokens_output"] or 0)
        + (row["tokens_reasoning"] or 0)
    ) or None

    elapsed = None
    created = row["time_created"]
    updated = row["time_updated"]
    if created and updated:
        elapsed = max(0, int((updated - created) / 1000))

    return {
        "source": "opencode_live_db",
        "session_id": row["id"],
        "total_tokens": total_tokens,
        "estimated_cost_usd": (
            round(float(row["cost"]), 6) if row["cost"] is not None else None
        ),
        "elapsed_seconds": elapsed,
        "kb_tokens_loaded": row["tokens_cache_read"] or None,
    }


def find_latest_kitty_session() -> dict | None:
    result = subprocess.run(
        ["opencode", "session", "list", "--format", "json", "--max-count", "20"],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        return None
    try:
        sessions = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    kitty_dir = str(REPO_ROOT)
    for session in sessions:
        if session.get("directory") == kitty_dir:
            return session
    return None


def export_session(session_id: str) -> dict | None:
    tmp = Path(tempfile.mkstemp(suffix=".json", prefix="opencode-export-")[1])
    try:
        result = subprocess.run(
            ["opencode", "export", session_id],
            stdout=open(str(tmp), "w"),
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
            cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            return None
        return json.loads(tmp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def extract_previous(export_data: dict) -> dict:
    info = export_data.get("info", {})
    tokens = info.get("tokens", {})
    tinfo = info.get("time", {})
    created = tinfo.get("created")
    updated = tinfo.get("updated")

    total_tokens = (
        tokens.get("input", 0)
        + tokens.get("output", 0)
        + tokens.get("reasoning", 0)
    ) or None

    elapsed = None
    if created and updated:
        elapsed = max(0, int((updated - created) / 1000))

    return {
        "source": "opencode_export",
        "session_id": info.get("id"),
        "total_tokens": total_tokens if total_tokens else None,
        "estimated_cost_usd": (
            round(float(info["cost"]), 6) if info.get("cost") is not None else None
        ),
        "elapsed_seconds": elapsed,
        "kb_tokens_loaded": tokens.get("cache", {}).get("read") or None,
    }


def unavailable(reason: str) -> dict:
    return {
        "source": "unavailable",
        "reason": reason,
        "total_tokens": None,
        "estimated_cost_usd": None,
        "elapsed_seconds": None,
        "kb_tokens_loaded": None,
    }


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--live"

    if mode == "--previous":
        session = find_latest_kitty_session()
        if session is None:
            json.dump(unavailable("no completed Kitty sessions found"), sys.stdout, indent=2)
            return 0
        export_data = export_session(session["id"])
        if export_data is None:
            json.dump(unavailable(f"export failed for {session['id']}"), sys.stdout, indent=2)
            return 0
        json.dump(extract_previous(export_data), sys.stdout, indent=2)
    else:
        measurements = measure_live()
        if measurements is None:
            json.dump(
                unavailable("no live session found in OpenCode DB"),
                sys.stdout,
                indent=2,
            )
            return 0
        json.dump(measurements, sys.stdout, indent=2)

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())