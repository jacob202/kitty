"""Domain classifier — keyword scorer over the user message.

Returns one of: soul | repair | health | research | code.
Used by context_assembler to pick the system-prompt file and by routes to
pick the LLM model route.
"""

from __future__ import annotations

from functools import lru_cache

from gateway.registry import get_collection_id

DOMAIN_KEYWORDS = {
    "repair": [
        "fix",
        "repair",
        "broken",
        "noise",
        "leak",
        "car",
        "truck",
        "vehicle",
        "honda",
        "circuit",
        "wire",
        "wiring",
        "solder",
        "amp",
        "speaker",
        "electronics",
        "schematic",
        "motor",
        "engine",
        "brake",
        "tire",
        "tool",
        "volt",
        "current",
        "resistance",
        "capacitor",
        "resistor",
    ],
    "health": [
        "symptom",
        "pain",
        "doctor",
        "medication",
        "med",
        "blood",
        "test",
        "sleep",
        "tired",
        "fatigue",
        "diagnosis",
        "condition",
        "supplement",
        "vitamin",
        "weight",
        "diet",
        "exercise",
        "fitness",
        "workout",
        "mental health",
        "anxiety",
        "depression",
        "prescription",
        "headache",
        "ibuprofen",
        "aspirin",
        "tylenol",
        "advil",
        "pill",
        "dose",
        "injury",
        "hurt",
        "sick",
        "nausea",
        "fever",
        "cough",
        "heartburn",
        "allergy",
        "allergic",
        "infection",
        "wound",
    ],
    "research": [
        "research",
        "find",
        "look up",
        "search",
        "investigate",
        "what is",
        "how does",
        "explain",
        "summarize",
        "compare",
        "difference between",
        "article",
        "paper",
        "study",
        "evidence",
        "source",
    ],
    "code": [
        "code",
        "build",
        "implement",
        "debug",
        "error",
        "function",
        "class",
        "api",
        "endpoint",
        "database",
        "python",
        "javascript",
        "typescript",
        "react",
        "fastapi",
        "flask",
        "docker",
        "git",
        "deploy",
        "test",
        "bug",
        "fix this code",
        "refactor",
        "script",
    ],
}


HEALTH_MULTIPLIERS = {
    "blood",
    "symptom",
    "medication",
    "diagnosis",
    "pain",
    "doctor",
    "nurse",
    "hospital",
    "prescription",
}

for _hm in HEALTH_MULTIPLIERS:
    if _hm not in DOMAIN_KEYWORDS["health"]:
        DOMAIN_KEYWORDS["health"].append(_hm)


DOMAIN_SPECIALISTS = {
    "repair": "audio_repair",
    "research": "electronics",
    "soul": "sask_watchdog",
}


def get_specialist(domain: str) -> dict:
    """Return canonical specialist name and collection id for a given domain."""
    specialist_name = DOMAIN_SPECIALISTS.get(domain, DOMAIN_SPECIALISTS["soul"])
    return {
        "name": specialist_name,
        "collection_id": get_collection_id(specialist_name),
    }


def _classify(user_message: str) -> str:
    """Score the message against keyword tables; return the best domain."""
    text_lower = user_message.lower()
    scores = {domain: 0 for domain in DOMAIN_KEYWORDS}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                multiplier = 3 if domain == "health" and kw in HEALTH_MULTIPLIERS else 1
                scores[domain] += multiplier

    max_score = max(scores.values())
    if max_score == 0:
        return "soul"

    best_domains = [d for d, s in scores.items() if s == max_score]
    if "health" in best_domains:
        return "health"
    return best_domains[0]


@lru_cache(maxsize=256)
def classify_domain(user_message: str) -> str:
    """Return soul|repair|health|research|code. Defaults to soul."""
    return _classify(user_message)
