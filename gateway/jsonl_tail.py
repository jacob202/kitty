"""Bounded helpers for append-only JSONL hot paths."""
from __future__ import annotations

from pathlib import Path


def read_tail_lines(
    path: Path,
    *,
    limit: int,
    max_bytes: int = 4 * 1024 * 1024,
    chunk_bytes: int = 64 * 1024,
) -> list[str]:
    """Return at most ``limit`` complete UTF-8 lines from the end of ``path``.

    The reader seeks from EOF and never reads more than ``max_bytes``. If the
    byte budget begins in the middle of a line, that partial first line is
    discarded rather than parsed as corrupt JSON.
    """
    if limit <= 0 or max_bytes <= 0 or not path.exists():
        return []
    with path.open("rb") as fh:
        fh.seek(0, 2)
        pos = fh.tell()
        chunks: list[bytes] = []
        newline_count = 0
        remaining = max_bytes
        while pos > 0 and remaining > 0 and newline_count <= limit:
            size = min(chunk_bytes, pos, remaining)
            pos -= size
            fh.seek(pos)
            chunk = fh.read(size)
            chunks.append(chunk)
            newline_count += chunk.count(b"\n")
            remaining -= size

    data = b"".join(reversed(chunks))
    lines = data.splitlines()
    if pos > 0 and data and not data.startswith(b"\n") and lines:
        lines = lines[1:]
    return [line.decode("utf-8", errors="replace") for line in lines[-limit:]]
