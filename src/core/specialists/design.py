"""Design and UX Specialist."""
from __future__ import annotations

from src.core.specialist_framework import BaseSpecialist
from src.core.specialist_prompt_template import create_design_prompt_template


class JonnyDesignSpecialist(BaseSpecialist):
    """Design Visionary - Product, UX, and Physical Design"""

    def _get_personality(self) -> str:
        return "polished, aesthetic, human-centered — obsessed with details that matter"

    def _get_system_prompt(self) -> str:
        template = create_design_prompt_template()
        # Override the role with the actual name
        template.role = "Jonny"
        return template.construct_prompt()

    def _get_safety_topics(self) -> list[str]:
        return [
            "accessibility",
            "dark pattern",
            "misleading",
            "deceptive",
            "wcag",
            "a11y",
            "cookie",
            "gdpr",
        ]
