"""The Algorithm — Kitty's explicit reasoning loop.

Every autonomous agent works a goal through six named phases instead of a
free-form ramble:

    OBSERVE → ORIENT → DECIDE → ACT → VERIFY → LEARN

Adapted from Daniel Miessler's PAI "Algorithm" primitive and made
model-agnostic — no Claude/Anthropic assumptions, no external hooks, no
``~/.claude`` paths. It is pure prompt scaffolding plus a phase detector.

This is a DEEP module: the phase model and prompt logic live here; callers
only touch ``frame_prompt()`` and ``detect_phase()``.

Public API:
    PHASES                          ordered tuple of Phase
    PHASE_NAMES                     their names, in order
    frame_prompt(base) -> str       append the phase guide to a system prompt
    detect_phase(text) -> str|None  best-guess phase label from agent text
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Phase:
    """One step of the Algorithm: a name, the question it answers, what to do."""

    name: str
    intent: str
    guidance: str


PHASES: tuple[Phase, ...] = (
    Phase(
        "OBSERVE",
        "What is actually being asked?",
        "Restate the goal in your own words and gather the raw facts and "
        "context. No solutions yet.",
    ),
    Phase(
        "ORIENT",
        "What does it mean?",
        "Frame the problem: constraints, unknowns, assumptions, and what "
        "success would look like.",
    ),
    Phase(
        "DECIDE",
        "What's the plan?",
        "Choose one approach and list the concrete steps. Name the success "
        "criteria you'll check later.",
    ),
    Phase(
        "ACT",
        "Do it.",
        "Execute the chosen step. Show the work — code, commands, or reasoning.",
    ),
    Phase(
        "VERIFY",
        "Did it work?",
        "Check the result against the success criteria from DECIDE. Be honest "
        "about gaps.",
    ),
    Phase(
        "LEARN",
        "What's worth keeping?",
        "Capture the one durable lesson or note, then give your final answer.",
    ),
)

PHASE_NAMES: tuple[str, ...] = tuple(p.name for p in PHASES)

_MARKER = re.compile(r"PHASE:\s*([A-Za-z]+)", re.IGNORECASE)


def frame_prompt(base: str) -> str:
    """Append the Algorithm phase guide to a base system prompt."""
    lines = [
        base,
        "",
        "## The Algorithm",
        "Work the goal through these phases in order. Label each section with a "
        "`## PHASE: NAME` heading so your progress is legible:",
    ]
    for i, p in enumerate(PHASES, 1):
        lines.append(f"{i}. **{p.name}** — {p.intent} {p.guidance}")
    lines.append(
        "Skip a phase only if it genuinely doesn't apply. Loop back to an "
        "earlier phase if VERIFY surfaces a problem."
    )
    return "\n".join(lines)


def detect_phase(text: str) -> str | None:
    """Best-guess the phase a chunk of agent output is in.

    Prefers an explicit ``PHASE: NAME`` marker — the last one wins, since a
    single response may span several phases. Returns ``None`` when no known
    phase marker is present.
    """
    if not text:
        return None
    for name in reversed(_MARKER.findall(text)):
        upper = name.upper()
        if upper in PHASE_NAMES:
            return upper
    return None
