"""Chat export parsers — ingest Claude.ai and ChatGPT exports into memory.

Public API:
  parse_claude_export(json_path) -> list[dict]    Extract messages from Claude export
  parse_chatgpt_export(json_path) -> list[dict]   Extract messages from ChatGPT export
  ingest_export(path, source_type) -> int          Parse and ingest into memory
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("kitty.chat_import")


def parse_claude_export(json_path: str | Path) -> list[dict]:
    """Parse a Claude.ai conversation export JSON file. Returns list of message dicts."""
    path = Path(json_path)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, Exception) as e:
        logger.error("Failed to parse Claude export: %s", e)
        return []

    messages = []

    # Claude exports are arrays of conversation objects
    conversations = data if isinstance(data, list) else [data]

    for conv in conversations:
        chat_messages = conv.get("chat_messages", [])
        for msg in chat_messages:
            role = msg.get("sender", "")
            text = msg.get("text", "")
            if text.strip():
                # Map Claude roles
                if role == "human":
                    role = "user"
                elif role == "assistant":
                    role = "assistant"
                messages.append({
                    "role": role,
                    "content": text[:2000],
                    "timestamp": msg.get("created_at", ""),
                    "source": "claude_export",
                })

    logger.info("Parsed %d messages from Claude export", len(messages))
    return messages


def parse_chatgpt_export(json_path: str | Path) -> list[dict]:
    """Parse a ChatGPT export JSON file. Returns list of message dicts."""
    path = Path(json_path)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, Exception) as e:
        logger.error("Failed to parse ChatGPT export: %s", e)
        return []

    messages = []

    # ChatGPT exports have a 'conversations' key
    conversations = data if isinstance(data, list) else data.get("conversations", [data])

    for conv in conversations:
        # Handle both "mapping" format and simple "messages" array
        mapping = conv.get("mapping", {})
        if mapping:
            for node_id, node in mapping.items():
                msg = node.get("message")
                if msg:
                    author = msg.get("author", {}).get("role", "")
                    content_parts = msg.get("content", {}).get("parts", [])
                    text = " ".join(str(p) for p in content_parts if isinstance(p, str))
                    if text.strip():
                        role = "user" if author == "user" else "assistant"
                        messages.append({
                            "role": role,
                            "content": text[:2000],
                            "timestamp": msg.get("create_time", ""),
                            "source": "chatgpt_export",
                        })
        else:
            # Simple messages array format
            for msg in conv.get("messages", []):
                role = msg.get("role", "")
                text = msg.get("content", "")
                if text.strip():
                    messages.append({
                        "role": role,
                        "content": text[:2000],
                        "timestamp": msg.get("timestamp", ""),
                        "source": "chatgpt_export",
                    })

    logger.info("Parsed %d messages from ChatGPT export", len(messages))
    return messages


def ingest_export(
    file_path: str | Path,
    source_type: str = "claude",
    limit: int = 500,
) -> int:
    """Parse and ingest a chat export into Kitty's memory. Returns number of facts stored."""
    path = Path(file_path)
    if not path.exists():
        return 0

    if source_type == "claude":
        messages = parse_claude_export(path)
    elif source_type == "chatgpt":
        messages = parse_chatgpt_export(path)
    else:
        logger.warning("Unknown export source type: %s", source_type)
        return 0

    if not messages:
        return 0

    # Ingest into memory as facts
    stored = 0
    try:
        from gateway.memory import add_memory
        for msg in messages[:limit]:
            if msg["role"] == "user":
                text = f"From {source_type} history: {msg['content'][:500]}"
                add_memory(text, namespace="facts", metadata={
                    "source": source_type,
                    "timestamp": msg.get("timestamp", ""),
                })
                stored += 1
    except Exception as e:
        logger.error("Chat import memory ingestion failed: %s", e)

    # Also ingest into knowledge base
    try:
        import tempfile
        text = "\n\n".join(f"[{m['role']}] {m['content']}" for m in messages[:limit])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(text)
            tmp_path = f.name
        from gateway.knowledge import ingest
        asyncio.run(ingest(tmp_path, sensitivity="low", source_label=f"{source_type}_export"))
        Path(tmp_path).unlink(missing_ok=True)
    except Exception as e:
        logger.warning("Chat import knowledge ingestion failed: %s", e)

    logger.info("Ingested %d facts from %s export", stored, source_type)
    return stored
