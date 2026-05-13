"""Shared ingest curation rules for books and queue pruning."""
from __future__ import annotations

from pathlib import Path

CORE_EXTS = {".md", ".txt", ".rst", ".json", ".jsonl"}
SECONDARY_EXTS = {".pdf", ".epub", ".mobi", ".azw3"}
EXCLUDED_EXTS = {".csv", ".jpg", ".jpeg", ".png", ".gif", ".webp"}

CORE_MARKERS = (
    "manual",
    "handbook",
    "guide",
    "spec",
    "handoff",
    "docs",
    "curated",
    "current",
    "reference",
)

SECONDARY_MARKERS = (
    "learning",
    "notes",
    "_unsorted",
    "fromdocuments",
    "psychology",
    "ai-tech",
)

EXCLUDED_MARKERS = (
    "archive",
    "archives",
    "backup",
    "backups",
    "cache",
    "tmp",
    "temp",
    "export",
    "exports",
    "log",
    "logs",
    "screenshot",
    "screenshots",
)


def _norm(path: str | Path) -> str:
    return str(path).replace("\\", "/").lower()


def score_ingest_candidate(path: str | Path, preview: str = "") -> tuple[int, list[str]]:
    """Score a path for ingest curation.

    Higher scores mean cleaner, more canonical sources. The score is meant to
    be simple enough to apply consistently in audit, queue building, and pruning.
    """
    low = _norm(path)
    ext = Path(low).suffix
    score = 0
    reasons: list[str] = []

    if ext in CORE_EXTS:
        score += 3
        reasons.append(f"text_ext:{ext}")
    elif ext in SECONDARY_EXTS:
        score += 2
        reasons.append(f"book_ext:{ext}")
    elif ext in EXCLUDED_EXTS:
        score -= 4
        reasons.append(f"noise_ext:{ext}")

    if any(marker in low for marker in CORE_MARKERS):
        score += 2
        reasons.append("core_marker")

    if any(marker in low for marker in SECONDARY_MARKERS):
        score -= 1
        reasons.append("secondary_marker")

    if any(marker in low for marker in EXCLUDED_MARKERS):
        score -= 4
        reasons.append("excluded_marker")

    if preview:
        text_len = len(preview.strip())
        if ext == ".pdf":
            if text_len >= 500:
                score += 1
                reasons.append("pdf_text_rich")
            elif text_len < 80:
                score -= 2
                reasons.append("pdf_weak_text")

    return score, reasons


def bucket_for_path(path: str | Path, preview: str = "") -> str:
    """Map a candidate to `core`, `secondary`, or `excluded`."""
    score, _ = score_ingest_candidate(path, preview=preview)
    if score >= 4:
        return "core"
    if score >= 1:
        return "secondary"
    return "excluded"
