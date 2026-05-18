#!/usr/bin/env python3
"""Convert and stage chat history exports for Kitty ingestion.

Sources handled:
  --chatgpt   <dir>    ChatGPT export folder (contains conversations.json)
  --claude    <zip>    Anthropic data export zip (contains conversations.json)
  --sessions  <zip>+  Claude.ai web session export zips (contain .jsonl files)
  --imessage           Read iMessage from ~/Library/Messages/chat.db (optional)

Output: staged .txt files in data/imports/<source>/ ready for ingest.py

Usage:
    python scripts/ingest_chat_history.py --chatgpt <dir> --claude <zip> --sessions <zip> [<zip> ...]
    python scripts/ingest_chat_history.py --all   # uses default paths
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICLOUD_DL = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Downloads"
CHATGPT_EXPORT_DIR = ICLOUD_DL / "data-f19e223a-7158-45b7-a76a-22c3d47efd74-1778341796-2a59119f-batch-0000"
CLAUDE_EXPORT_ZIP = ICLOUD_DL / "11eebf96d2b5f3eac0ba69a9df4a47b32c193f0e1a0634567975211dac6ba55b-2026-05-02-17-42-21-1559dbc68af54a92855af6e62fd0c3b4.zip"
SESSION_ZIPS = [
    Path.home() / "Downloads/session-export-1778674457606.zip",
    Path.home() / "Downloads/session-export-1778674471460.zip",
]

OUT_CHATGPT   = ROOT / "data/imports/chatgpt"
OUT_CLAUDE    = ROOT / "data/imports/claude_export"
OUT_SESSIONS  = ROOT / "data/imports/claude_sessions"

MIN_CHARS = 100  # skip very short conversations


def safe_filename(title: str, uid: str, idx: int) -> str:
    slug = re.sub(r"[^\w\s-]", "", (title or "untitled")).strip()
    slug = re.sub(r"[\s]+", "_", slug)[:60]
    return f"{idx:04d}_{slug or uid[:8]}.txt"


# ---------------------------------------------------------------------------
# ChatGPT export
# ---------------------------------------------------------------------------

def extract_chatgpt_text(msg: dict) -> str:
    """Pull text from a ChatGPT message regardless of content shape."""
    # Prefer top-level text field
    if msg.get("text") and isinstance(msg["text"], str) and msg["text"].strip():
        return msg["text"].strip()
    # Fall back to content parts list
    parts = msg.get("content") or []
    if isinstance(parts, list):
        texts = []
        for p in parts:
            if isinstance(p, dict) and p.get("type") == "text":
                texts.append((p.get("text") or "").strip())
        return "\n".join(t for t in texts if t)
    if isinstance(parts, str):
        return parts.strip()
    return ""


def convert_chatgpt(src_dir: Path, out_dir: Path) -> int:
    conv_file = src_dir / "conversations.json"
    if not conv_file.is_file():
        print(f"[chatgpt] conversations.json not found in {src_dir}")
        return 0

    data = json.loads(conv_file.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("[chatgpt] unexpected format — not a list")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0

    for idx, convo in enumerate(data):
        title = (convo.get("name") or "").strip()
        uid = convo.get("uuid", "") or str(idx)
        messages = convo.get("chat_messages") or []
        if not messages:
            continue

        lines = [f"# {title or 'Untitled'}", f"Source: ChatGPT", ""]
        created = convo.get("created_at") or convo.get("updated_at") or ""
        if created:
            lines.append(f"Date: {created[:10]}")
            lines.append("")

        for msg in messages:
            sender = msg.get("sender") or "unknown"
            role = "Jacob" if sender == "human" else "ChatGPT"
            text = extract_chatgpt_text(msg)
            if not text:
                continue
            lines.append(f"[{role}]")
            lines.append(text)
            lines.append("")

        body = "\n".join(lines).strip()
        if len(body) < MIN_CHARS:
            continue

        fname = safe_filename(title, uid, idx)
        (out_dir / fname).write_text(body, encoding="utf-8")
        written += 1

    print(f"[chatgpt] wrote {written} conversations → {out_dir}")
    return written


# ---------------------------------------------------------------------------
# Anthropic / Claude.ai export zip
# ---------------------------------------------------------------------------

def extract_mapping_pairs(mapping: dict, current_node: str | None = None) -> list[tuple[str, str]]:
    """Walk a ChatGPT/Anthropic mapping tree → [(role, text), ...].

    Handles two formats:
      - ChatGPT: message.author.role + message.content.parts (list of str or dict)
      - Anthropic: message.role + message.content (str or list of text-part dicts)
    """
    if not mapping:
        return []

    # Walk from current_node back to root via parent links, then reverse
    if current_node and current_node in mapping:
        path: list[str] = []
        nid: str | None = current_node
        while nid and nid in mapping:
            path.append(nid)
            nid = mapping[nid].get("parent")
        order = list(reversed(path))
    else:
        # Fallback: topological walk via children
        children: dict[str | None, list] = {}
        for nid, node in mapping.items():
            parent = node.get("parent")
            children.setdefault(parent, []).append(nid)
        order: list[str] = []

        def walk(nid: str | None) -> None:
            if nid is not None:
                order.append(nid)
            for child in children.get(nid, []):
                walk(child)
        walk(None)

    pairs: list[tuple[str, str]] = []
    for nid in order:
        node = mapping.get(nid) or {}
        msg = node.get("message") or {}
        if not msg:
            continue

        # ChatGPT format: author.role
        author = msg.get("author") or {}
        role = author.get("role") or msg.get("role") or ""
        if role in ("system", "tool", ""):
            continue

        # ChatGPT format: content.parts (list of str or dict)
        content_obj = msg.get("content") or {}
        if isinstance(content_obj, dict):
            parts = content_obj.get("parts") or []
            texts = []
            for p in parts:
                if isinstance(p, str) and p.strip():
                    texts.append(p.strip())
                elif isinstance(p, dict):
                    t = p.get("text") or ""
                    if t.strip():
                        texts.append(t.strip())
            text = "\n".join(texts)
        elif isinstance(content_obj, str):
            text = content_obj.strip()
        elif isinstance(content_obj, list):
            # Anthropic format: list of {type, text} dicts
            text = "\n".join(
                (p.get("text") or "") for p in content_obj
                if isinstance(p, dict) and p.get("type") == "text"
            ).strip()
        else:
            text = ""

        if text:
            pairs.append((role, text))
    return pairs


def extract_claude_text_from_mapping(mapping: dict) -> list[tuple[str, str]]:
    return extract_mapping_pairs(mapping)


def extract_claude_text_chat_messages(messages: list) -> list[tuple[str, str]]:
    """Handle the chat_messages format (same as ChatGPT export variant)."""
    pairs = []
    for msg in messages:
        sender = msg.get("sender") or msg.get("role") or "unknown"
        role = "Jacob" if sender == "human" else "Claude"
        text = extract_chatgpt_text(msg)  # same field layout
        if text:
            pairs.append((role, text))
    return pairs


def extract_content_text(content) -> str:
    """Extract plain text from Claude/Anthropic content (str or list of parts)."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        texts = []
        for p in content:
            if not isinstance(p, dict):
                continue
            ptype = p.get("type", "")
            if ptype == "text":
                t = (p.get("text") or "").strip()
                if t:
                    texts.append(t)
            # skip: thinking, tool_use, tool_result, image, etc.
        return "\n".join(texts)
    return ""


def convert_claude_export(zip_path: Path, out_dir: Path) -> int:
    if not zip_path.is_file():
        print(f"[claude] zip not found: {zip_path}")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    global_idx = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        # Anthropic splits across conversations-000.json, conversations-001.json, etc.
        conv_files = sorted(n for n in names if re.match(r"conversations-\d+\.json$", n))
        if not conv_files:
            # fallback: single conversations.json
            single = next((n for n in names if n.endswith("conversations.json")), None)
            conv_files = [single] if single else []

        if not conv_files:
            print(f"[claude] no conversation JSON files inside {zip_path.name}")
            return 0

        for conv_file in conv_files:
            data = json.loads(zf.read(conv_file).decode("utf-8"))
            if not isinstance(data, list):
                continue

            for convo in data:
                global_idx += 1
                title = (convo.get("name") or convo.get("title") or "").strip()
                uid = convo.get("uuid") or convo.get("id") or convo.get("conversation_id") or str(global_idx)
                current_node = convo.get("current_node")

                mapping = convo.get("mapping") or {}
                if mapping:
                    pairs = extract_mapping_pairs(mapping, current_node)
                else:
                    pairs = extract_claude_text_chat_messages(convo.get("chat_messages") or [])

                if not pairs:
                    continue

                # create_time is a Unix float in ChatGPT exports
                created = convo.get("created_at") or ""
                if not created and convo.get("create_time"):
                    try:
                        ts = float(convo["create_time"])
                        created = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                    except Exception:
                        pass

                source_label = "ChatGPT" if convo.get("default_model_slug") or convo.get("gizmo_type") else "Claude.ai"
                lines = [f"# {title or 'Untitled'}", f"Source: {source_label}", ""]
                if created:
                    lines.append(f"Date: {created[:10]}")
                    lines.append("")

                for role, text in pairs:
                    if role in ("user", "human"):
                        label = "Jacob"
                    else:
                        label = source_label
                    lines.append(f"[{label}]")
                    lines.append(text)
                    lines.append("")

                body = "\n".join(lines).strip()
                if len(body) < MIN_CHARS:
                    continue

                fname = safe_filename(title, uid, global_idx)
                (out_dir / fname).write_text(body, encoding="utf-8")
                written += 1

    print(f"[claude] wrote {written} conversations → {out_dir}")
    return written


# ---------------------------------------------------------------------------
# Claude.ai web session exports (.jsonl inside zip)
# ---------------------------------------------------------------------------

def convert_sessions(zip_paths: list[Path], out_dir: Path) -> int:
    """Convert Claude Code session export .jsonl files to readable text.

    Format: each line is a JSON object with:
      type = "user"      → message.content = str or list of parts
      type = "assistant" → message.content = list of parts (text, thinking, tool_use, ...)
    We extract only real text (skip tool calls, tool results, thinking blocks).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    seen: set[str] = set()

    for zip_path in zip_paths:
        if not zip_path.is_file():
            print(f"[sessions] zip not found: {zip_path}")
            continue

        with zipfile.ZipFile(zip_path, "r") as zf:
            jsonl_names = [n for n in zf.namelist() if n.endswith(".jsonl")]
            for jname in jsonl_names:
                # Deduplicate: same session may appear in multiple export zips
                sig = jname.split("/")[-1]
                if sig in seen:
                    continue
                seen.add(sig)

                raw = zf.read(jname).decode("utf-8", errors="replace")
                lines_raw = [l.strip() for l in raw.splitlines() if l.strip()]

                pairs: list[tuple[str, str]] = []
                created = ""

                for line in lines_raw:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    etype = event.get("type", "")
                    if etype not in ("user", "assistant"):
                        if not created and event.get("timestamp"):
                            created = event["timestamp"][:10]
                        continue

                    msg = event.get("message") or {}
                    role = msg.get("role") or etype
                    content = msg.get("content") or ""

                    if not created and event.get("timestamp"):
                        created = event["timestamp"][:10]

                    # User messages: skip tool_result turns (internal plumbing)
                    if role == "user":
                        if isinstance(content, list):
                            # If all parts are tool_result, skip this event
                            if all(isinstance(p, dict) and p.get("type") == "tool_result" for p in content):
                                continue
                            text = "\n".join(
                                (p.get("text") or "") for p in content
                                if isinstance(p, dict) and p.get("type") == "text"
                            ).strip()
                        else:
                            text = str(content).strip()
                        if text:
                            pairs.append(("Jacob", text))

                    # Assistant messages: extract only text parts
                    elif role == "assistant":
                        text = extract_content_text(content)
                        if text:
                            pairs.append(("Claude", text))

                if not pairs:
                    continue

                stem = Path(jname).stem[:40]
                out_lines = [f"# Claude Code Session: {stem}", "Source: Claude Code session", ""]
                if created:
                    out_lines.append(f"Date: {created}")
                    out_lines.append("")
                for role, text in pairs:
                    out_lines.append(f"[{role}]")
                    out_lines.append(text)
                    out_lines.append("")

                body = "\n".join(out_lines).strip()
                if len(body) < MIN_CHARS:
                    continue

                fname = f"{stem}.txt"
                (out_dir / fname).write_text(body, encoding="utf-8")
                written += 1

    print(f"[sessions] wrote {written} session files → {out_dir}")
    return written


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Stage chat history exports for Kitty ingestion")
    parser.add_argument("--chatgpt", type=Path, default=CHATGPT_EXPORT_DIR, metavar="DIR")
    parser.add_argument("--claude", type=Path, default=CLAUDE_EXPORT_ZIP, metavar="ZIP")
    parser.add_argument("--sessions", type=Path, nargs="+", default=SESSION_ZIPS, metavar="ZIP")
    parser.add_argument("--all", dest="do_all", action="store_true", help="Run all sources with defaults")
    parser.add_argument("--skip-chatgpt", action="store_true")
    parser.add_argument("--skip-claude", action="store_true")
    parser.add_argument("--skip-sessions", action="store_true")
    args = parser.parse_args()

    total = 0

    if not args.skip_chatgpt:
        total += convert_chatgpt(args.chatgpt, OUT_CHATGPT)

    if not args.skip_claude:
        total += convert_claude_export(args.claude, OUT_CLAUDE)

    if not args.skip_sessions:
        total += convert_sessions(args.sessions, OUT_SESSIONS)

    print(f"\nTotal files staged: {total}")
    print("\nNext step — ingest into Kitty knowledge base:")
    print(f"  python scripts/ingest.py {OUT_CHATGPT} --sensitivity low")
    print(f"  python scripts/ingest.py {OUT_CLAUDE} --sensitivity low")
    print(f"  python scripts/ingest.py {OUT_SESSIONS} --sensitivity low")


if __name__ == "__main__":
    main()
