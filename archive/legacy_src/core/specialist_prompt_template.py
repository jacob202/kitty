"""Prompt template stubs for domain specialists."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class SpecialistPromptTemplate:
    role: str = "Specialist"
    domain: str = "general"
    personality: str = "helpful and knowledgeable"
    extra_context: list[str] = field(default_factory=list)

    def construct_prompt(self) -> str:
        lines = [f"You are {self.role}, a {self.domain} specialist."]
        lines.append(f"Personality: {self.personality}.")
        for ctx in self.extra_context:
            lines.append(ctx)
        return " ".join(lines)


def create_audio_prompt_template() -> SpecialistPromptTemplate:
    return SpecialistPromptTemplate(
        role="Alex",
        domain="audio electronics",
        personality="technical but supportive, safety-conscious",
        extra_context=["Always warn about high-voltage and capacitor discharge risks."],
    )


def create_code_prompt_template() -> SpecialistPromptTemplate:
    return SpecialistPromptTemplate(
        role="Devin",
        domain="software development",
        personality="pragmatic, readable-code-first, pattern-aware",
    )


def create_design_prompt_template() -> SpecialistPromptTemplate:
    return SpecialistPromptTemplate(
        role="Jonny",
        domain="product and UX design",
        personality="polished, aesthetic, human-centered",
    )
