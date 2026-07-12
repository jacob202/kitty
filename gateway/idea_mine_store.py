"""Packet 024 phase 2 — chat-log idea mine review store and pipeline.

Holds extraction candidates produced by ``scripts/curation/extract_chat_goldmine.py``
in a dedicated SQLite table. Items stay quarantined until Jacob reviews them:
only ``approved`` / ``edited`` items may surface in future context, and only
those are eligible to flow into the existing inbox → triage → knowledge
pipeline. This obeys packet 023's taste rules — nothing recovered from chat
history becomes always-on memory until Jacob explicitly approves it.

Nothing in this module writes to mem0 / memory_graph / long-term memory
directly. The inbox hand-off is the *only* outward path, and it is gated on
review state.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from gateway import db as kitty_db
from gateway.paths import INBOX_FILE, KITTY_DB_FILE

logger = logging.getLogger("kitty.idea_mine_store")

IDEA_MINE_DB_FILE = KITTY_DB_FILE

OBJECT_TYPES = {
    "project_thread",
    "idea_seed",
    "decision_recovered",
    "preference_or_taste",
    "prompt_or_workflow",
}
SENSITIVITIES = {"normal", "personal", "sensitive", "quiet"}
REVIEW_STATES = {"unreviewed", "approved", "edited", "rejected", "keep_quiet"}

# Only these review states may appear in future context (packet 023: no
# unreviewed item becomes always-on memory; rejected / keep_quiet never surface).
SURFACEABLE_REVIEW_STATES = {"approved", "edited"}
# Explicitly suppressed — must never surface, even if looked up by query.
SUPPRESSED_REVIEW_STATES = {"rejected", "keep_quiet"}


def init_db(db_file: Path = IDEA_MINE_DB_FILE) -> None:
    """Apply pending migrations. Idempotent."""
    kitty_db.migrate(db_file=db_file)


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _validate_item(item: dict[str, Any]) -> None:
    if not isinstance(item, dict):
        raise ValueError("idea_mine item must be a dict")
    if item.get("object_type") not in OBJECT_TYPES:
        raise ValueError(f"unknown object_type: {item.get('object_type')!r}")
    if item.get("user_review", "unreviewed") not in REVIEW_STATES:
        raise ValueError(f"bad user_review: {item.get('user_review')!r}")


def insert_item(item: dict[str, Any], *, db_file: Path = IDEA_MINE_DB_FILE) -> int:
    """Insert one extraction item. Returns the new row id."""
    _validate_item(item)
    object_type = item["object_type"]
    user_review = item.get("user_review", "unreviewed")
    source_ref = item.get("evidence_source") or item.get("source_ref")
    payload = {k: v for k, v in item.items() if k not in ("evidence_source", "source_ref")}
    now = _now_iso()
    with kitty_db.connect(db_file) as conn:
        cur = conn.execute(
            """
            INSERT INTO idea_mine_items
                (object_type, payload_json, source_ref, user_review, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (object_type, json.dumps(payload, ensure_ascii=False), source_ref, user_review, now, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def import_from_jsonl(path: str | Path, *, db_file: Path = IDEA_MINE_DB_FILE) -> int:
    """Read a JSONL file from the extractor and insert each item.

    Fail loud: a malformed line raises instead of being silently skipped.
    Returns the number of items inserted.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"idea mine import file not found: {p}")
    count = 0
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            insert_item(json.loads(line), db_file=db_file)
            count += 1
    logger.info("imported %d idea-mine item(s) from %s", count, p)
    return count


def list_items(
    object_type: str | None = None,
    review: str | None = None,
    *,
    db_file: Path = IDEA_MINE_DB_FILE,
) -> list[dict[str, Any]]:
    """Return rows as dicts with ``payload`` (parsed) and row metadata."""
    clauses: list[str] = []
    params: list[Any] = []
    if object_type is not None:
        clauses.append("object_type = ?")
        params.append(object_type)
    if review is not None:
        clauses.append("user_review = ?")
        params.append(review)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with kitty_db.connect(db_file) as conn:
        rows = conn.execute(
            f"SELECT * FROM idea_mine_items {where} ORDER BY id ASC", params
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_item(item_id: int, *, db_file: Path = IDEA_MINE_DB_FILE) -> dict[str, Any] | None:
    with kitty_db.connect(db_file) as conn:
        row = conn.execute(
            "SELECT * FROM idea_mine_items WHERE id = ?", (item_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def set_review(
    item_id: int,
    review_state: str,
    *,
    db_file: Path = IDEA_MINE_DB_FILE,
) -> bool:
    """Update an item's review state. Returns False if the item is missing."""
    if review_state not in REVIEW_STATES:
        raise ValueError(f"bad user_review: {review_state!r}")
    now = _now_iso()
    with kitty_db.connect(db_file) as conn:
        cur = conn.execute(
            "UPDATE idea_mine_items SET user_review = ?, updated_at = ? WHERE id = ?",
            (review_state, now, item_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return False
    return True


def is_surfaceable(item: dict[str, Any]) -> bool:
    """Whether a single item may appear in future context.

    Implements packet 023's gate: only reviewed-and-approved items surface.
    ``rejected`` / ``keep_quiet`` are explicitly suppressed; ``unreviewed``
    stays quarantined until Jacob decides.
    """
    review = item.get("user_review", "unreviewed")
    return review in SURFACEABLE_REVIEW_STATES


def surfaceable_items(*, db_file: Path = IDEA_MINE_DB_FILE) -> list[dict[str, Any]]:
    """Return only items that may appear in future context."""
    placeholders = ", ".join("?" for _ in SURFACEABLE_REVIEW_STATES)
    with kitty_db.connect(db_file) as conn:
        rows = conn.execute(
            f"SELECT * FROM idea_mine_items WHERE user_review IN ({placeholders}) "
            "ORDER BY id ASC",
            tuple(SURFACEABLE_REVIEW_STATES),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def export_approved_to_inbox(
    *,
    db_file: Path = IDEA_MINE_DB_FILE,
    inbox_file: Path = INBOX_FILE,
    dry_run: bool = False,
) -> list[int]:
    """Hand reviewed (surfaceable, un-exported) items to the inbox pipeline.

    Approved items become inbox entries so they flow through the existing
    triage → knowledge pipeline. Items that are unreviewed, rejected, or
    keep_quiet are never handed off — that is the packet-023 taste gate.

    Returns the list of item ids exported (empty when ``dry_run``).
    """
    from gateway import desktop_store

    candidates = surfaceable_items(db_file=db_file)
    exported_ids: list[int] = []
    for item in candidates:
        if item.get("exported_at"):
            continue
        entry_text = _item_to_inbox_text(item)
        if not dry_run:
            desktop_store.append_text_capture(
                text=entry_text,
                source="idea_mine",
                capture_type="idea_mine",
                tags=["idea-mine", item["object_type"]],
                inbox_file=inbox_file,
            )
            now = _now_iso()
            with kitty_db.connect(db_file) as conn:
                conn.execute(
                    "UPDATE idea_mine_items SET exported_at = ?, updated_at = ? WHERE id = ?",
                    (now, now, item["id"]),
                )
                conn.commit()
        exported_ids.append(item["id"])
    return exported_ids


def _item_to_inbox_text(item: dict[str, Any]) -> str:
    payload = item.get("payload", {})
    lines = [
        f"[idea-mine:{item['object_type']}] {payload.get('title', '(untitled)')}",
    ]
    for key in ("one_line", "spark", "decision", "preference", "name"):
        if payload.get(key):
            lines.append(payload[key])
    if payload.get("why_it_matters"):
        lines.append(f"why it matters: {payload['why_it_matters']}")
    if payload.get("next_small_move"):
        lines.append(f"next small move: {payload['next_small_move']}")
    sensitivity = payload.get("sensitivity")
    if sensitivity in ("sensitive", "quiet"):
        lines.append("sensitivity: quiet — surface only when directly relevant")
    return "\n".join(lines)


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    payload = json.loads(d.pop("payload_json", "{}"))
    d["payload"] = payload
    d["id"] = int(d["id"])
    return d


__all__ = [
    "IDEA_MINE_DB_FILE",
    "OBJECT_TYPES",
    "SENSITIVITIES",
    "REVIEW_STATES",
    "SURFACEABLE_REVIEW_STATES",
    "SUPPRESSED_REVIEW_STATES",
    "init_db",
    "insert_item",
    "import_from_jsonl",
    "list_items",
    "get_item",
    "set_review",
    "is_surfaceable",
    "surfaceable_items",
    "export_approved_to_inbox",
]
