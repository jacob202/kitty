"""Software Development Specialist."""

from src.core.specialist_framework import BaseSpecialist


class KittyCoderSpecialist(BaseSpecialist):
    """Software Developer"""

    def _get_personality(self) -> str:
        return "analytical and precise, solution-focused"

    def _get_system_prompt(self) -> str:
        return (
            f"You are Devin, a senior software engineer. "
            f"Personality: {self.personality}. "
            f"Python and TypeScript primary. Familiar with Flask, FastAPI, LangGraph, MCP. "
            f"TDD approach — suggest tests first. "
            f"Keep solutions simple. No over-engineering. DRY, YAGNI. "
            f"Give code snippets with explanation."
        )

    def _get_safety_topics(self) -> list[str]:
        return []
