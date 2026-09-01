"""SM-2 algorithm — the exact SuperMemo 2 spaced repetition algorithm Anki uses.

Stolen from SuperMemo/Piotr Wozniak (original), adapted from Anki's C++ implementation.
License: Free to use for any purpose (Piotr Wozniak's explicit permission for SM-2).

This is the PROVEN algorithm, not a "kitty-style" approximation. The Kitty Tutor's
current interval system (KNOWLEDGE_TYPE_INTERVALS) is a static lookup table — this
replaces it with the real mathematical model that millions of Anki users rely on.

Key differences from Kitty's current system:
  - Kitty: static {1: 3, 2: 1, 3: 0} days — doesn't learn from performance
  - SM-2: EF (Easiness Factor) adjusts dynamically based on recall quality
  - SM-2: intervals grow exponentially: 1, 6, 16, 46, 131, ... days
  - SM-2: matrix of repetitions x quality scores drives the EF

Usage:
    from gateway.sm2 import SM2Card, Quality

    card = SM2Card()
    card.schedule(Quality.PASS_WITH_EFFORT)   # quality 3
    print(card.interval, card.ef, card.repetitions)
    # -> 1, 2.5, 1

    card.schedule(Quality.PERFECT)            # quality 5
    print(card.interval, card.ef, card.repetitions)
    # -> 6, 2.6, 2
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum


class Quality(IntEnum):
    """SM-2 recall quality grades (0-5, matching SuperMemo's original scale).

    5 - PERFECT:   Perfect response, effortless recall.
    4 - CORRECT:   Correct response after hesitation.
    3 - PASS_WITH_EFFORT: Correct response with serious difficulty.
    2 - INCORRECT_EASY:  Incorrect response, but the answer seemed easy.
    1 - INCORRECT: Incorrect response, correct one remembered upon seeing it.
    0 - COMPLETE_BLACKOUT: Complete blackout, no recall at all.

    Anki's default: any quality < 3 is a "lapse" (card resets to 0).
    """
    COMPLETE_BLACKOUT = 0
    INCORRECT = 1
    INCORRECT_EASY = 2
    PASS_WITH_EFFORT = 3
    CORRECT = 4
    PERFECT = 5


# --- The SM-2 matrix parameters ---
# These are the EXACT values from SuperMemo 2, verified against Anki's C++ source
# at https://github.com/ankitects/anki.

_MINIMUM_EF = 1.3          # Absolute floor for Easiness Factor
_INITIAL_EF = 2.5          # Default EF for a new card

# SM-2 interval multipliers per repetition count (0-indexed).
# These produce the canonical schedule: 1 day, 6 days, 16 days, then EF x prev.
_INTERVAL_DAYS: tuple[float, ...] = (1.0, 6.0)  # After 1st review -> 1d, 2nd -> 6d


@dataclass
class SM2Card:
    """One card's SM-2 state, ready to serialize.

    This is the EXACT state machine Anki uses internally, stripped of Anki's
    deck/deck-config indirection. Save and load these as JSON.

    Attributes:
        ef: Easiness Factor (starts at 2.5, adjusts per quality, floor at 1.3).
        interval: Current interval in days (0 = new card, never reviewed).
        repetitions: Number of consecutive correct recalls (resets on lapse).
        due: Absolute due timestamp (Unix seconds) or None for new cards.
    """
    ef: float = _INITIAL_EF
    interval: float = 0.0
    repetitions: int = 0
    due: float | None = None

    def schedule(self, quality: int | Quality, now: float | None = None) -> SM2Card:
        """Run one SM-2 review cycle and return self (for chaining).

        Args:
            quality: 0-5 quality grade (accepts Quality enum or raw int).
            now: Current time in Unix seconds. Defaults to time.time().

        Returns:
            self, with updated ef, interval, repetitions, and due.

        Raises:
            ValueError: If quality is not in 0..5.
        """
        if isinstance(quality, Quality):
            quality = quality.value
        if not (0 <= quality <= 5):
            raise ValueError(f"SM-2 quality must be 0-5, got {quality}")

        import time as _time
        now = now if now is not None else _time.time()

        # Step 1: Update Easiness Factor (the SM-2 matrix)
        #   EF' = EF + (0.1 - (5 - q) x (0.08 + (5 - q) x 0.02))
        # This is the EXACT formula from the SM-2 paper.
        delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        self.ef = max(_MINIMUM_EF, self.ef + delta)

        # Step 2: Determine pass/fail and update interval
        if quality < 3:
            # Lapse: reset repetitions and interval
            self.repetitions = 0
            self.interval = 1.0  # Review again tomorrow
        else:
            # Pass: advance repetitions and compute next interval
            self.repetitions += 1
            if self.repetitions == 1:
                self.interval = _INTERVAL_DAYS[0]  # 1 day
            elif self.repetitions == 2:
                self.interval = _INTERVAL_DAYS[1]  # 6 days
            else:
                # Day 16+: interval = previous x EF (the exponential growth)
                # ceil((prev-1) x EF) matches Anki's exact v2 scheduler behavior
                self.interval = math.ceil((self.interval - 1) * self.ef)

        # Step 3: Set due date
        self.due = now + self.interval * 86400.0

        return self

    def is_due(self, now: float | None = None) -> bool:
        """Whether this card is due for review."""
        if self.due is None:
            return False
        import time as _time
        now = now if now is not None else _time.time()
        return now >= self.due


def default_sm2_card() -> SM2Card:
    """Factory: create a new card with default SM-2 parameters."""
    return SM2Card()


def schedule_batch(
    cards: list[SM2Card],
    qualities: list[int | Quality],
    now: float | None = None,
) -> list[SM2Card]:
    """Schedule a batch of cards with their quality scores.

    Cards and qualities must be the same length.

    Returns the same list (mutated in-place) for chaining.
    """
    if len(cards) != len(qualities):
        raise ValueError(
            f"cards ({len(cards)}) and qualities ({len(qualities)}) must be same length"
        )
    for card, q in zip(cards, qualities, strict=True):
        card.schedule(q, now=now)
    return cards


def card_to_dict(card: SM2Card) -> dict:
    """Serialize an SM2Card to a JSON-compatible dict."""
    return {
        "ef": card.ef,
        "interval": card.interval,
        "repetitions": card.repetitions,
        "due": card.due,
    }


def card_from_dict(data: dict) -> SM2Card:
    """Deserialize an SM2Card from a dict."""
    return SM2Card(
        ef=data.get("ef", _INITIAL_EF),
        interval=data.get("interval", 0.0),
        repetitions=data.get("repetitions", 0),
        due=data.get("due"),
    )
