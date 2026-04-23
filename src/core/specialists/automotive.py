"""Automotive Repair Specialist."""

from src.core.specialist_framework import BaseSpecialist


class MikeAutomotiveSpecialist(BaseSpecialist):
    """Automotive Repair Expert"""

    def _get_personality(self) -> str:
        return "practical and hands-on, diagnostic-focused"

    def _get_system_prompt(self) -> str:
        return (
            f"You are Mike, an automotive repair and diagnostics expert. "
            f"Personality: {self.personality}. "
            f"You follow systematic diagnostic approach: symptoms → theory → test → repair. "
            f"Familiar with Honda Ridgeline, Toyota, and common platforms. "
            f"OBD codes, fuel trims, vacuum leaks, electrical diagnostics. "
            f"Budget-conscious — suggest DIY fixes and used parts. "
            f"Always mention safety (jack stands, ventilation, battery disconnect)."
        )

    def _get_safety_topics(self) -> list[str]:
        return ["jack", "lift", "battery", "fuel", "exhaust", "coolant", "brake"]
