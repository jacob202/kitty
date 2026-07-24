"""Read and update Kitty's personality documents — soul, identity, agents, and preferences."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from threading import Lock

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from gateway.paths import CONFIG_DIR, PERSONALITY_DIR
from gateway.personality import invalidate_cache

router = APIRouter(tags=["settings"])

SOUL_FILE = CONFIG_DIR / "SOUL.md"
PREFERENCES_FILE = CONFIG_DIR / "PREFERENCES.md"

# Personality files live in the personality/ directory
PERSONALITY_FILES: dict[str, Path] = {
    "soul.md": PERSONALITY_DIR / "soul.md",
    "identity.md": PERSONALITY_DIR / "identity.md",
    "agents.md": PERSONALITY_DIR / "agents.md",
}

_DOCUMENT_LOCK = Lock()


class PersonalityUpdate(BaseModel):
    """Complete, non-empty replacements for the visible personality documents."""

    soul: str = Field(min_length=1)
    preferences: str = Field(min_length=1)

    @model_validator(mode="after")
    def documents_must_not_be_blank(self) -> "PersonalityUpdate":
        if not self.soul.strip():
            raise ValueError("Soul cannot be blank")
        if not self.preferences.strip():
            raise ValueError("Preferences cannot be blank")
        return self


def _normalise_document(content: str, *, label: str) -> str:
    if not content.strip():
        raise ValueError(f"{label} cannot be blank")
    return content.rstrip() + "\n"


def _stage_document(path: Path, content: str, mode: int) -> str:
    fd, temporary_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise
    return temporary_path


def _write_documents(soul: str, preferences: str) -> None:
    """Replace both documents under one lock and roll back a partial pair write."""
    paths = (SOUL_FILE, PREFERENCES_FILE)
    with _DOCUMENT_LOCK:
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(f"Personality config file is missing: {path}")

        originals = {path: path.read_bytes() for path in paths}
        modes = {path: path.stat().st_mode & 0o777 for path in paths}
        temporary_paths = [
            _stage_document(path, content, modes[path])
            for path, content in ((SOUL_FILE, soul), (PREFERENCES_FILE, preferences))
        ]
        replaced: list[Path] = []
        try:
            for temporary_path, path in zip(temporary_paths, paths):
                os.replace(temporary_path, path)
                replaced.append(path)
        except Exception as exc:
            try:
                for path in replaced:
                    restore_path = _stage_document(path, originals[path].decode("utf-8"), modes[path])
                    os.replace(restore_path, path)
            except Exception as rollback_exc:
                raise RuntimeError(
                    f"Personality update failed and rollback failed: {rollback_exc}"
                ) from exc
            raise
        finally:
            for temporary_path in temporary_paths:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass


@router.get("/settings/personality")
def get_personality() -> dict[str, str]:
    """Return all personality documents — soul, identity, agents, and preferences."""
    result: dict[str, str] = {}
    for name, path in PERSONALITY_FILES.items():
        try:
            result[name] = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            result[name] = ""
    result["soul"] = SOUL_FILE.read_text(encoding="utf-8")
    result["preferences"] = PREFERENCES_FILE.read_text(encoding="utf-8")
    return result


@router.put("/settings/personality")
def put_personality(payload: PersonalityUpdate) -> dict[str, bool]:
    """Persist an intentional complete replacement of both legacy personality documents."""
    soul = _normalise_document(payload.soul, label="Soul")
    preferences = _normalise_document(payload.preferences, label="Preferences")
    _write_documents(soul, preferences)
    invalidate_cache()
    return {"ok": True}
