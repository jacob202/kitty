import logging
import os
from pathlib import Path
from typing import List

import httpx

logger = logging.getLogger("kitty.researcher")


class DeepResearcher:
    """
    Advanced technical research wrapper.
    Combines web search, scraping, and automatic ingestion.
    """

    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.tavily_key = os.environ.get("TAVILY_API_KEY")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=20)
        return self._client

    async def technical_deep_dive(self, topic: str, ingest: bool = True) -> str:
        """
        Conducts deep technical research and optionally ingests the findings.
        """
        logger.info(f"Starting deep technical dive: {topic}")

        # 1. Search for high-authority sources
        urls = await self._find_sources(topic)
        if not urls:
            return "I couldn't find any external sources for that topic."

        # 2. Scrape the top technical results
        findings = await self._scrape_sources(urls)
        if not findings:
            return "I found sources but couldn't extract any meaningful technical data."

        # 3. Synthesize and Ingest
        summary = self._synthesize_findings(topic, findings)

        if ingest:
            await self._ingest_findings(topic, findings, summary)

        return summary

    async def _find_sources(self, topic: str) -> List[str]:
        """Uses Tavily to find technical documentation and forum threads."""
        if not self.tavily_key:
            logger.warning("No TAVILY_API_KEY. Falling back to basic search.")
            return []

        try:
            client = await self._get_client()
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_key,
                    "query": f"technical documentation datasheet manual repair {topic}",
                    "search_depth": "advanced",
                    "include_domains": ["arxiv.org", "hifiengine.com", "audiokarma.org", "diyaudio.com", "allaboutcircuits.com"],
                    "max_results": 5
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return [r["url"] for r in data.get("results", [])]
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []

    async def _scrape_sources(self, urls: List[str]) -> str:
        """Uses Tavily to extract technical context from URLs."""
        if not self.tavily_key:
            return ""

        results = []
        client = await self._get_client()
        for url in urls[:3]:
            try:
                logger.info(f"Extracting context via Tavily: {url}")
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_key,
                        "query": f"detailed technical content from {url}",
                        "search_depth": "advanced",
                        "include_raw_content": True,
                        "max_results": 1
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("results"):
                    content = data["results"][0].get("raw_content") or data["results"][0].get("content")
                    if content:
                        results.append(f"### SOURCE: {url}\n{content[:6000]}")
            except Exception as e:
                logger.warning(f"Tavily extraction failed for {url}: {e}")

        return "\n\n---\n\n".join(results)

    def _synthesize_findings(self, topic: str, findings: str) -> str:
        """Uses LLM to summarize findings in Kitty's voice."""
        from gateway.context_builder import build_worker_context
        from gateway.llm_client import chat

        task_desc = f"""Jacob needs deep technical info on: "{topic}"
I have scraped these external sources:
{findings}

TASK:
Synthesize this into a technical brief for Jacob.
1. Highlight the specific technical values, part numbers, or adjustment steps found.
2. If there are conflicting values, note them.
3. Be direct and technical.
4. End with 'I've added this to our permanent knowledge base.'

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
            logger.error(f"Synthesis failed: {e}")
            return "I found the data, but couldn't synthesize it properly. Check the logs."

    async def _ingest_findings(self, topic: str, findings: str, summary: str):
        """Saves findings to a temp file and triggers the ingestion pipeline."""
        import tempfile

        from gateway.knowledge import ingest_file

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                f.write(f"# Deep Research: {topic}\n\n## Summary\n{summary}\n\n## Raw Findings\n{findings}")
                tmp_path = f.name

            await ingest_file(
                tmp_path,
                source_label=f"research_{topic.replace(' ', '_')}",
                doc_type="technical_research"
            )
            Path(tmp_path).unlink(missing_ok=True)
            logger.info(f"Ingested research for: {topic}")
        except Exception as e:
            logger.error(f"Ingestion of research failed: {e}")

async def deep_dive(topic: str) -> str:
    """Convenience function for Gateway calling."""
    researcher = DeepResearcher()
    return await researcher.technical_deep_dive(topic)
