"""
Alex (Code Specialist).
"""
from typing import Dict


class KittyCoderSpecialist:
    """Code specialist that cites sources."""

    def __init__(self, name: str = "KittyCoder", domain: str = "code", knowledge_base_path: str = ""):
        self.name = name
        self.domain = domain
        self.knowledge_base_path = knowledge_base_path

    def answer(self, query: str) -> Dict:
        """Answer code questions with source citation."""
        if "python" in query.lower():
            return {
                "answer": "Use list comprehension for concise loops.",
                "source": "Python docs: list comprehensions",
                "confidence": 0.9,
            }
        if "javascript" in query.lower() or "js" in query.lower():
            return {
                "answer": "Use map() or forEach() for array iteration.",
                "source": "MDN: Array methods",
                "confidence": 0.8,
            }
        return {
            "answer": "I don't have a specific code answer for that.",
            "source": "no source found",
            "confidence": 0.3,
        }

    def explain(self, code: str) -> Dict:
        """Explain what code does."""
        return {
            "explanation": f"This code: {code[:50]}...",
            "source": "Direct code analysis",
            "confidence": 0.7,
        }
