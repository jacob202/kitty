"""Image Studio V2 — Character library (private by default) with face
embeddings, versioning, tags, and character-specific gallery."""
from __future__ import annotations

import json
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


class GalleryItemNotFoundError(CharacterError):
    """Raised when a gallery item does not exist."""


@dataclass
class Character:
    character_id: str
    name: str
    description: str | None = None
    preferred_recipe: str | None = None
    identity_preset: str = "balanced"
    privacy_state: str = "private"
    soft_deleted: bool = False
    face_embedding: bytes | None = None
    face_embedding_model: str | None = None
    version: int = 1
    superseded_by: str | None = None
    tags: list[str] | None = None
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
            "face_embedding": self.face_embedding.hex() if self.face_embedding else None,
            "face_embedding_model": self.face_embedding_model,
            "version": self.version,
            "superseded_by": self.superseded_by,
            "tags": self.tags,
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
    tags: list[str] | None = None
    face_embedding: bytes | None = None
    face_embedding_model: str | None = None
    version: int = 1
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
            "tags": self.tags,
            "face_embedding": self.face_embedding.hex() if self.face_embedding else None,
            "face_embedding_model": self.face_embedding_model,
            "version": self.version,
            "created_at": self.created_at,
        }


@dataclass
class GalleryItem:
    item_id: str
    character_id: str
    job_id: str | None = None
    output_path: str = ""
    prompt: str | None = None
    recipe_id: str | None = None
    identity_mode: str | None = None
    identity_strength: float | None = None
    rating: int | None = None
    tags: list[str] | None = None
    sort_order: int = 0
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "character_id": self.character_id,
            "job_id": self.job_id,
            "output_path": self.output_path,
            "prompt": self.prompt,
            "recipe_id": self.recipe_id,
            "identity_mode": self.identity_mode,
            "identity_strength": self.identity_strength,
            "rating": self.rating,
            "tags": self.tags,
            "sort_order": self.sort_order,
            "created_at": self.created_at,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _ensure_db() -> None:
    kitty_db.migrate(db_file=KITTY_DB_FILE)


def _normalize_tags(tags: list[str] | None) -> str | None:
    if tags is None:
        return None
    unique = sorted(set(t.strip().lower() for t in tags if t.strip()))
    return json.dumps(unique) if unique else None


def list_characters(
    include_soft_deleted: bool = False,
    tag: str | None = None,
) -> list[Character]:
    _ensure_db()
    query = "SELECT * FROM image_characters"
    conditions: list[str] = []
    params: list[Any] = []
    if not include_soft_deleted:
        conditions.append("soft_deleted = 0")
    if tag:
        conditions.append("tags LIKE ?")
        params.append(f"%{tag.strip().lower()}%")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY updated_at DESC"
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        rows = conn.execute(query, params).fetchall()
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
    tags: list[str] | None = None,
    face_embedding: bytes | None = None,
    face_embedding_model: str | None = None,
) -> Character:
    if not name or not name.strip():
        raise CharacterError("name must not be empty")
    if len(name.strip()) > 120:
        raise CharacterError("name too long (max 120 chars)")
    valid_presets = ("creative", "balanced", "identity_first")
    if identity_preset not in valid_presets:
        raise CharacterError(
            f"identity_preset must be {'/'.join(valid_presets)}, got {identity_preset!r}"
        )

    _ensure_db()
    cid = _new_id("char_")
    now = _now()
    tags_json = _normalize_tags(tags)
    char = Character(
        character_id=cid,
        name=name.strip(),
        description=description,
        preferred_recipe=preferred_recipe,
        identity_preset=identity_preset,
        face_embedding=face_embedding,
        face_embedding_model=face_embedding_model,
        version=1,
        tags=tags,
        created_at=now,
        updated_at=now,
    )
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            """INSERT INTO image_characters
               (character_id, name, description, preferred_recipe, identity_preset,
                privacy_state, soft_deleted, face_embedding, face_embedding_model,
                version, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cid, char.name, char.description, char.preferred_recipe,
             char.identity_preset, char.privacy_state, 0,
             char.face_embedding, char.face_embedding_model,
             char.version, tags_json, now, now),
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
    tags: list[str] | None = None,
    face_embedding: bytes | None = None,
    face_embedding_model: str | None = None,
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
        valid_presets = ("creative", "balanced", "identity_first")
        if identity_preset not in valid_presets:
            raise CharacterError(
                f"identity_preset must be {'/'.join(valid_presets)}, got {identity_preset!r}"
            )
        updates["identity_preset"] = identity_preset
    if tags is not None:
        updates["tags"] = _normalize_tags(tags)
    if face_embedding is not None:
        updates["face_embedding"] = face_embedding
    if face_embedding_model is not None:
        updates["face_embedding_model"] = face_embedding_model

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


def supersede_character(character_id: str, successor_id: str) -> Character:
    """Mark character as superseded by another. Bumps version."""
    char = get_character(character_id)
    if char.soft_deleted:
        raise CharacterError(f"character {character_id!r} is soft-deleted")
    get_character(successor_id)
    now = _now()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            "UPDATE image_characters SET superseded_by = ?, version = version + 1, updated_at = ? WHERE character_id = ?",
            (successor_id, now, character_id),
        )
        conn.commit()
    return get_character(character_id)


def add_character_ref(
    character_id: str,
    data: bytes,
    *,
    original_name: str | None = None,
    media_type: str | None = None,
    quality_notes: str | None = None,
    is_primary: bool = False,
    tags: list[str] | None = None,
    face_embedding: bytes | None = None,
    face_embedding_model: str | None = None,
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

    tags_json = _normalize_tags(tags)
    ref = CharacterRef(
        ref_id=rid,
        character_id=character_id,
        storage_path=str(storage_path),
        original_name=original_name,
        media_type=media_type or "image/png",
        file_size=len(data),
        quality_notes=quality_notes,
        tags=tags,
        face_embedding=face_embedding,
        face_embedding_model=face_embedding_model,
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
                original_name, media_type, file_size, quality_notes,
                tags, face_embedding, face_embedding_model, version, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rid, character_id, next_order, int(is_primary), str(storage_path),
             original_name, ref.media_type, ref.file_size, quality_notes,
             tags_json, face_embedding, face_embedding_model, 1, ref.created_at),
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


# ── Gallery ──────────────────────────────────────────────────────────────────


def add_gallery_item(
    character_id: str,
    output_path: str,
    *,
    job_id: str | None = None,
    prompt: str | None = None,
    recipe_id: str | None = None,
    identity_mode: str | None = None,
    identity_strength: float | None = None,
    rating: int | None = None,
    tags: list[str] | None = None,
) -> GalleryItem:
    get_character(character_id)
    _ensure_db()
    item_id = _new_id("gal_")
    now = _now()
    tags_json = _normalize_tags(tags)

    next_order = 0
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        max_row = conn.execute(
            "SELECT MAX(sort_order) as mx FROM image_character_gallery WHERE character_id = ?",
            (character_id,),
        ).fetchone()
        if max_row and max_row["mx"] is not None:
            next_order = max_row["mx"] + 1
        conn.execute(
            """INSERT INTO image_character_gallery
               (item_id, character_id, job_id, output_path, prompt,
                recipe_id, identity_mode, identity_strength, rating,
                tags, sort_order, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item_id, character_id, job_id, output_path, prompt,
             recipe_id, identity_mode, identity_strength, rating,
             tags_json, next_order, now),
        )
        conn.commit()

    return GalleryItem(
        item_id=item_id,
        character_id=character_id,
        job_id=job_id,
        output_path=output_path,
        prompt=prompt,
        recipe_id=recipe_id,
        identity_mode=identity_mode,
        identity_strength=identity_strength,
        rating=rating,
        tags=tags,
        sort_order=next_order,
        created_at=now,
    )


def list_gallery(
    character_id: str,
    limit: int = 50,
    tag: str | None = None,
) -> list[GalleryItem]:
    get_character(character_id)
    _ensure_db()
    query = "SELECT * FROM image_character_gallery WHERE character_id = ?"
    params: list[Any] = [character_id]
    if tag:
        query += " AND tags LIKE ?"
        params.append(f"%{tag.strip().lower()}%")
    query += " ORDER BY sort_order DESC LIMIT ?"
    params.append(limit)
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_gallery(r) for r in rows]


def update_gallery_item(item_id: str, *, rating: int | None = None, tags: list[str] | None = None) -> GalleryItem:
    _ensure_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute(
            "SELECT * FROM image_character_gallery WHERE item_id = ?", (item_id,)
        ).fetchone()
    if row is None:
        raise GalleryItemNotFoundError(f"gallery item {item_id!r} not found")

    updates: dict[str, Any] = {}
    if rating is not None:
        updates["rating"] = rating
    if tags is not None:
        updates["tags"] = _normalize_tags(tags)

    if updates:
        set_clauses = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [item_id]
        with kitty_db.connect(KITTY_DB_FILE) as conn:
            conn.execute(
                f"UPDATE image_character_gallery SET {set_clauses} WHERE item_id = ?",
                values,
            )
            conn.commit()

    return get_gallery_item(item_id)


def get_gallery_item(item_id: str) -> GalleryItem:
    _ensure_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute(
            "SELECT * FROM image_character_gallery WHERE item_id = ?", (item_id,)
        ).fetchone()
    if row is None:
        raise GalleryItemNotFoundError(f"gallery item {item_id!r} not found")
    return _row_to_gallery(row)


def delete_gallery_item(item_id: str) -> None:
    _ensure_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute(
            "SELECT output_path FROM image_character_gallery WHERE item_id = ?", (item_id,)
        ).fetchone()
        if row is None:
            raise GalleryItemNotFoundError(f"gallery item {item_id!r} not found")
        conn.execute("DELETE FROM image_character_gallery WHERE item_id = ?", (item_id,))
        conn.commit()
    path = Path(row["output_path"])
    if path.exists():
        path.unlink(missing_ok=True)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ext_from_name(name: str) -> str:
    dot = name.rfind(".")
    if dot == -1:
        return "png"
    ext = name[dot + 1:].lower()
    allowed = {"png", "jpg", "jpeg", "webp", "gif"}
    return ext if ext in allowed else "png"


def _row_to_character(row: Any) -> Character:
    raw_tags = row["tags"]
    return Character(
        character_id=row["character_id"],
        name=row["name"],
        description=row["description"],
        preferred_recipe=row["preferred_recipe"],
        identity_preset=row["identity_preset"] or "balanced",
        privacy_state=row["privacy_state"] or "private",
        soft_deleted=bool(row["soft_deleted"]),
        face_embedding=row["face_embedding"],
        face_embedding_model=row["face_embedding_model"],
        version=row["version"] or 1,
        superseded_by=row["superseded_by"],
        tags=json.loads(raw_tags) if raw_tags else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_ref(row: Any) -> CharacterRef:
    raw_tags = row["tags"]
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
        tags=json.loads(raw_tags) if raw_tags else None,
        face_embedding=row["face_embedding"],
        face_embedding_model=row["face_embedding_model"],
        version=row["version"] or 1,
        created_at=row["created_at"],
    )


def _row_to_gallery(row: Any) -> GalleryItem:
    raw_tags = row["tags"]
    return GalleryItem(
        item_id=row["item_id"],
        character_id=row["character_id"],
        job_id=row["job_id"],
        output_path=row["output_path"],
        prompt=row["prompt"],
        recipe_id=row["recipe_id"],
        identity_mode=row["identity_mode"],
        identity_strength=row["identity_strength"],
        rating=row["rating"],
        tags=json.loads(raw_tags) if raw_tags else None,
        sort_order=row["sort_order"],
        created_at=row["created_at"],
    )


__all__ = [
    "Character",
    "CharacterRef",
    "GalleryItem",
    "CharacterError",
    "CharacterNotFoundError",
    "GalleryItemNotFoundError",
    "list_characters",
    "get_character",
    "create_character",
    "update_character",
    "soft_delete_character",
    "supersede_character",
    "add_character_ref",
    "list_character_refs",
    "delete_character_ref",
    "add_gallery_item",
    "list_gallery",
    "get_gallery_item",
    "update_gallery_item",
    "delete_gallery_item",
]
