"""Synthesizer interface and implementations for Specialist Council."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.specialist_framework import SpecialistResponse


class ResponseSynthesizer(ABC):
    """Interface for synthesizing multiple specialist responses."""
    
    @abstractmethod
    def synthesize(self, query: str, responses: List[SpecialistResponse]) -> SpecialistResponse:
        """Synthesize multiple specialist responses into a single response."""
        pass


class LLMSynthesizer(ResponseSynthesizer):
    """Default synthesizer that uses LLM to combine specialist responses."""
    
    def __init__(self, model: Optional[str] = None):
        self.model = model
    
    def synthesize(self, query: str, responses: List[SpecialistResponse]) -> SpecialistResponse:
        """Synthesize responses using LLM (original implementation)."""
        from src.space_kitty.llm_client import call_llm
        import logging
        
        logger = logging.getLogger(__name__)
        
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
                model=self.model
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


class SimpleAverageSynthesizer(ResponseSynthesizer):
    """Simple synthesizer that averages responses without LLM."""
    
    def synthesize(self, query: str, responses: List[SpecialistResponse]) -> SpecialistResponse:
        """Synthesize by averaging confidence and combining content simply."""
        if not responses:
            return SpecialistResponse(
                content="No specialists available for consultation.",
                confidence=0.0,
                sources=[],
                safety_warnings=[],
                suggested_followups=[]
            )
        
        if len(responses) == 1:
            return responses[0]
        
        # Combine content with clear attribution
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
        
        # Use the response with highest confidence as base, but combine insights
        base_response = max(responses, key=lambda r: r.confidence)
        combined_content = "\n\n---\n\n".join(context_parts)
        
        # Calculate average confidence
        avg_confidence = sum(r.confidence for r in responses) / len(responses)
        
        # Deduplicate sources and safety warnings
        all_sources = list(set(all_sources))
        all_safety = list(set(all_safety))
        
        return SpecialistResponse(
            content=combined_content,
            confidence=avg_confidence,
            sources=all_sources,
            safety_warnings=all_safety,
            suggested_followups=[],
            diagnostics=all_diagnostics
        )