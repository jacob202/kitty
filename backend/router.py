"""
Specialist router — classifies incoming messages and selects
the right specialist prompt + model tier.
"""

from pathlib import Path
from .config import settings, SOUL_DIR

SOUL_FILE = SOUL_DIR / "kitty.md"
SPECIALISTS = {
    "researcher": SOUL_DIR / "specialists" / "researcher.md",
    "coder":      SOUL_DIR / "specialists" / "coder.md",
    "creative":   SOUL_DIR / "specialists" / "creative.md",
    "companion":  SOUL_DIR / "specialists" / "companion.md",
    "analyst":    SOUL_DIR / "specialists" / "analyst.md",
}

# Keywords that trigger each specialist (fast pre-filter before LLM routing)
_SIGNALS: dict[str, list[str]] = {
    "coder": [
        "code", "bug", "error", "function", "class", "debug", "script",
        "python", "javascript", "typescript", "refactor", "implement",
        "api", "database", "sql", "git", "deploy", "build", "test",
    ],
    "researcher": [
        "research", "find", "look up", "search", "what is", "explain",
        "how does", "why does", "summarize", "compare",
        "difference between", "according to", "source", "citation",
    ],
    "creative": [
        "write", "story", "poem", "creative", "brainstorm", "idea",
        "design", "imagine", "fiction", "character", "plot", "lyrics",
        "music", "art", "concept", "invent", "come up with",
    ],
    "companion": [
        "feeling", "feel", "sad", "happy", "anxious", "stressed",
        "tired", "excited", "lonely", "struggling", "need to talk",
        "just want", "vent", "hard day", "miss", "relationship",
    ],
    "analyst": [
        "should i", "help me think", "decision", "analyze", "pros and cons",
        "trade off", "tradeoff", "evaluate", "comparing", "which is better",
        "strategy", "plan", "thinking about", "weighing", "advice on",
        "make sense", "worth it", "good idea", "bad idea",
    ],
}

# Model routing by specialist
_MODEL_MAP: dict[str, str] = {
    "coder":      settings.opus_model,    # precision matters
    "analyst":    settings.opus_model,    # reasoning matters
    "researcher": settings.sonnet_model,
    "creative":   settings.sonnet_model,
    "companion":  settings.sonnet_model,
    "general":    settings.sonnet_model,
}

_MAX_TOKENS_MAP: dict[str, int] = {
    "coder":      settings.opus_max_tokens,
    "analyst":    settings.opus_max_tokens,
    "researcher": settings.sonnet_max_tokens,
    "creative":   settings.sonnet_max_tokens,
    "companion":  settings.sonnet_max_tokens,
    "general":    settings.sonnet_max_tokens,
}


def _load(path: Path) -> str:
    """Read a soul/specialist file; returns empty string if file is missing."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def classify(message: str) -> str:
    """Return specialist name based on keyword signals. Falls back to 'general'."""
    lower = message.lower()
    scores: dict[str, int] = {k: 0 for k in _SIGNALS}
    for specialist, keywords in _SIGNALS.items():
        for kw in keywords:
            if kw in lower:
                scores[specialist] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general"


def build_system_prompt(specialist: str, memory_block: str, profile_block: str) -> str:
    """Assemble the full system prompt for a given specialist."""
    soul = _load(SOUL_FILE)
    extension = _load(SPECIALISTS[specialist]) if specialist in SPECIALISTS else ""

    sections = [soul]
    if extension:
        sections.append(extension)
    if profile_block:
        sections.append(profile_block)
    if memory_block:
        sections.append(memory_block)

    return "\n\n---\n\n".join(sections)


def get_model(specialist: str) -> str:
    """Return the Anthropic model ID for the given specialist."""
    return _MODEL_MAP.get(specialist, settings.sonnet_model)


def get_max_tokens(specialist: str) -> int:
    """Return the max-token budget for the given specialist."""
    return _MAX_TOKENS_MAP.get(specialist, settings.sonnet_max_tokens)
