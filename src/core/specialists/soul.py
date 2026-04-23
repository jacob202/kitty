"""Kitty's Core Soul Specialist."""

import logging
from pathlib import Path

from src.core.specialist_framework import BaseSpecialist, SpecialistResponse

logger = logging.getLogger(__name__)

class KittySoulSpecialist(BaseSpecialist):
    """
    Kitty's core personality — handles casual conversation, journal interface,
    and emotional presence. Uses SOUL.md as the system prompt verbatim.
    """

    _SOUL_PATH = Path("config/SOUL.md")

    def _get_personality(self) -> str:
        return "direct, warm, no bullshit — not clinical, not coddling"

    def _get_system_prompt(self) -> str:
        if self._SOUL_PATH.exists():
            return self._SOUL_PATH.read_text().strip()
        return (
            "You are Kitty. Direct, warm, no bullshit. Not clinical. Not coddling. "
            "Check for the emotional driver underneath the question. "
            "Give the smallest executable next step. Budget-first, Canadian sourcing. "
            "Never shame. Radical acceptance. Radical kindness."
        )

    def _get_safety_topics(self) -> list[str]:
        return ["suicid", "self-harm", "crisis", "emergency"]

    def _check_and_surface_pattern(self) -> str:
        """
        Check for active psychological patterns and return a gentle observation.
        Only fires ~15% of the time to avoid overdoing it.
        """
        import random

        # Rate limit: only fire 15% of the time
        if random.random() > 0.15:
            return ""

        try:
            from src.space_kitty.honcho import Honcho

            honcho = Honcho()
            state = honcho.get_current_state()

            observations = []

            # Research loop
            research_loop = state.get("research_loop", {})
            if (
                research_loop.get("signal") == "active"
                and research_loop.get("intensity", 0) > 0.6
            ):
                observations.append(
                    "Research loop detected — you've been looking into this for a few sessions. What's the smallest next step?"
                )

            # Planning loop
            planning_loop = state.get("planning_loop", {})
            if (
                planning_loop.get("signal") == "active"
                and planning_loop.get("intensity", 0) > 0.6
            ):
                observations.append(
                    "Noticed you're in planning mode — beautiful architecture, no implementation. What's the one thing you'd actually do?"
                )

            # Execution gap (check via execution category if exists)
            execution = state.get("execution", {})
            if execution.get("signal") == "gap" and execution.get("intensity", 0) > 0.6:
                observations.append(
                    "Execution gap widening — what's specifically in the way?"
                )

            # Return one random observation if any
            if observations:
                return random.choice(observations)

        except Exception as e:
            logger.debug(f"Pattern check failed: {e}")

        return ""

    def _prepend_observation(self, content: str, observation: str) -> str:
        """Prepend a gentle pattern observation to the response."""
        if not observation:
            return content

        return f"{observation}\n\n---\n\n{content}"

    def query(
        self,
        question: str,
        context: dict = None,
        model: str = None,
        context_preamble: str = "",
        honcho_approach: str = "",
    ) -> SpecialistResponse:
        """Soul queries skip KB lookup — respond directly from personality."""
        try:
            from src.space_kitty.llm_client import call_llm

            # Get system prompt and append Honcho approach recommendation
            system_prompt = self._get_system_prompt()

            # Inject Honcho approach
            actual_approach = honcho_approach if honcho_approach else ""
            if not actual_approach:
                try:
                    from src.space_kitty.honcho import Honcho

                    honcho = Honcho()
                    actual_approach = honcho.get_approach_recommendation()
                except Exception as e:
                    logger.debug(f"Could not get Honcho approach: {e}")

            if actual_approach:
                system_prompt = f"{system_prompt}\n\n[Current tone & strategy recommendation: {actual_approach}]"

            if context_preamble:
                system_prompt = context_preamble + "\n\n" + system_prompt

            content = call_llm(
                prompt=question,
                system_prompt=system_prompt,
                temperature=0.75,
                model=model,
            )
        except Exception as e:
            logger.warning(f"LLM call failed for Kitty soul: {e}")
            content = "Hey. I'm here. What's on your mind?"

        # Check for patterns and surface if appropriate
        observation = self._check_and_surface_pattern()
        content = self._prepend_observation(content, observation)

        safety = self._check_safety(question)
        return SpecialistResponse(
            content=content,
            confidence=0.85,
            sources=[],
            safety_warnings=safety,
            suggested_followups=[],
            diagnostics={
                "fallback_used": content.startswith("[offline mode]"),
                "mode": (
                    "online" if not content.startswith("[offline mode]") else "offline"
                ),
                "specialist": self.name,
                "domain": self.domain,
                "emotional_adaptation": bool(actual_approach),
            },
        )
