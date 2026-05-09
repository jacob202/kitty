"""Code Specialist."""
from __future__ import annotations

from src.core.specialist_framework import BaseSpecialist
from src.core.specialist_prompt_template import create_code_prompt_template


class KittyCoderSpecialist(BaseSpecialist):
    """Code specialist that uses LLM + KB for software development questions."""

    def _get_personality(self) -> str:
        return "pragmatic, readable-code-first, pattern-aware"

    def _get_system_prompt(self) -> str:
        template = create_code_prompt_template()
        # Override the role with the actual name
        template.role = "Devin"
        return template.construct_prompt()

    def _get_safety_topics(self) -> list[str]:
        return ["rm -rf", "drop table", "eval(", "sudo", "chmod 777"]
