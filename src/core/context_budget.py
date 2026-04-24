"""Typed, budgeted context assembly for LLM prompts.

Replaces additive prompt stuffing with explicit slot allocation.
Slots have priority (lower number = higher priority). When the total
budget is exceeded, lower-priority slots are truncated or dropped first.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class ContextSlot(IntEnum):
    """Context slots in priority order (lower = higher priority)."""
    IDENTITY = 1       # core persona, communication strategy
    CORRECTIONS = 2    # user corrections — always high priority
    PROJECT = 3        # project-level facts
    RECENT = 4         # recent context snapshots, emotional state
    EPHEMERAL = 5      # behavioral patterns, working memory for this turn


# Preset profiles: (total_chars, {slot: budget})
_PRESETS: dict[str, tuple[int, dict[ContextSlot, int]]] = {
    "compact": (800, {
        ContextSlot.IDENTITY: 200,
        ContextSlot.CORRECTIONS: 300,
        ContextSlot.RECENT: 200,
        # PROJECT and EPHEMERAL dropped entirely
    }),
    "balanced": (2000, {
        ContextSlot.IDENTITY: 500,
        ContextSlot.CORRECTIONS: 400,
        ContextSlot.PROJECT: 300,
        ContextSlot.RECENT: 500,
        ContextSlot.EPHEMERAL: 200,
    }),
    "verbose": (4000, {
        ContextSlot.IDENTITY: 800,
        ContextSlot.CORRECTIONS: 800,
        ContextSlot.PROJECT: 600,
        ContextSlot.RECENT: 1000,
        ContextSlot.EPHEMERAL: 500,
    }),
}

# Default char budget per slot (backward compat)
_SLOT_DEFAULTS: dict[ContextSlot, int] = dict(_PRESETS["balanced"][1])


@dataclass
class ContextBudget:
    preset: str = "balanced"
    _slots: dict[ContextSlot, str] = field(default_factory=dict, init=False)

    @property
    def total_chars(self) -> int:
        return _PRESETS.get(self.preset, _PRESETS["balanced"])[0]

    @property
    def _slot_budgets(self) -> dict[ContextSlot, int]:
        return _PRESETS.get(self.preset, _PRESETS["balanced"])[1]

    def add(self, slot: ContextSlot, content: str) -> None:
        """Add content to a slot. Silently ignores slots not in the current preset."""
        if slot not in self._slot_budgets:
            return  # Slot disabled by preset
        stripped = content.strip()
        if stripped:
            self._slots[slot] = stripped

    def assemble(self) -> str:
        """Build the final context string, respecting priority and total budget."""
        if not self._slots:
            return ""

        remaining = self.total_chars
        parts: list[str] = []

        sep = "\n\n"
        for slot in sorted(ContextSlot):
            content = self._slots.get(slot, "")
            if not content:
                continue
            # Reserve space for separator if this isn't the first part
            sep_cost = len(sep) if parts else 0
            available = remaining - sep_cost
            slot_budget = min(self._slot_budgets.get(slot, 200), available)
            if slot_budget <= 0:
                break
            chunk = content[:slot_budget]
            parts.append(chunk)
            remaining -= len(chunk) + sep_cost

        return "\n\n".join(parts)
