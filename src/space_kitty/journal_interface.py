"""Minimal journal interface compatibility shim."""

from __future__ import annotations


class JournalInterface:
    def log(self, *_args, **_kwargs):
        return None

    def detect_patterns(self) -> list[str]:
        return []
