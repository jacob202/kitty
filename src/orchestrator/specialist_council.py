"""
Specialist Council — Multi-specialist collaboration and synthesis.
Allows CoreOrchestrator to consult multiple domain experts and synthesize their views.
"""

import logging
from typing import List, Optional

from src.core.specialist_framework import BaseSpecialist, SpecialistResponse
from src.orchestrator.synthesizer import ResponseSynthesizer, LLMSynthesizer

logger = logging.getLogger(__name__)


class SpecialistCouncil:
    """
    Orchestrates collaboration between multiple domain specialists.
    """

    def __init__(
        self, 
        specialists: List[BaseSpecialist], 
        synthesizer: Optional[ResponseSynthesizer] = None
    ):
        """
        Args:
            specialists: List of specialists to consult
            synthesizer: Synthesizer to use for combining responses (None = use default LLM synthesizer)
        """
        self.specialists = specialists
        self.synthesizer = synthesizer or LLMSynthesizer()

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
        import concurrent.futures
         
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.specialists)) as executor:
            future_to_spec = {
                executor.submit(specialist.query, query, context or {}, **kwargs): specialist
                for specialist in self.specialists
            }
            for future in concurrent.futures.as_completed(future_to_spec):
                spec = future_to_spec[future]
                try:
                    resp = future.result()
                    responses.append(resp)
                except Exception as e:
                    logger.warning(f"Specialist {spec.name} failed during consultation: {e}")

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

        return self.synthesizer.synthesize(query, responses)

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
