"""Tests for mcp/imagen/character_lock.py — single-reference fail-closed lock."""
from __future__ import annotations

import hashlib
import json

import pytest

from mcp.imagen.config import settings


@pytest.fixture(autouse=True)
def _isolate_locks_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "character_locks_dir", tmp_path / "locks")


def _make_png(path, pixel=(10, 20, 30), size=(4, 4)):
    from PIL import Image

    Image.new("RGB", size, pixel).save(path, format="PNG")


def test_lock_path_layout(tmp_path):
    from mcp.imagen.character_lock import lock_path

    p = lock_path("james")
    assert p == settings.character_locks_dir / "james" / "reference.lock.json"


def test_resolve_missing_lock_blocks():
    from mcp.imagen.character_lock import CharacterLockError, resolve_locked_reference

    with pytest.raises(CharacterLockError, match="no reference lock"):
        resolve_locked_reference("james")


def test_create_and_resolve_lock(tmp_path):
    from mcp.imagen.character_lock import create_lock, resolve_locked_reference

    photo = tmp_path / "james.png"
    _make_png(photo)

    locked = create_lock("james", photo)
    assert locked.character == "james"
    assert locked.path == photo
    assert locked.width == 4
    assert locked.height == 4

    resolved = resolve_locked_reference("james")
    assert resolved.path == photo
    assert resolved.sha256 == hashlib.sha256(photo.read_bytes()).hexdigest()


def test_create_lock_missing_source_blocks(tmp_path):
    from mcp.imagen.character_lock import CharacterLockError, create_lock

    with pytest.raises(CharacterLockError, match="missing file"):
        create_lock("james", tmp_path / "does-not-exist.png")


def test_resolve_blocks_when_file_deleted(tmp_path):
    from mcp.imagen.character_lock import (
        CharacterLockError,
        create_lock,
        resolve_locked_reference,
    )

    photo = tmp_path / "james.png"
    _make_png(photo)
    create_lock("james", photo)
    photo.unlink()

    with pytest.raises(CharacterLockError, match="missing on disk"):
        resolve_locked_reference("james")


def test_resolve_blocks_on_sha_mismatch(tmp_path):
    from mcp.imagen.character_lock import (
        CharacterLockError,
        create_lock,
        resolve_locked_reference,
    )

    photo = tmp_path / "james.png"
    _make_png(photo)
    create_lock("james", photo)

    # Bytes changed after the lock was written — must never silently re-hash
    # and accept the new file as canonical.
    _make_png(photo, pixel=(200, 50, 5))

    with pytest.raises(CharacterLockError, match="changed"):
        resolve_locked_reference("james")


def test_resolve_blocks_on_undecodable_image(tmp_path):
    from mcp.imagen.character_lock import CharacterLockError, lock_path, resolve_locked_reference

    photo = tmp_path / "james.png"
    photo.write_bytes(b"not actually an image")

    lp = lock_path("james")
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_text(
        json.dumps(
            {
                "character": "james",
                "path": str(photo),
                "sha256": hashlib.sha256(photo.read_bytes()).hexdigest(),
            }
        )
    )

    with pytest.raises(CharacterLockError, match="cannot be decoded"):
        resolve_locked_reference("james")


def test_resolve_blocks_on_missing_fields(tmp_path):
    from mcp.imagen.character_lock import CharacterLockError, lock_path, resolve_locked_reference

    lp = lock_path("james")
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_text(json.dumps({"character": "james"}))

    with pytest.raises(CharacterLockError, match="missing"):
        resolve_locked_reference("james")


def test_locked_reference_path_helper(tmp_path):
    from mcp.imagen.character_lock import create_lock, locked_reference_path

    photo = tmp_path / "james.png"
    _make_png(photo)
    create_lock("james", photo)

    assert locked_reference_path("james") == photo


def test_never_falls_back_to_other_files_in_dir(tmp_path):
    """A stray second photo in the same character dir must never be picked up."""
    from mcp.imagen.character_lock import create_lock, resolve_locked_reference

    photo = tmp_path / "james_real.png"
    _make_png(photo)
    create_lock("james", photo)

    decoy = tmp_path / "james_decoy.png"
    _make_png(decoy, pixel=(1, 2, 3))

    resolved = resolve_locked_reference("james")
    assert resolved.path == photo
