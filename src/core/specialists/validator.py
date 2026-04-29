"""
Specialist answer validator — check for source/citation.
"""
from typing import Dict


def validate_answer(specialist: str, answer: str, source: str = "") -> Dict:
    """
    Validate a specialist answer.
    Returns: {"valid": bool, "confidence": float, "issues": list}
    """
    issues = []
    confidence = 0.8  # default

    # Rule: device-specific, medical, procedural, or spec claims need source
    if specialist in ("kelly", "mike", "alex"):
        if not source and "source not found" not in answer.lower():
            issues.append("Missing source for specialist answer")
            confidence -= 0.3

    # Rule: answer should not be too vague
    if len(answer.split()) < 5:
        issues.append("Answer too short or vague")
        confidence -= 0.2

    # Rule: answer should end with a next step or question
    if not any(
        answer.strip().endswith(w)
        for w in (".", "?", "!", "what", "how", "next", "try")
    ):
        issues.append("Answer lacks clear ending or next step")
        confidence -= 0.1

    confidence = max(0.0, min(1.0, confidence))
    valid = confidence >= 0.5 and len(issues) == 0

    return {
        "valid": valid,
        "confidence": confidence,
        "issues": issues,
        "answer": answer,
        "source": source or "no source provided",
    }
