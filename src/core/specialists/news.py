"""News Feed Specialist — Real-time domain-specific news and intelligence."""

from __future__ import annotations

import logging

from src.core.specialist_framework import BaseSpecialist, SpecialistResponse
from src.services.context_service import query_domain_news

logger = logging.getLogger(__name__)


class NewsFeedSpecialist(BaseSpecialist):
    """News and Intelligence Gathering Expert"""

    DOMAIN_MAP = {
        "auto": "automotive",
        "car": "automotive",
        "code": "code",
        "dev": "code",
        "audio": "audio",
        "music": "audio",
        "fitness": "fitness",
        "growth": "growth",
        "design": "design",
        "creative": "creative",
        "infra": "infrastructure",
        "devops": "infrastructure",
        "research": "research",
        "science": "research",
    }

    def _get_personality(self) -> str:
        return "sharp, analytical, always up-to-date — information is power only if it's timely"

    def _get_system_prompt(self) -> str:
        return (
            f"You are the News Feed Specialist, an expert in aggregating, summarizing, "
            f"and delivering breaking news, industry trends, and domain-specific intelligence. "
            f"Personality: {self.personality}. "
            f"Your job is to surface highly relevant news tailored to the user's current context "
            f"or the active specialist domain. "
            f"Filter out noise, clickbait, and duplicate stories. Focus on high-signal "
            f"developments, new releases, important CVEs, market shifts, and research breakthroughs. "
            f"Always provide sources and context for why the news matters right now."
        )

    def _get_safety_topics(self) -> list[str]:
        return [
            "misinformation",
            "fake news",
            "propaganda",
            "unverified rumor",
            "financial advice",
            "market manipulation",
        ]

    def query(
        self,
        question: str,
        context: dict | None = None,
        model: str | None = None,
        context_preamble: str = "",
        honcho_approach: str = "",
    ) -> SpecialistResponse:
        domain = None
        if context and "domain" in context:
            domain = context["domain"]
        if not domain:
            q_lower = question.lower()
            for keyword, mapped in self.DOMAIN_MAP.items():
                if keyword in q_lower:
                    domain = mapped
                    break

        news_context = query_domain_news(domain or "news", limit=5)

        full_question = question
        if news_context:
            full_question = f"{news_context}\n\nUser question: {question}"

        return super().query(
            question=full_question,
            context=context,
            model=model,
            context_preamble=context_preamble,
            honcho_approach=honcho_approach,
        )
