#!/usr/bin/env python3
"""Preference-pair collection for lightweight RLHF data gathering."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STORE = Path("data/rlhf/preferences.jsonl")


@dataclass(frozen=True)
class ResponseOption:
    id: str
    label: str
    text: str


@dataclass(frozen=True)
class PreferencePair:
    query: str
    chosen_id: str
    rejected_id: str
    chosen_text: str
    rejected_text: str
    timestamp: str
    session_id: str
    metadata: dict[str, object]


class PreferenceCollector:
    """Create deterministic response options and store chosen-vs-rejected pairs."""

    def __init__(self, store_path: Path | str = DEFAULT_STORE):
        self.store_path = Path(store_path)

    def make_options(self, query: str, count: int = 3) -> list[ResponseOption]:
        query = (query or "").strip()
        if not query:
            raise ValueError("query is required")
        if count < 2 or count > 4:
            raise ValueError("count must be between 2 and 4")

        templates = [
            ("direct", "Start with the likely cause, then give the next concrete test."),
            ("checklist", "Break it into a short checklist with observable pass/fail points."),
            ("safety", "Call out safety constraints first, then continue with practical steps."),
            ("teach-back", "Explain the reasoning simply enough to reuse next time."),
        ]

        return [
            ResponseOption(
                id=f"opt-{idx + 1}",
                label=label,
                text=f"For: {query}\nApproach: {instruction}",
            )
            for idx, (label, instruction) in enumerate(templates[:count])
        ]

    def store_preference(
        self,
        query: str,
        options: Iterable[ResponseOption | dict[str, str]],
        chosen_id: str,
        metadata: dict[str, object] | None = None,
        session_id: str | None = None,
    ) -> list[PreferencePair]:
        normalized = [self._normalize_option(option) for option in options]
        if len(normalized) < 2:
            raise ValueError("at least two response options are required")

        chosen = next((option for option in normalized if option.id == chosen_id), None)
        if not chosen:
            raise ValueError("chosen_id must match one response option")

        timestamp = datetime.now(timezone.utc).isoformat()
        session = session_id or str(uuid.uuid4())
        pairs = [
            PreferencePair(
                query=query,
                chosen_id=chosen.id,
                rejected_id=option.id,
                chosen_text=chosen.text,
                rejected_text=option.text,
                timestamp=timestamp,
                session_id=session,
                metadata=metadata or {},
            )
            for option in normalized
            if option.id != chosen.id
        ]

        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with self.store_path.open("a", encoding="utf-8") as fh:
            for pair in pairs:
                fh.write(json.dumps(asdict(pair), ensure_ascii=False) + "\n")

        return pairs

    def _normalize_option(self, option: ResponseOption | dict[str, str]) -> ResponseOption:
        if isinstance(option, ResponseOption):
            return option
        return ResponseOption(
            id=str(option["id"]),
            label=str(option.get("label", option["id"])),
            text=str(option["text"]),
        )
