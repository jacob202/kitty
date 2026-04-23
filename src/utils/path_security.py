"""Small path-validation helpers for user-supplied route values."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")


class PathSecurityError(ValueError):
    """Raised when a user-supplied path or id is unsafe."""


def safe_project_id(value: object, *, field: str = "project_id") -> str:
    """Return a safe project id containing only simple filename-safe characters."""
    if not isinstance(value, str):
        raise PathSecurityError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise PathSecurityError(f"{field} is required")
    if "/" in cleaned or "\\" in cleaned or cleaned in {".", ".."}:
        raise PathSecurityError(f"{field} contains invalid path characters")
    if not PROJECT_ID_RE.fullmatch(cleaned):
        raise PathSecurityError(f"{field} contains invalid characters")
    return cleaned


def resolve_allowed_file(path_value: object, allowed_roots: Iterable[Path]) -> Path:
    """Resolve a user-supplied file path and require it to stay inside allowed roots."""
    if not isinstance(path_value, str):
        raise PathSecurityError("pdf_path must be a string")
    raw = path_value.strip()
    if not raw:
        raise PathSecurityError("pdf_path is required")

    candidate = Path(raw).expanduser().resolve()
    roots = [root.resolve() for root in allowed_roots]
    if not any(candidate == root or root in candidate.parents for root in roots):
        raise PathSecurityError("pdf_path is outside allowed directories")
    if not candidate.is_file():
        raise FileNotFoundError(str(candidate))
    return candidate
