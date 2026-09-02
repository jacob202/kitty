import logging
import os
from pathlib import Path
from typing import List

import httpx

logger = logging.getLogger("kitty.researcher")


class ResearcherError(RuntimeError):
    pass


class ResearchSearchUnavailable(ResearcherError):
    pass


class ResearchSynthesisError(ResearcherError):
    pass


class DeepResearcher:
    """
    Legacy technical research wrapper.
    Combines web search, scraping, synthesis, and optional knowledge promotion.

    General Research is being replaced by the engine-backed contract tracked in
    issue #547. Until then this module must remain honest about persistence:
    research results are not permanent knowledge unless promotion is explicitly
    requested and actually succeeds.
    """

    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.tavily_key = os.environ.get("TAVILY_API_KEY")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=20)
        return self._client

    async def technical_deep_dive_report(self, topic: str, progress=None) -> dict:
        """Run research and return structured evidence without promoting it to memory."""
        logger.info("Starting deep technical dive: %s", topic)
        if progress:
            progress("searching", None)
        urls = await self._find_sources(topic)
        if not urls:
            return {"summary": "I couldn't find any external sources for that topic.", "sources": [], "findings": ""}
        if progress:
            progress("reading", urls)
        findings = await self._scrape_sources(urls)
        if not findings:
            return {"summary": "I found sources but couldn't extract any meaningful technical data.", "sources": urls, "findings": ""}
        if progress:
            progress("synthesizing", urls)
        summary = self._synthesize_findings(topic, findings)
        return {"summary": summary, "sources": urls, "findings": findings}

    async def technical_deep_dive(self, topic: str, ingest: bool = False) -> str:
        """Conduct technical research and optionally promote it to knowledge."""
        report = await self.technical_deep_dive_report(topic)
        summary = report["summary"]
        findings = report["findings"]
        if not ingest or not findings:
            return summary
        ingested = await self._ingest_findings(topic, findings, summary)
        if ingested:
            return f"{summary}\n\nSaved to Kitty's knowledge base."
        return f"{summary}\n\nResearch completed, but saving it to the knowledge base failed."

    async def _find_sources(self, topic: str) -> List[str]:
        """Uses Tavily to find technical documentation and forum threads."""
        if not self.tavily_key:
            raise ResearchSearchUnavailable("TAVILY_API_KEY is not configured")

        try:
            client = await self._get_client()
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_key,
                    "query": f"technical documentation datasheet manual repair {topic}",
                    "search_depth": "advanced",
                    "include_domains": [
                        "arxiv.org",
                        "hifiengine.com",
                        "audiokarma.org",
                        "diyaudio.com",
                        "allaboutcircuits.com",
                    ],
                    "max_results": 5,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return [r["url"] for r in data.get("results", [])]
        except Exception as e:
            logger.exception("Tavily search failed")
            raise ResearchSearchUnavailable(f"Tavily search failed: {e}") from e

    async def _scrape_sources(self, urls: List[str]) -> str:
        """Uses Tavily to extract technical context from URLs."""
        if not self.tavily_key:
            return ""

        results = []
        client = await self._get_client()
        for url in urls[:3]:
            try:
                logger.info("Extracting context via Tavily: %s", url)
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_key,
                        "query": f"detailed technical content from {url}",
                        "search_depth": "advanced",
                        "include_raw_content": True,
                        "max_results": 1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("results"):
                    content = data["results"][0].get("raw_content") or data["results"][0].get(
                        "content"
                    )
                    if content:
                        results.append(f"### SOURCE: {url}\n{content[:6000]}")
            except Exception as e:
                logger.warning("Tavily extraction failed for %s: %s", url, e)

        return "\n\n---\n\n".join(results)

    def _synthesize_findings(self, topic: str, findings: str) -> str:
        """Uses LLM to summarize findings in Kitty's voice."""
        from gateway.context_assembler import build_worker_context
        from gateway.llm_client import chat

        task_desc = f"""Jacob needs deep technical info on: "{topic}"
I have scraped these external sources:
{findings}

TASK:
Synthesize this into a technical brief for Jacob.
1. Highlight the specific technical values, part numbers, or adjustment steps found.
2. If there are conflicting values, note them.
3. Be direct and technical.
4. Do not claim the research was saved, remembered, or added to a knowledge base; persistence is handled separately after synthesis.

Rules: Short sentences. Use contractions. Speak Canadian."""

        prompt = build_worker_context("researcher", topic=topic, chunks=task_desc)

        try:
            return chat(
                model="deepseek/deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.3,
            )
        except Exception as e:
            logger.exception("Research synthesis failed")
            raise ResearchSynthesisError(f"Research synthesis failed: {e}") from e

    async def _ingest_findings(self, topic: str, findings: str, summary: str) -> bool:
        """Promote findings to knowledge. Returns True only after successful ingest."""
        import tempfile

        from gateway.knowledge import ingest_file

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                f.write(
                    f"# Deep Research: {topic}\n\n## Summary\n{summary}\n\n## Raw Findings\n{findings}"
                )
                tmp_path = f.name

            await ingest_file(
                tmp_path,
                source_label=f"research_{topic.replace(' ', '_')}",
                doc_type="technical_research",
            )
            logger.info("Ingested research for: %s", topic)
            return True
        except Exception as e:
            logger.error("Ingestion of research failed: %s", e)
            return False
        finally:
            if tmp_path is not None:
                Path(tmp_path).unlink(missing_ok=True)


async def deep_dive(topic: str, *, ingest: bool = False) -> str:
    """Convenience function for Gateway calling; persistence is opt-in."""
    researcher = DeepResearcher()
    return await researcher.technical_deep_dive(topic, ingest=ingest)
