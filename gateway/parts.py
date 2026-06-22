"""Parts system — Kitty's internal council.

Two modes:
- External toggle: caller sets parts_mode=True, every response shows the debate
- Context-triggered: should_surface_parts() detects when to auto-show it

The parts are: Skeptic, Champion, Pragmatist, Observer.
"""

from gateway.prompts import PARTS_COUNCIL_PROMPT

# Triggers that suggest a parts-mode response adds value
_HIGH_STAKES_TRIGGERS = [
    "should i", "should we", "deciding", "decision", "choose", "choice",
    "worth it", "is it worth", "commit", "quit", "leave", "stay",
    "invest", "buy", "sell", "switch", "change everything",
]

_CHALLENGE_TRIGGERS = [
    "i think", "i believe", "i know", "obviously", "clearly", "definitely",
    "always", "never", "everyone", "no one", "the only", "the best",
    "for sure", "100%", "guaranteed",
]

_SOCRATIC_TRIGGERS = [
    "what do you think", "am i right", "is this a good idea", "does this make sense",
    "validate", "confirm", "agree", "tell me i'm", "reassure",
]


def should_surface_parts(message: str) -> bool:
    """Return True when the context warrants auto-surfacing the parts debate.

    Triggers: high-stakes decisions, strong assertions that invite challenge,
    explicit requests for validation/agreement.
    """
    text = message.lower()

    high_stakes = any(t in text for t in _HIGH_STAKES_TRIGGERS)
    assertion = any(t in text for t in _CHALLENGE_TRIGGERS)
    validation_seek = any(t in text for t in _SOCRATIC_TRIGGERS)

    # Surface when: decision + assertion, or seeking validation
    return (high_stakes and assertion) or validation_seek


def build_parts_system_prompt(base_prompt: str) -> str:
    """Append the parts debate instruction to an existing system prompt."""
    return base_prompt + "\n\n" + PARTS_COUNCIL_PROMPT
