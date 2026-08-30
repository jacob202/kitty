"""Memory policy — consentful, scoped, decayed memory for continuity, not surveillance.

Rule-based classification and filtering so Kitty remembers what helps Jacob
continue and does not repeatedly foreground sensitive/support context unless
directly relevant or explicitly requested.

Public surface:
- :func:`classify` — classify an Item into a MemoryClass
- :func:`should_surface` — whether an item should appear in assembled context
- :func:`rewrite_sensitive_summary` — rewrite psych summaries as support preferences
- :func:`memory_display_reason` — one-line explanation for surfacing
- :class:`MemoryClass` — the classification enum
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from gateway.memory_graph import Item, Source

logger = __import__("logging").getLogger("kitty.memory_policy")


class MemoryClass(str, Enum):
    """The mode/classification of a memory item.

    Values are ordered roughly from "most likely to surface" to "least likely."
    """

    PINNED = "pinned"
    WORKING_CONTEXT = "working_context"
    PREFERENCE = "preference"
    CREATIVE_THREAD = "creative_thread"
    SENSITIVE_SUPPORT = "sensitive_support"
    ARCHIVED = "archived"
    BLOCKED = "blocked"

    def __str__(self) -> str:
        return self.value


# ── Keywords used for rule-based classification ──────────────────────────────

_SENSITIVE_TERMS: tuple[str, ...] = (
    "recovery", "relapse", "addiction", "grief", "trauma", "crisis",
    "suicidal", "self-harm", "overdose", "detox", "rehab", "withdrawal",
    "sobriety", "drunk", "high", "craving", "spiral", "shame",
    "therapist", "therapy session", "counselling", "psychiatrist",
    "hospital", "emergency", "ambulance", "mental health",
    "breakdown", "panic attack", "anxiety attack", "ptsd",
    "intrusive thought", "flashback",
)

_PREFERENCE_TERMS: tuple[str, ...] = (
    "prefer", "preference", "usually like", "i like when", "i hate when",
    "works best", "better when", "my workflow", "my style",
)

_CREATIVE_TERMS: tuple[str, ...] = (
    "poem", "poetry", "painting", "drawing", "sketch", "write", "writing",
    "story", "character", "worldbuild", "music", "song", "melody",
    "image prompt", "generate", "mascot", "art", "creative",
    "motif", "aesthetic", "palette", "tone", "vibe", "design idea",
)

_WORKING_CONTEXT_TERMS: tuple[str, ...] = (
    "current project", "building", "implementing", "working on",
    "next step", "todo", "unfinished", "in progress", "draft",
    "decision made", "decided", "chose", "settled",
)

# ── Public API ───────────────────────────────────────────────────────────────-


def classify(item: Item, query: str = "") -> MemoryClass:
    """Classify a memory Item into a MemoryClass using rule-based heuristics.

    Priority order (first match wins):
      1. Pinned — metadata or explicit pin marker
      2. Blocked — metadata or ``keep_quiet``/``blocked`` tag
      3. Archived — metadata archive flag
      4. Sensitive support — keywords or sensitivity tags
      5. Working context — project/building/decision keywords
      6. Preference — likes/workflow keywords
      7. Creative thread — art/music/writing keywords
      8. Default — preference (safe fallback)
    """
    # Check metadata overrides first
    tags = _get_tags(item.metadata)

    if item.metadata.get("pinned") is True or "pinned" in tags:
        return MemoryClass.PINNED
    if item.metadata.get("blocked") is True or "keep_quiet" in tags or "blocked" in tags:
        return MemoryClass.BLOCKED
    if item.metadata.get("archived") is True or "archived" in tags:
        return MemoryClass.ARCHIVED

    text_lower = item.text.lower()
    source = item.source

    # Sensitivity: high-sensitivity metadata or keyword match
    if item.metadata.get("sensitivity") == "high" or _has_any(text_lower, _SENSITIVE_TERMS):
        return MemoryClass.SENSITIVE_SUPPORT

    # Creative threads from known creative sources
    if source in (Source.JOURNAL, Source.MEMORY) and _has_any(text_lower, _CREATIVE_TERMS):
        return MemoryClass.CREATIVE_THREAD

    # Working context: project/decision/build keywords
    if _has_any(text_lower, _WORKING_CONTEXT_TERMS):
        return MemoryClass.WORKING_CONTEXT

    # Preferences
    if _has_any(text_lower, _PREFERENCE_TERMS):
        return MemoryClass.PREFERENCE

    # Creative from other sources
    if _has_any(text_lower, _CREATIVE_TERMS):
        return MemoryClass.CREATIVE_THREAD

    return MemoryClass.PREFERENCE


def should_surface(
    item: Item,
    query: str = "",
    mode: str = "default",
) -> bool:
    """Whether this item should be included in the assembled context.

    Args:
        item: The memory item to evaluate.
        query: The user's current message (used for relevance matching).
        mode: Context assembly mode — ``"default"``, ``"creative"``,
            or ``"support"``.

    Rules:
        - Pinned items always surface.
        - Blocked items never surface unless directly queried by keyword.
        - Archived items never surface unless directly queried.
        - Sensitive support items are suppressed in default mode unless
          the query directly mentions a sensitive term.
        - All other classes surface normally.
    """
    cls = classify(item, query)
    query_terms = set(query.lower().split())

    if cls == MemoryClass.PINNED:
        return True

    if cls == MemoryClass.BLOCKED:
        return False

    if cls == MemoryClass.ARCHIVED:
        return False

    if cls == MemoryClass.SENSITIVE_SUPPORT:
        if mode == "support":
            return True
        if _query_matches_sensitive(query_terms):
            return True
        return False

    return True


def rewrite_sensitive_summary(text: str) -> str:
    """Rewrite a psych/identity summary into a support-preference statement.

    Transforms patterns like:
        "Jacob has been spiraling about X"
        -> "Jacob prefers practical, positive support around X."

    Returns the original text unchanged if no rewrite is needed.
    """
    text_stripped = text.strip()

    patterns = [
        (r"Jacob has been spiraling about (.+)", r"Jacob prefers practical support around \1."),
        (r"Jacob has been struggling with (.+)", r"Jacob prefers practical support around \1."),
        (r"Jacob has been focused on recovery", r"Jacob values recovery support that stays practical and positive unless he explicitly asks for a deeper frame."),
        (r"Jacob keeps struggling with (.+)", r"Jacob prefers support that acknowledges \1 without making it the center of every interaction."),
        (r"Jacob has been dealing with (.+)", r"Jacob prefers practical positivity around \1 unless he explicitly asks for more depth."),
        (r"Jacob has been going through (.+)", r"Jacob is navigating \1 and prefers support that is steady, not dramatized."),
    ]

    rewritten = text_stripped
    for pattern, replacement in patterns:
        if re.search(pattern, rewritten, re.IGNORECASE):
            rewritten = re.sub(pattern, replacement, rewritten, count=1, flags=re.IGNORECASE)

    # Catch-all for any "Jacob has been" + negative framing
    if rewritten == text_stripped and re.search(
        r"Jacob has been (?:focused on|thinking about|dealing with|working through) (recovery|spiral|relapse|addiction|grief|trauma|health)",
        rewritten,
        re.IGNORECASE,
    ):
        rewritten = re.sub(
            r"Jacob has been .+",
            "Jacob values recovery support that stays practical and positive unless he explicitly asks for a deeper frame.",
            rewritten,
            count=1,
        )

    return rewritten


def memory_display_reason(item: Item, query: str = "") -> str:
    """Short, one-line explanation of why this item is being surfaced.

    Returns a string like:
        "Pinned memory" / "Active project context" / "Preference" / "Creative thread"
    """
    cls = classify(item, query)
    reasons = {
        MemoryClass.PINNED: "Pinned memory",
        MemoryClass.WORKING_CONTEXT: "Active project context",
        MemoryClass.PREFERENCE: "Preference",
        MemoryClass.CREATIVE_THREAD: "Creative thread",
        MemoryClass.SENSITIVE_SUPPORT: "Support context",
        MemoryClass.ARCHIVED: "Archived",
        MemoryClass.BLOCKED: "Blocked",
    }
    return reasons.get(cls, "Memory")


# ── Internals ────────────────────────────────────────────────────────────────


def _get_tags(metadata: dict[str, Any]) -> list[str]:
    tags = metadata.get("tags", [])
    if isinstance(tags, list):
        return [str(t).lower() for t in tags]
    if isinstance(tags, str):
        return [tags.lower()]
    return []


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _query_matches_sensitive(query_terms: set[str]) -> bool:
    """Return True if the user's query explicitly references a sensitive topic."""
    sensitive_queries: tuple[str, ...] = (
        "recovery", "relapse", "addiction", "grief", "trauma", "crisis",
        "therapy", "therapist", "mental health", "counselling",
        "sober", "sobriety", "detox", "rehab",
        "spiral", "shame", "panic", "anxiety", "ptsd",
    )
    return any(q in sensitive_queries for q in query_terms)


__all__ = [
    "MemoryClass",
    "classify",
    "should_surface",
    "rewrite_sensitive_summary",
    "memory_display_reason",
]
