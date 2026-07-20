"""Image Studio V1 — Character library (private by default)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway import db as kitty_db
from gateway.paths import KITTY_DATA_DIR, KITTY_DB_FILE

CHARACTER_STORAGE_DIR = KITTY_DATA_DIR / "image_characters"
CHARACTER_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class CharacterError(RuntimeError):
    """Raised when a character-store operation cannot complete safely."""


class CharacterNotFoundError(CharacterError):
    """Raised when a character id does not exist."""


@dataclass
class Character:
    character_id: str
    name: str
    description: str | None = None
    preferred_recipe: str | None = None
    identity_preset: str = "balanced"
    privacy_state: str = "private"
    soft_deleted: bool = False
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "character_id": self.character_id,
            "name": self.name,
            "description": self.description,
            "preferred_recipe": self.preferred_recipe,
            "identity_preset": self.identity_preset,
            "privacy_state": self.privacy_state,
            "soft_deleted": self.soft_deleted,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class CharacterRef:
    ref_id: str
    character_id: str
    sort_order: int = 0
    is_primary: bool = False
    storage_path: str = ""
    original_name: str | None = None
    media_type: str | None = None
    file_size: int | None = None
    width: int | None = None
    height: int | None = None
    quality_notes: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref_id": self.ref_id,
            "character_id": self.character_id,
            "sort_order": self.sort_order,
            "is_primary": self.is_primary,
            "storage_path": self.storage_path,
            "original_name": self.original_name,
            "media_type": self.media_type,
            "file_size": self.file_size,
            "width": self.width,
            "height": self.height,
            "quality_notes": self.quality_notes,
            "created_at": self.created_at,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _ensure_db() -> None:
    kitty_db.migrate(db_file=KITTY_DB_FILE)


def list_characters(include_soft_deleted: bool = False) -> list[Character]:
    _ensure_db()
    query = "SELECT * FROM image_characters"
    if not include_soft_deleted:
        query += " WHERE soft_deleted = 0"
    query += " ORDER BY updated_at DESC"
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        rows = conn.execute(query).fetchall()
    return [_row_to_character(r) for r in rows]


def get_character(character_id: str) -> Character:
    _ensure_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute(
            "SELECT * FROM image_characters WHERE character_id = ?", (character_id,)
        ).fetchone()
    if row is None:
        raise CharacterNotFoundError(f"character {character_id!r} not found")
    return _row_to_character(row)


def create_character(
    name: str,
    *,
    description: str | None = None,
    preferred_recipe: str | None = None,
    identity_preset: str = "balanced",
) -> Character:
    if not name or not name.strip():
        raise CharacterError("name must not be empty")
    if len(name.strip()) > 120:
        raise CharacterError("name too long (max 120 chars)")

    _ensure_db()
    cid = _new_id("char_")
    now = _now()
    char = Character(
        character_id=cid,
        name=name.strip(),
        description=description,
        preferred_recipe=preferred_recipe,
        identity_preset=identity_preset,
        created_at=now,
        updated_at=now,
    )
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            """INSERT INTO image_characters
               (character_id, name, description, preferred_recipe, identity_preset,
                privacy_state, soft_deleted, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cid, char.name, char.description, char.preferred_recipe,
             char.identity_preset, char.privacy_state, 0, now, now),
        )
        conn.commit()
    return char


def update_character(
    character_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    preferred_recipe: str | None = None,
    identity_preset: str | None = None,
) -> Character:
    char = get_character(character_id)
    if char.soft_deleted:
        raise CharacterError(f"character {character_id!r} is soft-deleted")

    updates: dict[str, Any] = {"updated_at": _now()}
    if name is not None:
        if not name.strip():
            raise CharacterError("name must not be empty")
        updates["name"] = name.strip()
    if description is not None:
        updates["description"] = description
    if preferred_recipe is not None:
        updates["preferred_recipe"] = preferred_recipe
    if identity_preset is not None:
        if identity_preset not in ("creative", "balanced", "identity_first"):
            raise CharacterError(
                f"identity_preset must be creative/balanced/identity_first, got {identity_preset!r}"
            )
        updates["identity_preset"] = identity_preset

    set_clauses = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [character_id]
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            f"UPDATE image_characters SET {set_clauses} WHERE character_id = ?", values
        )
        conn.commit()
    return get_character(character_id)


def soft_delete_character(character_id: str) -> Character:
    char = get_character(character_id)
    now = _now()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            "UPDATE image_characters SET soft_deleted = 1, updated_at = ? WHERE character_id = ?",
            (now, character_id),
        )
        conn.commit()
    char.soft_deleted = True
    char.updated_at = now
    return char


def add_character_ref(
    character_id: str,
    data: bytes,
    *,
    original_name: str | None = None,
    media_type: str | None = None,
    quality_notes: str | None = None,
    is_primary: bool = False,
) -> CharacterRef:
    char = get_character(character_id)
    if char.soft_deleted:
        raise CharacterError(f"character {character_id!r} is soft-deleted")

    _ensure_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        existing = conn.execute(
            "SELECT COUNT(*) as cnt FROM image_character_refs WHERE character_id = ?",
            (character_id,),
        ).fetchone()
        if existing["cnt"] >= 6:
            raise CharacterError("character already has 6 reference images (max)")

    rid = _new_id("cref_")
    char_dir = CHARACTER_STORAGE_DIR / character_id
    char_dir.mkdir(parents=True, exist_ok=True)
    ext = _ext_from_name(original_name) if original_name else "png"
    storage_path = char_dir / f"{rid}.{ext}"
    storage_path.write_bytes(data)

    ref = CharacterRef(
        ref_id=rid,
        character_id=character_id,
        storage_path=str(storage_path),
        original_name=original_name,
        media_type=media_type or "image/png",
        file_size=len(data),
        quality_notes=quality_notes,
        created_at=_now(),
    )

    if is_primary:
        _ensure_db()
        with kitty_db.connect(KITTY_DB_FILE) as conn:
            conn.execute(
                "UPDATE image_character_refs SET is_primary = 0 WHERE character_id = ?",
                (character_id,),
            )
        ref.is_primary = True

    next_order = 0
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        max_row = conn.execute(
            "SELECT MAX(sort_order) as mx FROM image_character_refs WHERE character_id = ?",
            (character_id,),
        ).fetchone()
        if max_row and max_row["mx"] is not None:
            next_order = max_row["mx"] + 1
        conn.execute(
            """INSERT INTO image_character_refs
               (ref_id, character_id, sort_order, is_primary, storage_path,
                original_name, media_type, file_size, quality_notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rid, character_id, next_order, int(is_primary), str(storage_path),
             original_name, ref.media_type, ref.file_size, quality_notes, ref.created_at),
        )
        conn.commit()

    ref.sort_order = next_order
    return ref


def list_character_refs(character_id: str) -> list[CharacterRef]:
    get_character(character_id)
    _ensure_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        rows = conn.execute(
            "SELECT * FROM image_character_refs WHERE character_id = ? ORDER BY sort_order",
            (character_id,),
        ).fetchall()
    return [_row_to_ref(r) for r in rows]


def delete_character_ref(character_id: str, ref_id: str) -> None:
    get_character(character_id)
    _ensure_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute(
            "SELECT storage_path FROM image_character_refs WHERE ref_id = ? AND character_id = ?",
            (ref_id, character_id),
        ).fetchone()
        if row is None:
            raise CharacterError(f"ref {ref_id!r} not found for character {character_id!r}")
        path = Path(row["storage_path"])
        conn.execute(
            "DELETE FROM image_character_refs WHERE ref_id = ? AND character_id = ?",
            (ref_id, character_id),
        )
        conn.commit()
    if path.exists():
        path.unlink(missing_ok=True)


def _ext_from_name(name: str) -> str:
    dot = name.rfind(".")
    if dot == -1:
        return "png"
    ext = name[dot + 1:].lower()
    allowed = {"png", "jpg", "jpeg", "webp", "gif"}
    return ext if ext in allowed else "png"


def _row_to_character(row: Any) -> Character:
    return Character(
        character_id=row["character_id"],
        name=row["name"],
        description=row["description"],
        preferred_recipe=row["preferred_recipe"],
        identity_preset=row["identity_preset"] or "balanced",
        privacy_state=row["privacy_state"] or "private",
        soft_deleted=bool(row["soft_deleted"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_ref(row: Any) -> CharacterRef:
    return CharacterRef(
        ref_id=row["ref_id"],
        character_id=row["character_id"],
        sort_order=row["sort_order"],
        is_primary=bool(row["is_primary"]),
        storage_path=row["storage_path"],
        original_name=row["original_name"],
        media_type=row["media_type"],
        file_size=row["file_size"],
        width=row["width"],
        height=row["height"],
        quality_notes=row["quality_notes"],
        created_at=row["created_at"],
    )
