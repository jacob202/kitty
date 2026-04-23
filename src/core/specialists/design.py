"""Design and UX Specialist."""

from pathlib import Path

from src.core.specialist_framework import BaseSpecialist


class JonnyDesignSpecialist(BaseSpecialist):
    """Design Visionary - Product, UX, and Physical Design"""

    _SOUL_PATH = Path("config/specialists/jonny.md")

    def _get_personality(self) -> str:
        return "polished, aesthetic, human-centered — obsessed with details that matter"

    def _get_system_prompt(self) -> str:
        # Try to load from soul file first
        if self._SOUL_PATH.exists():
            return self._SOUL_PATH.read_text().strip()
        # Fallback to default
        return (
            f"You are Jonny, a design visionary. "
            f"Personality: {self.personality}. "
            f"You think about: human-centered design, product-market fit, aesthetic coherence, "
            f"physical and digital form, the details that separate good from great. "
            f"You ask: does this need to exist? Is this the right category? "
            f"Would someone actually love this? "
            f"Challenge mediocrity. Push for elegance."
        )

    def _get_safety_topics(self) -> list[str]:
        return []
