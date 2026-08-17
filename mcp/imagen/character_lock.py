"""Single-reference character lock — one approved photo per character, fail-closed.

A character's identity reference is not "whatever is in the faces directory
today" — it is exactly the file recorded in ``reference.lock.json``, verified
by SHA-256 on every read. Any drift (missing lock, missing file, changed
bytes, undecodable image) blocks rather than silently substituting a
different photo. Locks live under ``settings.character_locks_dir`` (default
``~/kitty-services/faces``), outside the git-tracked repo.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from mcp.imagen.config import settings


class CharacterLockError(Exception):
    """Reference lock missing, broken, or tampered with — never fall back."""


@dataclass(frozen=True)
class LockedReference:
    character: str
    path: Path
    sha256: str
    width: int
    height: int


def lock_path(character: str) -> Path:
    """Where ``character``'s lock file lives."""
    return settings.character_locks_dir / character / "reference.lock.json"


def locked_reference_path(character: str) -> Path:
    """Return the verified canonical reference path for ``character``.

    Raises ``CharacterLockError`` (fail closed) on any lock, file, or
    integrity problem — never falls back to another image.
    """
    return resolve_locked_reference(character).path


def resolve_locked_reference(character: str) -> LockedReference:
    lp = lock_path(character)
    if not lp.exists():
        raise CharacterLockError(f"no reference lock for {character!r}: {lp} does not exist")

    try:
        raw = json.loads(lp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise CharacterLockError(f"reference lock for {character!r} is unreadable: {e}") from e

    ref_path_str = raw.get("path")
    expected_sha = raw.get("sha256")
    if not ref_path_str or not expected_sha:
        raise CharacterLockError(
            f"reference lock for {character!r} is missing required fields (path/sha256): {lp}"
        )

    ref_path = Path(ref_path_str).expanduser()
    if not ref_path.exists():
        raise CharacterLockError(
            f"locked reference for {character!r} is missing on disk: {ref_path}"
        )

    actual_sha = _sha256_file(ref_path)
    if actual_sha != expected_sha:
        raise CharacterLockError(
            f"locked reference for {character!r} changed since it was locked: "
            f"expected sha256 {expected_sha}, found {actual_sha} at {ref_path}. "
            "Refusing to use a different image — re-lock explicitly if this is intentional."
        )

    width, height = _decode_dimensions(ref_path, character)

    return LockedReference(
        character=character,
        path=ref_path,
        sha256=actual_sha,
        width=width,
        height=height,
    )


def create_lock(character: str, source_path: Path | str) -> LockedReference:
    """Write ``reference.lock.json`` for ``character`` pointing at ``source_path``.

    SHA-256 and dimensions are computed from the file itself, so the lock is
    always internally consistent at creation time. Does not copy the photo —
    the lock records a path, the photo stays wherever it already lives.
    """
    source_path = Path(source_path).expanduser()
    if not source_path.exists():
        raise CharacterLockError(f"cannot lock missing file: {source_path}")

    sha = _sha256_file(source_path)
    width, height = _decode_dimensions(source_path, character)

    lp = lock_path(character)
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_text(
        json.dumps(
            {
                "character": character,
                "path": str(source_path),
                "sha256": sha,
                "width": width,
                "height": height,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return LockedReference(
        character=character, path=source_path, sha256=sha, width=width, height=height
    )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _decode_dimensions(path: Path, character: str) -> tuple[int, int]:
    from PIL import Image as PILImage
    from PIL import UnidentifiedImageError

    try:
        with PILImage.open(path) as img:
            img.verify()
        with PILImage.open(path) as img:
            return img.size
    except (UnidentifiedImageError, OSError) as e:
        raise CharacterLockError(
            f"locked reference for {character!r} cannot be decoded as an image: {path} ({e})"
        ) from e
