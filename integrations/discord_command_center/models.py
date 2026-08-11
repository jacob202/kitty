from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiffAudit:
    files: int
    insertions: int
    deletions: int
    status_lines: tuple[str, ...] = ()

    @property
    def dirty(self) -> bool:
        return self.files > 0


@dataclass(frozen=True)
class ProgressEvent:
    kind: str
    message: str
    exit_code: int | None = None
    code: str | None = None
