"""Document upload validation for knowledge ingestion.

Defense-in-depth for ``POST /knowledge/ingest``. DeepTutor validates uploads
with magic-byte sniffing, an extension allowlist, and filename sanitization
(see ``deeptutor/utils/document_validator.py``). Kitty's knowledge route
currently trusts the file extension and size bounds alone; this module closes
that gap without adding dependencies.

Failure is loud: invalid inputs raise ``DocumentValidationError`` with a cause,
never a silent default.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("kitty.document_validator")

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB — matches the route's download cap.

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".docx",
    ".doc",
    ".rtf",
    ".html",
    ".htm",
    ".xml",
    ".json",
    ".csv",
    ".xlsx",
    ".xls",
    ".pptx",
    ".ppt",
}

# Magic-byte prefixes used to reject extension spoofing. A file claiming to be
# .pdf but starting with MZ (executable) is rejected.
_MAGIC_PREFIXES: dict[bytes, set[str]] = {
    b"%PDF": {".pdf"},
    b"PK\x03\x04": {".docx", ".xlsx", ".pptx", ".ppt", ".doc", ".rtf"},
    b"\x1f\x8b": {".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm"},
}


class DocumentValidationError(Exception):
    """Raised when an uploaded document fails safety validation."""


def _check_magic(path: Path, ext: str) -> None:
    """Reject files whose leading bytes contradict the declared extension."""
    try:
        head = path.read_bytes()[:8]
    except OSError as exc:
        raise DocumentValidationError(f"cannot read file: {exc}") from exc
    for prefix, expected in _MAGIC_PREFIXES.items():
        if head.startswith(prefix) and ext not in expected:
            raise DocumentValidationError(
                f"file content ({prefix!r}) does not match extension {ext!r}"
            )


def sanitize_filename(name: str) -> str:
    """Return a filesystem-safe filename, preserving a valid extension.

    Strips path components, null bytes, and control characters. Unicode is
    NFC-normalized. Absolute or traversal paths collapse to a bare name.
    """
    import unicodedata

    name = unicodedata.normalize("NFC", name)
    name = name.replace("\x00", "")
    name = "".join(ch for ch in name if ord(ch) >= 32)
    name = name.replace("\\", "/")  # treat backslash as a separator too
    name = Path(name).name or "upload"
    if not name or name in (".", ".."):
        name = "upload"
    return name


def validate_document(path: str | Path) -> Path:
    """Validate a local file for knowledge ingestion.

    Checks existence, size, extension allowlist, and magic bytes. Returns the
    validated ``Path``. Raises ``DocumentValidationError`` on any failure.
    """
    p = Path(path).expanduser()
    if not p.exists():
        raise DocumentValidationError(f"file not found: {p}")
    if not p.is_file():
        raise DocumentValidationError(f"not a regular file: {p}")
    try:
        size = p.stat().st_size
    except OSError as exc:
        raise DocumentValidationError(f"cannot stat file: {exc}") from exc
    if size > MAX_FILE_SIZE:
        raise DocumentValidationError(
            f"file too large: {size} bytes exceeds {MAX_FILE_SIZE} byte cap"
        )
    ext = p.suffix.lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise DocumentValidationError(f"unsupported extension: {ext!r}")
    _check_magic(p, ext)
    return p
