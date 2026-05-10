"""
Knowledge Acquisition Specialist — curated sources per specialist domain.
Provides authoritative references, knowledge bases, and canonical texts
that each specialist can draw from for grounded responses.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.core.specialist_framework import BaseSpecialist, SpecialistResponse

logger = logging.getLogger(__name__)


_LIGHTRAG_INSTANCE = None


def _get_lightrag():
    """Singleton LightRAG instance for knowledge storage."""
    global _LIGHTRAG_INSTANCE
    if _LIGHTRAG_INSTANCE is None:
        from src.memory.lightrag_store import LightRAGStore
        _LIGHTRAG_INSTANCE = LightRAGStore()
    return _LIGHTRAG_INSTANCE

# Curated source repositories per domain
# Each entry maps a domain name to a list of (source_type, title, reference) tuples.
# Source types include: "book", "paper", "standard", "manual", "database", "tool"
DOMAIN_SOURCES: dict[str, list[tuple[str, str, str]]] = {
    "audio": [
        ("book", "Audio Power Amplifier Design", "Douglas Self"),
        ("book", "Designing Audio Power Amplifiers", "Bob Cordell"),
        ("book", "Small Signal Audio Design", "Douglas Self"),
        ("book", "The Art of Electronics", "Horowitz & Hill"),
        ("standard", "Audio Engineering Society Standards", "AES"),
    ],
    "automotive": [
        ("manual", "Honda Service Manuals", "American Honda Motor Co."),
        ("manual", "Toyota Repair Manuals", "Toyota Motor Corp."),
        ("book", "Auto Fundamentals", "Martin W. Stockel"),
        ("book", "Automotive Technology", "James D. Halderman"),
        ("standard", "ASE Certification Tests", "National Institute for Automotive Service Excellence"),
    ],
    "code": [
        ("book", "Clean Code", "Robert C. Martin"),
        ("book", "Design Patterns", "Gang of Four"),
        ("book", "The Pragmatic Programmer", "Hunt & Thomas"),
        ("book", "Introduction to Algorithms", "CLRS"),
        ("book", "Structure and Interpretation of Computer Programs", "SICP"),
        ("reference", "Python Documentation", "python.org"),
        ("reference", "MDN Web Docs", "Mozilla"),
    ],
    "creative": [
        ("book", "The Elements of Style", "Strunk & White"),
        ("book", "On Writing", "Stephen King"),
        ("book", "Bird by Bird", "Anne Lamott"),
        ("book", "The Artist's Way", "Julia Cameron"),
        ("book", "Steal Like an Artist", "Austin Kleon"),
        ("reference", "AP Stylebook", "Associated Press"),
        ("reference", "The Chicago Manual of Style", "University of Chicago Press"),
    ],
    "design": [
        ("book", "The Design of Everyday Things", "Don Norman"),
        ("book", "Don't Make Me Think", "Steve Krug"),
        ("book", "Designing Design", "Kenya Hara"),
        ("book", "Universal Principles of Design", "Lidwell, Holden & Butler"),
        ("reference", "Human Interface Guidelines", "Apple"),
        ("reference", "Material Design Guidelines", "Google"),
    ],
    "fitness": [
        ("book", "Becoming a Supple Leopard", "Dr. Kelly Starrett"),
        ("book", "Starting Strength", "Mark Rippetoe"),
        ("book", "Practical Programming for Strength Training", "Rippetoe & Baker"),
        ("book", "The New Encyclopedia of Modern Bodybuilding", "Arnold Schwarzenegger"),
        ("book", "Nutrition for Health, Fitness & Sport", "Williams, Rawson & Branch"),
        ("reference", "ACSM Guidelines for Exercise Testing and Prescription", "ACSM"),
    ],
    "growth": [
        ("book", "Daring Greatly", "Brené Brown"),
        ("book", "The Gifts of Imperfection", "Brené Brown"),
        ("book", "Man's Search for Meaning", "Viktor Frankl"),
        ("book", "The Power of Now", "Eckhart Tolle"),
        ("book", "Atomic Habits", "James Clear"),
        ("book", "The Body Keeps the Score", "Bessel van der Kolk"),
        ("book", "Radical Acceptance", "Tara Brach"),
    ],
    "infrastructure": [
        ("book", "The Phoenix Project", "Gene Kim"),
        ("book", "The DevOps Handbook", "Kim, Humble, Debois & Willis"),
        ("book", "Site Reliability Engineering", "Beyer, Jones, Petoff & Murphy"),
        ("book", "Security Engineering", "Ross Anderson"),
        ("book", "The Practice of Cloud System Administration", "Limoncelli, Chalup & Hogan"),
        ("reference", "CIS Benchmarks", "Center for Internet Security"),
        ("reference", "NIST Cybersecurity Framework", "NIST"),
    ],
    "research": [
        ("book", "The Elements of Statistical Learning", "Hastie, Tibshirani & Friedman"),
        ("book", "Pattern Recognition and Machine Learning", "Christopher Bishop"),
        ("book", "Deep Learning", "Goodfellow, Bengio & Courville"),
        ("book", "Research Design", "John W. Creswell"),
        ("paper", "Attention Is All You Need", "Vaswani et al."),
        ("reference", "ArXiv", "Cornell University"),
        ("reference", "PubMed", "National Library of Medicine"),
    ],
    "soul": [
        ("book", "Man's Search for Meaning", "Viktor Frankl"),
        ("book", "The Power of Now", "Eckhart Tolle"),
        ("book", "Radical Acceptance", "Tara Brach"),
        ("book", "Nonviolent Communication", "Marshall Rosenberg"),
    ],
}

# Domain aliases for lookup normalization
DOMAIN_ALIASES: dict[str, str] = {
    "devops": "infrastructure",
    "security": "infrastructure",
    "data_science": "research",
    "data-ai": "research",
    "data_ai": "research",
    "creative_writing": "creative",
    "wellness": "fitness",
    "product": "growth",
    "mental_health": "growth",
}


def get_sources_for_domain(domain: str) -> list[tuple[str, str, str]]:
    """Get curated sources for a given domain name.

    Supports both canonical names and common aliases.
    """
    normalized = DOMAIN_ALIASES.get(domain, domain)
    return DOMAIN_SOURCES.get(normalized, [])


def get_source_titles(domain: str) -> list[str]:
    """Get just the titles/references for a domain."""
    return [title for _, title, _ in get_sources_for_domain(domain)]


def get_source_authors(domain: str) -> list[str]:
    """Get unique authors referenced for a domain."""
    authors: set[str] = set()
    for _, _, author in get_sources_for_domain(domain):
        authors.add(author)
    return sorted(authors)


def _format_domain_sources(domain: str) -> str:
    """Format curated sources for a domain as a readable text block."""
    sources = get_sources_for_domain(domain)
    if not sources:
        return ""

    lines = [f"Curated sources for '{domain}':"]
    for source_type, title, author in sources:
        lines.append(f"  - [{source_type}] {title} — {author}")
    return "\n".join(lines)


class KnowledgeAcquisitionSpecialist(BaseSpecialist):
    """Reference librarian specialist — knows curated sources for every domain."""

    def _get_personality(self) -> str:
        return "scholarly, thorough, well-read"

    def _get_system_prompt(self) -> str:
        return (
            f"You are Oracle, a knowledge acquisition and reference specialist. "
            f"Personality: {self.personality}. "
            f"You maintain a curated library of authoritative sources across all domains. "
            f"When asked about a topic, recommend the most relevant books, papers, standards, "
            f"and references from your curated collection. "
            f"Covered domains include: {', '.join(sorted(DOMAIN_SOURCES.keys()))}. "
            f"Be concise but cite specifics — author, title, source type. "
            f"Source curation methodology: prioritize recency (prefer the latest edition), "
            f"authority (peer-reviewed, industry-standard, or canonical), and direct relevance "
            f"to the user's specific sub-topic. When multiple sources are equally relevant, "
            f"recommend the one that best balances depth and accessibility. "
            f"Synthesize across sources when appropriate — note where authorities agree or disagree. "
            f"Identify gaps: if a user asks about a topic with thin coverage in your library, "
            f"say so honestly and suggest the closest alternative or adjacent field. "
            f"Citation format: always include source type (book/paper/standard/manual/database/tool), "
            f"full title, and author/organization. For papers, include publication venue if known. "
            f"A good reference librarian doesn't just hand you a book — they tell you why it matters."
        )

    def _get_safety_topics(self) -> list[str]:
        return ["crisis", "emergency", "medical", "legal"]

    def query(
        self,
        question: str,
        context: dict[str, Any] | None = None,
        model: str | None = None,
        context_preamble: str = "",
        honcho_approach: str = "",
    ) -> SpecialistResponse:
        """Intercept domain-specific source and research queries before falling back to LLM."""
        q_lower = question.lower().strip()

        # Check for direct domain source queries
        matched_domain = self._match_domain_source_query(q_lower)
        if matched_domain:
            sources_text = _format_domain_sources(matched_domain)
            titles = get_source_titles(matched_domain)
            return SpecialistResponse(
                content=sources_text,
                confidence=0.95,
                sources=titles,
                safety_warnings=[],
                suggested_followups=[
                    f"Tell me about {title}" for title in titles[:3]
                ],
                diagnostics={
                    "fallback_used": False,
                    "mode": "localsource",
                    "specialist": self.name,
                    "domain": self.domain,
                },
            )

        # Check for research commands: "research <domain>" or "research all"
        if q_lower.startswith("research "):
            target = q_lower[len("research "):].strip()
            domain = DOMAIN_ALIASES.get(target, target)
            if domain in DOMAIN_SOURCES:
                results = self.research_domain(domain)
                n_success = sum(1 for v in results.values() if v)
                n_total = len(results)
                success_titles = [t for t, v in results.items() if v]
                return SpecialistResponse(
                    content=(
                        f"Researched {n_success}/{n_total} sources for '{domain}'.\n"
                        + "\n".join(f"  ✅ {t}" for t in success_titles)
                    ),
                    confidence=0.9,
                    sources=success_titles,
                    safety_warnings=[],
                    suggested_followups=[
                        f"What did you learn about {success_titles[0]}" if success_titles else f"sources for {domain}"
                    ],
                    diagnostics={
                        "fallback_used": False,
                        "mode": "research",
                        "specialist": self.name,
                        "domain": domain,
                        "n_success": n_success,
                        "n_total": n_total,
                    },
                )
            if target in ("all", "every", "everything"):
                results = self.research_all_sources()
                total_success = sum(
                    sum(1 for v in domain_results.values() if v)
                    for domain_results in results.values()
                )
                total_sources = sum(
                    len(domain_results)
                    for domain_results in results.values()
                )
                return SpecialistResponse(
                    content=(
                        f"Researched {total_success}/{total_sources} sources across all domains.\n"
                        + "\n".join(
                            f"  {d}: {sum(1 for v in r.values() if v)}/{len(r)}"
                            for d, r in sorted(results.items())
                        )
                    ),
                    confidence=0.9,
                    sources=list(DOMAIN_SOURCES.keys()),
                    safety_warnings=[],
                    suggested_followups=list(DOMAIN_SOURCES.keys()),
                    diagnostics={
                        "fallback_used": False,
                        "mode": "research_all",
                        "specialist": self.name,
                        "total_success": total_success,
                        "total_sources": total_sources,
                    },
                )

        # Otherwise fall back to LLM-based query via parent
        return super().query(
            question=question,
            context=context,
            model=model,
            context_preamble=context_preamble,
            honcho_approach=honcho_approach,
        )

    def _match_domain_source_query(self, q_lower: str) -> str | None:
        """Check if query is asking about sources for a known domain."""
        # Conversational query patterns to match
        prefix_patterns = [
            "sources for ",
            "books about ",
            "books on ",
            "reference books for ",
            "reference books on ",
            "recommend resources for ",
            "resources for ",
            "best books on ",
            "good books on ",
            "what to read about ",
            "what books about ",
        ]
        suffix_patterns = [
            " sources",
            " books",
            " reference books",
            " references",
            " resources",
        ]

        for domain in DOMAIN_SOURCES:
            for prefix in prefix_patterns:
                if f"{prefix}{domain}" in q_lower:
                    return domain
            for suffix in suffix_patterns:
                if f"{domain}{suffix}" in q_lower:
                    return domain

        # Check aliases
        for alias, canonical in DOMAIN_ALIASES.items():
            for prefix in prefix_patterns:
                if f"{prefix}{alias}" in q_lower:
                    return canonical
            for suffix in suffix_patterns:
                if f"{alias}{suffix}" in q_lower:
                    return canonical

        return None

    def list_curated_domains(self) -> list[str]:
        """List all curated domain names."""
        return sorted(DOMAIN_SOURCES.keys())

    def research_source(
        self,
        source_type: str,
        title: str,
        author: str = "",
        store: bool = True,
    ) -> str:
        """Research a single source from the internet and optionally store it.

        Args:
            source_type: Type of source (book, paper, standard, etc.)
            title: Title of the source
            author: Author/organization
            store: If True, store the fetched knowledge in LightRAG

        Returns:
            The researched text content
        """
        from src.core.specialists.knowledge_researcher import research_source

        content = research_source(source_type, title, author)

        if store and "No web research results" not in content:
            try:
                rag = _get_lightrag()
                doc_text = (
                    f"Source type: {source_type}\n"
                    f"Title: {title}\n"
                    f"Author: {author}\n"
                    f"Domain: {self.domain}\n"
                    f"---\n{content}"
                )
                rag.add_document(doc_text, metadata={
                    "source": title,
                    "type": source_type,
                    "author": author,
                    "domain": self.domain,
                })
                logger.info(f"Stored research for '{title}' in LightRAG")
            except Exception as e:
                logger.warning(f"Failed to store research for '{title}': {e}")

        return content

    def research_domain(self, domain: str, store: bool = True) -> dict[str, str | None]:
        """Research all sources for a domain from the internet.

        Fetches info about each curated source (Wikipedia, OpenLibrary, ArXiv)
        and optionally stores the knowledge in LightRAG for all specialists to query.

        Args:
            domain: The domain name (e.g., "audio", "code")
            store: If True, store fetched knowledge in LightRAG

        Returns:
            Dict mapping source title to researched content (None if skipped/failed)
        """
        sources = get_sources_for_domain(domain)
        if not sources:
            logger.warning(f"No curated sources for domain '{domain}'")
            return {}

        results: dict[str, str | None] = {}
        for i, (source_type, title, author) in enumerate(sources):
            logger.info(f"Researching [{i+1}/{len(sources)}] {title}...")
            content = self.research_source(source_type, title, author, store=store)
            results[title] = content
            time.sleep(0.3)  # be polite between requests

        return results

    def research_all_sources(self, store: bool = True) -> dict[str, dict[str, str | None]]:
        """Research ALL curated sources across every domain.

        Iterates all DOMAIN_SOURCES, researches each one from the internet,
        and optionally stores the knowledge in LightRAG.

        Args:
            store: If True, store fetched knowledge in LightRAG

        Returns:
            Nested dict mapping domain -> (title -> researched content)
        """
        all_results: dict[str, dict[str, str | None]] = {}
        for domain in sorted(DOMAIN_SOURCES.keys()):
            logger.info(f"\n=== Researching domain: '{domain}' ===")
            domain_results = self.research_domain(domain, store=store)
            all_results[domain] = domain_results
        return all_results
