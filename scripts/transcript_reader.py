#!/usr/bin/env python3
"""Read-only cross-tool transcript reader.

Claude Code: ~/.claude/projects/<project-dir>/*.jsonl
Codex:       ~/.codex/sessions/**/*.jsonl
opencode:    ~/.local/share/opencode/opencode.db

Usage:
    python3 scripts/transcript_reader.py --project kitty --last 20
    python3 scripts/transcript_reader.py --project /Users/jacobbrizinski/Projects/kitty --last 10
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()


def project_dir(project: str) -> Path:
    """Map a project path or name to the Claude Code project directory name."""
    path = Path(project).expanduser().resolve()
    escaped = str(path).replace("/", "-")
    return HOME / ".claude" / "projects" / escaped


def extract_claude_turns(project_path: str, last_n: int):
    """Yield (timestamp, role, text) from Claude Code jsonl transcripts."""
    pdir = project_dir(project_path)
    files = sorted(pdir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    turns = []
    for f in files:
        with open(f, "r", encoding="utf-8", errors="ignore") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = obj.get("timestamp", "")
                msg = obj.get("message") or {}
                role = msg.get("role") or obj.get("role")
                content = msg.get("content") or obj.get("content")
                text = _flatten_content(content)
                if role in ("user", "assistant") and text:
                    turns.append((ts, role, text))
                    if len(turns) >= last_n:
                        break
        if len(turns) >= last_n:
            break
    return turns[:last_n]


def extract_codex_turns(project_path: str, last_n: int):
    """Yield (timestamp, role, text) from Codex jsonl transcripts."""
    base = HOME / ".codex" / "sessions"
    files = sorted(base.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    turns = []
    target = str(Path(project_path).expanduser().resolve())
    for f in files:
        with open(f, "r", encoding="utf-8", errors="ignore") as fp:
            raw = fp.read()
            # Codex sessions aren't organized by project dir the way Claude's
            # are; skip any session that never references the target path.
            if target not in raw:
                continue
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "response_item":
                    continue
                payload = obj.get("payload", {})
                if payload.get("type") != "message":
                    continue
                role = payload.get("role")
                if role not in ("user", "assistant"):
                    continue
                text = _flatten_content(payload.get("content"))
                if text:
                    turns.append((obj.get("timestamp", ""), role, text))
                    if len(turns) >= last_n:
                        break
        if len(turns) >= last_n:
            break
    return turns[:last_n]


def extract_opencode_turns(project_path: str, last_n: int):
    """Yield (timestamp, role, text) from opencode SQLite db."""
    db_path = HOME / ".local" / "share" / "opencode" / "opencode.db"
    if not db_path.exists():
        return []
    target = str(Path(project_path).expanduser().resolve())
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # Find sessions whose directory matches the target project
    cur.execute(
        "SELECT id FROM session WHERE directory = ? ORDER BY time_updated DESC LIMIT ?",
        (target, last_n * 2),
    )
    session_ids = [r["id"] for r in cur.fetchall()]
    turns = []
    for sid in session_ids:
        cur.execute(
            """
            SELECT m.id, m.data, p.data as part_data
            FROM message m
            LEFT JOIN part p ON p.message_id = m.id
            WHERE m.session_id = ? AND (m.data LIKE '%"role":"user"%' OR m.data LIKE '%"role":"assistant"%')
            ORDER BY m.time_created ASC
            """,
            (sid,),
        )
        for row in cur.fetchall():
            msg = json.loads(row["data"])
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            text = ""
            if row["part_data"]:
                part = json.loads(row["part_data"])
                text = part.get("text", "")
            if text:
                created = msg.get("time", {}).get("created", 0)
                ts = (
                    datetime.fromtimestamp(created / 1000, tz=timezone.utc).isoformat()
                    if created
                    else ""
                )
                turns.append((ts, role, text))
                if len(turns) >= last_n:
                    break
        if len(turns) >= last_n:
            break
    conn.close()
    return turns[:last_n]


def _flatten_content(content):
    """Extract plain text from Claude/Codex content blobs."""
    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, str):
                texts.append(block)
            elif isinstance(block, dict):
                if block.get("type") in ("text", "input_text", "output_text"):
                    texts.append(block.get("text", ""))
                elif block.get("type") == "tool_result" and "content" in block:
                    texts.append(_flatten_content(block["content"]))
                elif block.get("type") == "tool_use":
                    texts.append(f"[tool_use: {block.get('name', '')}]")
        return " ".join(t for t in texts if t)
    return ""


def format_turns(turns, source):
    lines = [f"\n=== {source} ==="]
    for ts, role, text in turns:
        preview = text.replace("\n", " ")[:300]
        lines.append(f"[{ts}] {role}: {preview}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Cross-tool transcript reader")
    parser.add_argument(
        "--project", default="/Users/jacobbrizinski/Projects/kitty", help="Project path or name"
    )
    parser.add_argument("--last", type=int, default=10, help="Number of recent turns per tool")
    args = parser.parse_args()

    print(f"Project: {args.project}")
    print(format_turns(extract_claude_turns(args.project, args.last), "Claude Code"))
    print(format_turns(extract_codex_turns(args.project, args.last), "Codex"))
    print(format_turns(extract_opencode_turns(args.project, args.last), "opencode"))


if __name__ == "__main__":
    main()
