"""
Specialist Council — Multi-specialist collaboration and synthesis.
Allows CoreOrchestrator to consult multiple domain experts and synthesize their views.
"""

import logging

from src.core.specialist_framework import BaseSpecialist, SpecialistResponse

logger = logging.getLogger(__name__)


class SpecialistCouncil:
    """
    Orchestrates collaboration between multiple domain specialists.
    """

    def __init__(self, specialists: list[BaseSpecialist], synthesizer_model: str | None = None):
        """
        Args:
            specialists: List of specialists to consult
            synthesizer_model: Model ID to use for synthesis (None = use default)
        """
        self.specialists = specialists
        self.synthesizer_model = synthesizer_model

    def consult(self, query: str, context: dict | None = None, **kwargs) -> SpecialistResponse:
        """
        Consult all specialists and synthesize a single response.
        """
        if not self.specialists:
            return SpecialistResponse(
                content="No specialists available for consultation.",
                confidence=0.0,
                sources=[],
                safety_warnings=[],
                suggested_followups=[]
            )

        responses = []
        for specialist in self.specialists:
            try:
                resp = specialist.query(query, context or {}, **kwargs)
                responses.append(resp)
            except Exception as e:
                logger.warning(f"Specialist {specialist.name} failed during consultation: {e}")

        if not responses:
            return SpecialistResponse(
                content="Consultation failed — all specialists errored out.",
                confidence=0.0,
                sources=[],
                safety_warnings=[],
                suggested_followups=[]
            )

        if len(responses) == 1:
            return responses[0]

        return self._synthesize(query, responses)

    def _synthesize(self, query: str, responses: list[SpecialistResponse]) -> SpecialistResponse:
        """Synthesize multiple specialist responses into one using the LLM."""
        from src.space_kitty.llm_client import call_llm

        context_parts = []
        all_sources = []
        all_safety = []
        all_diagnostics = {"consultants": []}

        for resp in responses:
            name = resp.diagnostics.get("specialist", "Expert")
            context_parts.append(f"### Perspective from {name}:\n{resp.content}")
            all_sources.extend(resp.sources)
            all_safety.extend(resp.safety_warnings)
            all_diagnostics["consultants"].append(resp.diagnostics)

        context_text = "\n\n".join(context_parts)

        system_prompt = (
            "You are Kitty, the lead orchestrator. You have consulted several domain specialists "
            "regarding the user's query. Your task is to synthesize their perspectives into a single, "
            "cohesive, and actionable response. Identify areas of agreement, resolve contradictions, "
            "and provide a unified path forward. Be direct, warm, and helpful."
        )

        prompt = (
            f"User Query: {query}\n\n"
            f"Specialist Responses:\n{context_text}\n\n"
            "Synthesize these into a final response for the user."
        )

        try:
            content = call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.synthesizer_model
            )
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            content = "I've consulted several experts, but I'm having trouble combining their advice. " \
                      "Here is a summary of their views:\n\n" + context_text

        # Deduplicate sources and safety warnings
        all_sources = list(set(all_sources))
        all_safety = list(set(all_safety))

        # Calculate average confidence
        avg_confidence = sum(r.confidence for r in responses) / len(responses)

        return SpecialistResponse(
            content=content,
            confidence=avg_confidence,
            sources=all_sources,
            safety_warnings=all_safety,
            suggested_followups=[],
            diagnostics=all_diagnostics
        )
