"""Chat message search — FTS5-powered keyword search across conversations.

Uses SQLite FTS5 (stdlib, no deps) directly on the kitty.db chat_messages
table via a dedicated FTS virtual table maintained by DB triggers.

Public API:
  search_chat_messages(query, limit=10) -> list[dict]
  rebuild_fts_index() -> int
"""

from __future__ import annotations

import logging
import time
from typing import Any

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE
from gateway.memory_graph import Item, Source, StoreAdapter

logger = logging.getLogger("kitty.chat_search")

_FTS_TABLE = "chat_messages_fts"
DB_FILE = KITTY_DB_FILE


def _ensure_fts_exists() -> None:
    """Apply the migration that creates the FTS5 virtual table. Idempotent."""
    kitty_db.migrate(db_file=DB_FILE)


def rebuild_fts_index() -> int:
    """Rebuild the FTS index from the current chat_messages table.

    This is a full rebuild — it deletes and re-inserts every row.
    Returns the number of messages indexed.
    """
    _ensure_fts_exists()
    with kitty_db.connect(DB_FILE) as conn:
        # Delete all existing FTS rows
        conn.execute(f"DELETE FROM {_FTS_TABLE}")

        # Re-insert all messages with conversation context
        rows = conn.execute(
            """
            SELECT m.id, t.conversation_id, m.content, m.role, m.created_at
            FROM chat_messages m
            JOIN chat_turns t ON t.id = m.turn_id
            """
        ).fetchall()

        count = 0
        for row in rows:
            conn.execute(
                f"INSERT INTO {_FTS_TABLE} (message_id, conversation_id, content, role, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (row["id"], row["conversation_id"], row["content"], row["role"], row["created_at"]),
            )
            count += 1

        conn.commit()

    logger.info("Rebuilt FTS index: %d messages", count)
    return count


def search_chat_messages(
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Full-text keyword search across all chat messages via FTS5.

    Args:
        query: The search string (FTS5 query syntax — supports quoted phrases,
               prefix matching with *, AND/OR/NOT operators).
        limit: Maximum results to return.

    Returns:
        List of result dicts with keys:
          message_id, conversation_id, content, role, created_at,
          chat_title, rank, score
    """
    _ensure_fts_exists()

    with kitty_db.connect(DB_FILE) as conn:
        rows = conn.execute(
            f"""
            SELECT
                f.message_id,
                f.conversation_id,
                f.content,
                f.role,
                f.created_at,
                COALESCE(c.title, '') AS chat_title,
                f.rank
            FROM {_FTS_TABLE} f
            LEFT JOIN chat_conversations c ON c.id = f.conversation_id
            WHERE f MATCH ?
            ORDER BY f.rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        # FTS5 rank is negative for good matches (BM25-like); more negative = better
        rank = row["rank"]
        rank = float(rank) if rank is not None else 0.0
        # Convert to a positive score normalized roughly to [0, 1]
        # rank <= -100 is an excellent match; clamp to avoid division by zero
        score = 1.0 / (1.0 + abs(rank)) if rank != 0 else 0.0

        # Build a snippet: extract ~120 chars around the first match region
        content = row["content"]
        snippet = _make_snippet(content, query)

        results.append({
            "message_id": row["message_id"],
            "conversation_id": row["conversation_id"],
            "content": content,
            "snippet": snippet,
            "role": row["role"],
            "created_at": row["created_at"],
            "chat_title": row["chat_title"],
            "rank": rank,
            "score": score,
        })

    return results


def _make_snippet(text: str, query: str, max_chars: int = 120) -> str:
    """Extract a concise snippet around the first occurrence of query terms."""
    if not text or not query:
        return text[:max_chars] if text else ""

    lower_text = text.lower()
    # Try to find the first query term
    for term in query.split():
        clean = term.strip('"').strip('*').lower()
        if not clean:
            continue
        pos = lower_text.find(clean)
        if pos >= 0:
            start = max(0, pos - 40)
            end = min(len(text), pos + 80)
            snippet = text[start:end]
            if start > 0:
                snippet = "…" + snippet
            if end < len(text):
                snippet = snippet + "…"
            return snippet.strip()

    return text[:max_chars]


class ChatMessagesAdapter(StoreAdapter):
    """Memory Graph adapter for chat messages.

    Searches user + assistant messages across all conversations for
    keyword matches via FTS5.
    """

    @property
    def name(self) -> str:
        return Source.CHATS.value

    async def fetch(self, query: str) -> list[Item]:
        """Fetch matching chat messages as memory graph Items."""
        if not query.strip():
            return []

        hits = search_chat_messages(query, limit=10)

        items: list[Item] = []
        for hit in hits:
            # Skip system and tool messages for search — they're noise
            if hit["role"] in ("system", "tool"):
                continue

            ts = None
            raw_ts = hit.get("created_at")
            if raw_ts is not None:
                try:
                    from datetime import datetime

                    ts = datetime.fromtimestamp(raw_ts)
                except (TypeError, OSError):
                    pass

            chat_title = hit.get("chat_title", "") or "Chat"
            content = hit.get("snippet") or hit.get("content", "")
            text = f"[{chat_title}] {content}"

            items.append(
                Item(
                    text=text,
                    source=Source.CHATS,
                    score=hit.get("score", 0.0),
                    ts=ts,
                    metadata={
                        "message_id": hit["message_id"],
                        "conversation_id": hit["conversation_id"],
                        "chat_title": chat_title,
                        "role": hit.get("role", ""),
                    },
                )
            )

        return items
