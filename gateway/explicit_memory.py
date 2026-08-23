"""Governed user-confirmed memories stored in Kitty's existing SQLite DB."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

DB_FILE = KITTY_DB_FILE

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "do",
        "does",
        "for",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "the",
        "to",
        "use",
        "what",
        "when",
        "where",
        "which",
        "with",
    }
)


class ExplicitMemoryError(RuntimeError):
    """Base error for explicit-memory lifecycle operations."""


class ExplicitMemoryNotFound(ExplicitMemoryError):
    """Raised when a requested active memory does not exist."""


def _utc_iso(value: datetime | None = None) -> str:
    stamp = value or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).isoformat()


def _init() -> None:
    kitty_db.migrate(db_file=DB_FILE)


def _row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "memory_key": row["memory_key"],
        "namespace": row["namespace"],
        "text": row["text"],
        "source_kind": row["source_kind"],
        "source_ref": row["source_ref"],
        "sensitivity": row["sensitivity"],
        "pinned": bool(row["pinned"]),
        "status": row["status"],
        "superseded_by": row["superseded_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "forgotten_at": row["forgotten_at"],
        "truth_confidence": 1.0,
    }


def remember(
    text: str,
    *,
    namespace: str = "facts",
    memory_key: str | None = None,
    supersedes_id: str | None = None,
    source_kind: str = "user_explicit",
    source_ref: str | None = None,
    sensitivity: str = "normal",
    pinned: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Store one explicit memory; same-key writes supersede the prior active row."""
    cleaned = text.strip()
    if not cleaned:
        raise ExplicitMemoryError("memory text cannot be blank")
    key = memory_key.strip() if memory_key and memory_key.strip() else None
    shelf = namespace.strip() or "facts"
    if shelf not in {"facts", "preferences"}:
        raise ExplicitMemoryError(f"unsupported explicit-memory namespace: {shelf!r}")
    sensitivity_level = sensitivity.strip() or "normal"
    if sensitivity_level not in {"normal", "sensitive"}:
        raise ExplicitMemoryError(f"unsupported sensitivity: {sensitivity_level!r}")
    stamp = _utc_iso(now)
    memory_id = f"exp_{uuid.uuid4().hex}"
    _init()

    with kitty_db.connect(DB_FILE) as conn:
        if supersedes_id is not None:
            prior = conn.execute(
                "SELECT id, memory_key FROM explicit_memories WHERE id = ? AND status = 'active'",
                (supersedes_id,),
            ).fetchone()
            if prior is None:
                raise ExplicitMemoryNotFound(
                    f"active explicit memory {supersedes_id!r} was not found"
                )
            prior_key = prior["memory_key"]
            if key is None:
                key = prior_key
            elif prior_key is not None and key != prior_key:
                raise ExplicitMemoryError("memory_key conflicts with the memory being superseded")

        superseded_ids: list[str] = []
        if key is not None:
            superseded_ids = [
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM explicit_memories WHERE memory_key = ? AND status = 'active'",
                    (key,),
                ).fetchall()
            ]
        if supersedes_id is not None and supersedes_id not in superseded_ids:
            superseded_ids.append(supersedes_id)

        for old_id in superseded_ids:
            conn.execute(
                "UPDATE explicit_memories SET status = 'superseded', updated_at = ? WHERE id = ?",
                (stamp, old_id),
            )

        conn.execute(
            """
            INSERT INTO explicit_memories (
                id, memory_key, namespace, text, source_kind, source_ref,
                sensitivity, pinned, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                memory_id,
                key,
                shelf,
                cleaned,
                source_kind.strip() or "user_explicit",
                source_ref,
                sensitivity_level,
                int(pinned),
                stamp,
                stamp,
            ),
        )
        for old_id in superseded_ids:
            conn.execute(
                "UPDATE explicit_memories SET superseded_by = ? WHERE id = ?",
                (memory_id, old_id),
            )
        conn.commit()

    result = get(memory_id)
    if result is None:  # defensive: the insert above must be visible
        raise ExplicitMemoryError(f"stored explicit memory {memory_id!r} could not be re-read")
    return result


def get(memory_id: str, *, include_inactive: bool = False) -> dict[str, Any] | None:
    _init()
    sql = "SELECT * FROM explicit_memories WHERE id = ?"
    params: list[Any] = [memory_id]
    if not include_inactive:
        sql += " AND status = 'active'"
    with kitty_db.connect(DB_FILE) as conn:
        row = conn.execute(sql, params).fetchone()
    return _row(row) if row is not None else None


def list_memories(
    *,
    namespace: str | None = None,
    limit: int = 50,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    _init()
    clauses: list[str] = []
    params: list[Any] = []
    if not include_inactive:
        clauses.append("status = 'active'")
    if namespace:
        clauses.append("namespace = ?")
        params.append(namespace)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(int(limit), 1000)))
    with kitty_db.connect(DB_FILE) as conn:
        rows = conn.execute(
            f"SELECT * FROM explicit_memories{where} ORDER BY updated_at DESC LIMIT ?", params
        ).fetchall()
    return [_row(row) for row in rows]


def forget(memory_id: str, *, now: datetime | None = None) -> bool:
    """Suppress an active explicit memory while retaining its audit row."""
    _init()
    stamp = _utc_iso(now)
    with kitty_db.connect(DB_FILE) as conn:
        cursor = conn.execute(
            """
            UPDATE explicit_memories
            SET status = 'forgotten', forgotten_at = ?, updated_at = ?
            WHERE id = ? AND status = 'active'
            """,
            (stamp, stamp, memory_id),
        )
        conn.commit()
    return cursor.rowcount == 1


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(text.casefold()) if token not in _STOPWORDS}


def search(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Small lexical retrieval over active explicit records; truth is not age-scored."""
    query_terms = _tokens(query)
    if not query_terms:
        return []
    candidates = list_memories(limit=500)
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for row in candidates:
        row_terms = _tokens(f"{row['memory_key'] or ''} {row['text']}")
        overlap = len(query_terms & row_terms)
        if overlap == 0:
            continue
        relevance = overlap / max(1, len(query_terms))
        if row["pinned"]:
            relevance += 0.05
        scored.append((relevance, row["updated_at"], row))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [row for _, _, row in scored[: max(1, min(int(limit), 50))]]
