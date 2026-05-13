"""Domain classifier with swappable backends.

Default backend: keyword scorer. Drop in an embedding-based or LLM-based
classifier by passing a ``DomainClassifier`` instance to ``classify_domain()``.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Optional

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


HEALTH_MULTIPLIERS = {
     "blood", "symptom", "medication", "diagnosis", "pain",
     "doctor", "nurse", "hospital", "prescription"
}

for _hm in HEALTH_MULTIPLIERS:
    if _hm not in DOMAIN_KEYWORDS["health"]:
        DOMAIN_KEYWORDS["health"].append(_hm)


class DomainClassifier(ABC):
    """Interface for domain classification backends."""

    @abstractmethod
    def classify(self, text: str) -> str:
        """Return domain string (soul|repair|health|research|code)."""


class KeywordClassifier(DomainClassifier):
    """Default keyword-scoring classifier."""

    def classify(self, text: str) -> str:
        text_lower = text.lower()
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


_default_classifier: Optional[DomainClassifier] = None


def _get_default_classifier() -> DomainClassifier:
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = KeywordClassifier()
    return _default_classifier


@lru_cache(maxsize=256)
def _classify_cached(user_message: str, classifier_id: str) -> str:
    """Cached classification. classifier_id distinguishes backends."""
    return _get_default_classifier().classify(user_message)


def classify_domain(user_message: str, classifier: Optional[DomainClassifier] = None) -> str:
    """Return soul|repair|health|research|code. Defaults to soul.

    Parameters
    ----------
    user_message : str
        The message to classify.
    classifier : DomainClassifier, optional
        Custom classifier backend. When None, uses the default
        KeywordClassifier. Passing a custom instance bypasses the LRU cache.
    """
    if classifier is None:
        return _classify_cached(user_message, "default")
    return classifier.classify(user_message)
