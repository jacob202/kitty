"""Undo/Restore endpoints (Packet 09)."""

from __future__ import annotations

from fastapi import APIRouter

from gateway import undo_journal
from gateway.errors import StorageConflict, StorageNotFound, ValidationError

router = APIRouter(tags=["undo"])


def _map_error(exc: undo_journal.UndoError) -> Exception:
    if isinstance(exc, undo_journal.UndoNotFound):
        return StorageNotFound(str(exc))
    if isinstance(exc, undo_journal.UndoConflict):
        return StorageConflict(str(exc))
    return ValidationError(str(exc))


@router.get("/undo/history")
async def undo_history(
    entity_type: str, entity_id: str, limit: int = 50
) -> dict:
    """List journal entries for one entity, newest first."""
    return {
        "entries": undo_journal.list_history(entity_type, entity_id, limit=limit)
    }


@router.post("/undo/{journal_id}")
async def undo_entry(journal_id: str) -> dict:
    """Undo a recorded mutation by restoring its prior (before) state."""
    try:
        result = undo_journal.undo(journal_id)
    except undo_journal.UndoError as exc:
        raise _map_error(exc) from exc
    return result
