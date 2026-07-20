"""Skill bundle import with DeepTutor-grade safety.

Adapted from ``deeptutor/utils/archive_extractor.py`` + ``document_validator.py``.
A skill bundle is a ``.zip`` of a ``SKILL.md`` plus optional data assets.
Importing an untrusted bundle is gated the same way as a document upload:

* every member is collapsed to a sanitized basename (defuses Zip Slip — no
  path component survives) and written flat into ``<skills>/{name}/``;
* per-entry uncompressed size, cumulative size, entry count and compression
  ratio are bounded to defeat zip bombs;
* only documentation/data extensions are accepted; no executable or nested
  archive survives;
* each member's leading bytes are sniffed so a renamed binary (``.exe`` -> ``.md``)
  is rejected;
* ``__MACOSX`` resource forks, dotfiles, and directories are dropped.

Failure is loud: any violation raises ``SkillImportError`` with a cause.

The destination follows Kitty's existing skill layout
(``.agents/skills/<name>/SKILL.md``), so imported skills are immediately
discoverable by :mod:`gateway.skill_registry`.
"""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from gateway.paths import PROJECT_ROOT

logger = logging.getLogger("kitty.skill_import")

SKILL_ROOT: Path = PROJECT_ROOT / ".agents" / "skills"

# A shared skill is documentation + data, never executable code.
ALLOWED_SKILL_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".txt", ".json", ".yaml", ".yml"}
)

# Conservative bounds; a skill bundle is small by nature.
MAX_BUNDLE_BYTES = 50 * 1024 * 1024
MAX_ENTRY_BYTES = 10 * 1024 * 1024
MAX_ENTRIES = 200
MAX_COMPRESSION_RATIO = 100.0

# Leading bytes that mark an executable or archive payload — rejected even if
# the extension claims to be a doc/data file.
_BINARY_PREFIXES: tuple[bytes, ...] = (
    b"MZ",          # DOS/PE executable
    b"PK\x03\x04",  # zip / office open xml
    b"\x1f\x8b",    # gzip
    b"\x7fELF",     # ELF binary
    b"OLE\x00",     # legacy OLE (old .doc/.xls)
)


class SkillImportError(ValueError):
    """Raised when a skill bundle fails import security or schema checks."""


@dataclass
class SkillImportResult:
    name: str
    path: Path
    files: list[str] = field(default_factory=list)


def _reject_binary_payload(name: str, data: bytes) -> None:
    head = data[:8]
    for prefix in _BINARY_PREFIXES:
        if head.startswith(prefix):
            raise SkillImportError(
                f"member {name!r} carries binary payload {prefix!r}; skill bundles "
                f"may only contain documentation/data files"
            )


def _skill_name_from(md_text: str) -> str:
    """Extract the ``name`` field from SKILL.md frontmatter, or raise."""
    text = md_text.lstrip()
    if not text.startswith("---"):
        raise SkillImportError("bundle SKILL.md has no YAML frontmatter")
    end = text.find("\n---", 3)
    if end == -1:
        raise SkillImportError("bundle SKILL.md frontmatter is unterminated")
    name = ""
    for line in text[3:end].splitlines():
        line = line.strip()
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip().strip('"').strip("'")
            break
    if not name:
        raise SkillImportError("bundle SKILL.md missing 'name' in frontmatter")
    if not name.replace("-", "").replace("_", "").isalnum():
        raise SkillImportError(f"invalid skill name: {name!r}")
    return name


def import_skill_bundle(zip_path: str | Path, *, target_root: Path = SKILL_ROOT) -> SkillImportResult:
    """Safely extract a skill ``.zip`` into ``target_root/{name}/`` and validate it.

    Returns :class:`SkillImportResult` on success. Raises :class:`SkillImportError`
    on any security or schema violation. Never silently skips a bad member.
    """
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise SkillImportError(f"bundle not found: {zip_path}")
    if zip_path.suffix.lower() != ".zip":
        raise SkillImportError(f"skill bundle must be a .zip, got {zip_path.suffix!r}")

    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise SkillImportError("bundle is corrupt or tampered") from exc
    with zf:
        if zf.testzip() is not None:
            raise SkillImportError("bundle is corrupt or tampered")
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            raise SkillImportError(f"too many entries: {len(infos)} > {MAX_ENTRIES}")

        # First pass: bounds + name + type checks (no extraction yet).
        total = 0
        skmd_text: str | None = None
        for info in infos:
            if info.is_dir():
                continue
            if info.filename.startswith("__MACOSX/") or "/." in info.filename or info.filename.endswith("/."):
                continue
            safe = Path(info.filename).name  # collapse to basename -> defuses Zip Slip
            if not safe or safe.startswith("."):
                continue
            ext = Path(safe).suffix.lower()
            if ext not in ALLOWED_SKILL_EXTENSIONS:
                raise SkillImportError(
                    f"rejected file type in bundle: {info.filename!r} ({ext or 'no extension'})"
                )
            if info.file_size > MAX_ENTRY_BYTES:
                raise SkillImportError(f"entry too large: {info.filename!r} ({info.file_size} bytes)")
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > MAX_COMPRESSION_RATIO:
                raise SkillImportError(f"zip-bomb suspect: {info.filename!r} ratio {ratio:.0f}x")
            total += info.file_size
            if total > MAX_BUNDLE_BYTES:
                raise SkillImportError(f"bundle too large: {total} > {MAX_BUNDLE_BYTES}")
            data = zf.read(info)
            _reject_binary_payload(safe, data)
            if safe == "SKILL.md":
                skmd_text = data.decode("utf-8", errors="strict")

        if skmd_text is None:
            raise SkillImportError("bundle has no SKILL.md")
        name = _skill_name_from(skmd_text)

        dest = target_root / name
        if dest.exists():
            raise SkillImportError(f"skill already exists: {name!r}")

        # Second pass: extract flat, validating each member's path.
        dest.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        for info in infos:
            if info.is_dir():
                continue
            if info.filename.startswith("__MACOSX/") or "/." in info.filename or info.filename.endswith("/."):
                continue
            safe = Path(info.filename).name
            if not safe or safe.startswith("."):
                continue
            ext = Path(safe).suffix.lower()
            if ext not in ALLOWED_SKILL_EXTENSIONS:
                continue
            target = (dest / safe).resolve()
            if target != (dest / safe).resolve() or not str(target).startswith(str(dest.resolve())):
                raise SkillImportError(f"zip-slip attempt: {info.filename!r}")
            data = zf.read(info)
            _reject_binary_payload(safe, data)
            target.write_bytes(data)
            written.append(safe)

    logger.info("Imported skill %r (%d files) from %s", name, len(written), zip_path)
    return SkillImportResult(name=name, path=dest, files=written)


__all__ = ["SkillImportError", "SkillImportResult", "import_skill_bundle"]
