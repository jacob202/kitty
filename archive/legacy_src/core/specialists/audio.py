"""Audio Electronics Specialist."""
from __future__ import annotations

from src.core.specialist_framework import BaseSpecialist
from src.core.specialist_prompt_template import create_audio_prompt_template


class AlexAudioSpecialist(BaseSpecialist):
    """Audio Electronics Expert"""

    def _get_personality(self) -> str:
        return "technical but supportive, safety-conscious"

    def _get_system_prompt(self) -> str:
        template = create_audio_prompt_template()
        # Override the role with the actual name
        template.role = "Alex"
        return template.construct_prompt()

    def _get_safety_topics(self) -> list[str]:
        return [
            "capacitor",
            "high voltage",
            "discharge",
            "transformer",
            "power supply",
            "mains",
            "shock",
            "ground loop",
        ]
