#!/usr/bin/env python3
import os
import json
import sqlite3
import glob

def read_claude_transcripts(limit=5):
    print("=== Recent Claude Code Activity ===")
    pattern = os.path.expanduser("~/.claude/projects/*/transcript.jsonl")
    for file in sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)[:3]:
        print(f"\nProject: {os.path.basename(os.path.dirname(file))}")
        try:
            with open(file, 'r') as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    data = json.loads(line)
                    role = data.get("role", data.get("type", "unknown"))
                    print(f"[{role}]: {str(data)[:200]}...")
        except Exception as e:
            print(f"Error reading {file}: {e}")

def read_codex_transcripts(limit=5):
    print("\n=== Recent Codex Activity ===")
    pattern = os.path.expanduser("~/.codex/sessions/*.jsonl")
    for file in sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)[:3]:
        print(f"\nSession: {os.path.basename(file)}")
        try:
            with open(file, 'r') as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    data = json.loads(line)
                    print(f"[Turn]: {str(data)[:200]}...")
        except Exception as e:
            print(f"Error reading {file}: {e}")

def read_opencode_transcripts(limit=5):
    print("\n=== Recent Opencode Activity ===")
    db_path = os.path.expanduser("~/.local/share/opencode/opencode.db")
    if not os.path.exists(db_path):
        return
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # Assume a standard schema or simple text search for opencode
        try:
            cur.execute("SELECT timestamp, role, content FROM messages ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            for r in reversed(rows):
                print(f"[{r[1]}]: {str(r[2])[:200]}...")
        except Exception:
            pass
    except Exception as e:
        print(f"Could not read opencode.db: {e}")

if __name__ == "__main__":
    print("Cross-Agent Transcript Visibility (Last 5 turns)")
    read_claude_transcripts()
    read_codex_transcripts()
    read_opencode_transcripts()
