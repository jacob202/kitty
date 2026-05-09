"""Keyword-based domain classifier — pure function, no LLM call."""
from functools import lru_cache

DOMAIN_KEYWORDS = {
    "repair": [
        "fix", "repair", "broken", "noise", "leak", "car", "truck", "vehicle",
        "honda", "circuit", "wire", "wiring", "solder", "amp", "speaker",
        "electronics", "schematic", "motor", "engine", "brake", "tire",
        "tool", "volt", "current", "resistance", "capacitor", "resistor",
    ],
    "health": [
        "symptom", "pain", "doctor", "medication", "med", "blood", "test",
        "sleep", "tired", "fatigue", "diagnosis", "condition", "supplement",
        "vitamin", "weight", "diet", "exercise", "fitness", "workout",
        "mental health", "anxiety", "depression", "prescription",
        "headache", "ibuprofen", "aspirin", "tylenol", "advil", "pill",
        "dose", "injury", "hurt", "sick", "nausea", "fever", "cough",
        "heartburn", "allergy", "allergic", "infection", "wound",
    ],
    "research": [
        "research", "find", "look up", "search", "investigate", "what is",
        "how does", "explain", "summarize", "compare", "difference between",
        "article", "paper", "study", "evidence", "source",
    ],
    "code": [
        "code", "build", "implement", "debug", "error", "function", "class",
        "api", "endpoint", "database", "python", "javascript", "typescript",
        "react", "fastapi", "flask", "docker", "git", "deploy", "test",
        "bug", "fix this code", "refactor", "script",
    ],
}


@lru_cache(maxsize=256)
def classify_domain(user_message: str) -> str:
    """Return soul|repair|health|research|code. Defaults to soul."""
    text = user_message.lower()
    scores = {domain: 0 for domain in DOMAIN_KEYWORDS}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[domain] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "soul"
