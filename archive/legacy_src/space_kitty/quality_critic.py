"""
Response Quality Critic — SOUL-aligned review.
Runs on drafts >200 words or complex responses.
"""
from typing import Dict, List


def _check_directness(draft: str) -> bool:
    """Check if draft is direct and actionable."""
    vague = ["might", "maybe", "perhaps", "could be", "it is possible"]
    return not any(w in draft.lower() for w in vague)


def _check_padding(draft: str) -> bool:
    """Check for unnecessary padding."""
    lines = draft.splitlines()
    empty_ratio = sum(1 for l in lines if not l.strip()) / max(len(lines), 1)
    return empty_ratio < 0.3  # Less than 30% empty lines


def _check_actionable(draft: str) -> bool:
    """Check if draft has clear next step."""
    action_words = ["next", "then", "run", "execute", "implement", "create", "update"]
    return any(w in draft.lower() for w in action_words)


def _check_soul_alignment(draft: str, soul_context: str) -> bool:
    """Check alignment with SOUL.md principles."""
    if not soul_context:
        return True  # No context to check against
    # Simple keyword alignment check
    soul_themes = ["focus", "direct", "simple", "build", "controlled"]
    matches = sum(1 for t in soul_themes if t in draft.lower())
    return matches >= 2  # At least 2 theme matches


def _check_validation(draft: str) -> bool:
    """Check if draft includes validation when proposing implementation."""
    has_code = "```" in draft or "def " in draft or "import " in draft
    has_validation = "test" in draft.lower() or "validate" in draft.lower() or "check" in draft.lower()
    if has_code:
        return has_validation
    return True


def _check_scope_creep(draft: str) -> bool:
    """Check for scope creep indicators."""
    creep = ["also", "while we're at it", "we could also", "another thing", "by the way"]
    return not any(w in draft.lower() for w in creep)


def review_draft(draft: str, soul_context: str = "") -> Dict:
    """
    Review a draft response.
    Returns: {"score": int, "flags": list, "refined": str}
    """
    flags = []
    score = 10

    if not _check_directness(draft):
        flags.append("indirect or vague language")
        score -= 2

    if not _check_padding(draft):
        flags.append("excessive padding or empty lines")
        score -= 1

    if not _check_actionable(draft):
        flags.append("no clear next action or step")
        score -= 2

    if not _check_soul_alignment(draft, soul_context):
        flags.append("poor alignment with SOUL.md")
        score -= 2

    if not _check_validation(draft):
        flags.append("missing validation for code/implementation")
        score -= 2

    if not _check_scope_creep(draft):
        flags.append("potential scope creep")
        score -= 1

    score = max(0, min(10, score))

    refined = draft
    if flags:
        refined += "\n\n[Critic suggestions: " + "; ".join(flags) + "]"

    return {"score": score, "flags": flags, "refined": refined}


def extract_learned_rule(draft: str, user_correction: str) -> str:
    """
    Extract a learned rule from user correction.
    Rule goes to docs/SOUL_LEARNED_RULES.md as pending_review.
    """
    if not user_correction:
        return ""
    # Simple extraction: treat correction as rule
    return f"Rule: {user_correction.strip()}"
