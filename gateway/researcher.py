import logging
import os
import subprocess
import json
import requests
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger("kitty.researcher")

class DeepResearcher:
    """
    Advanced technical research wrapper.
    Combines web search, scraping, and automatic ingestion.
    """
    
    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.tavily_key = os.environ.get("TAVILY_API_KEY")
        
    def technical_deep_dive(self, topic: str, ingest: bool = True) -> str:
        """
        Conducts deep technical research and optionally ingests the findings.
        """
        logger.info(f"Starting deep technical dive: {topic}")
        
        # 1. Search for high-authority sources
        urls = self._find_sources(topic)
        if not urls:
            return "I couldn't find any external sources for that topic."
            
        # 2. Scrape the top technical results
        findings = self._scrape_sources(urls)
        if not findings:
            return "I found sources but couldn't extract any meaningful technical data."
            
        # 3. Synthesize and Ingest
        summary = self._synthesize_findings(topic, findings)
        
        if ingest:
            self._ingest_findings(topic, findings, summary)
            
        return summary

    def _find_sources(self, topic: str) -> List[str]:
        """Uses Tavily to find technical documentation and forum threads."""
        if not self.tavily_key:
            logger.warning("No TAVILY_API_KEY. Falling back to basic search.")
            return []
            
        try:
            # Tavily specialized search for tech data
            resp = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_key,
                    "query": f"technical documentation datasheet manual repair {topic}",
                    "search_depth": "advanced",
                    "include_domains": ["arxiv.org", "hifiengine.com", "audiokarma.org", "diyaudio.com", "allaboutcircuits.com"],
                    "max_results": 5
                },
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            return [r["url"] for r in data.get("results", [])]
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []

    def _scrape_sources(self, urls: List[str]) -> str:
        """Uses Firecrawl-py to scrape technical markdown from URLs."""
        from firecrawl import FirecrawlApp
        app = FirecrawlApp(api_key=os.environ.get("FIRECRAWL_API_KEY"))
        
        results = []
        for url in urls[:3]:
            try:
                logger.info(f"Scraping: {url}")
                scrape_result = app.scrape_url(url, params={'formats': ['markdown']})
                markdown = scrape_result.get("markdown")
                if markdown:
                    results.append(f"### SOURCE: {url}\n{markdown[:5000]}")
            except Exception as e:
                logger.warning(f"Scrape failed for {url}: {e}")
                
        return "\n\n---\n\n".join(results)

    def _synthesize_findings(self, topic: str, findings: str) -> str:
        """Uses LLM to summarize findings in Kitty's voice."""
        soul_path = Path("/Users/jacobbrizinski/Projects/kitty/prompts/soul_v1.md")
        soul_context = soul_path.read_text() if soul_path.exists() else ""

        prompt = f"""{soul_context}

CONTEXT:
Jacob needs deep technical info on: "{topic}"
I have scraped these external sources:
{findings}

TASK:
Synthesize this into a technical brief for Jacob.
1. Highlight the specific technical values, part numbers, or adjustment steps found.
2. If there are conflicting values, note them.
3. Be direct and technical. 
4. End with 'I've added this to our permanent knowledge base.'

Rules: Short sentences. Use contractions. Speak Canadian."""

        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "google/gemini-2.0-flash-exp:free" if not self.api_key else "deepseek/deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.3
                },
                timeout=45
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return "I found the data, but couldn't synthesize it properly. Check the logs."

    def _ingest_findings(self, topic: str, findings: str, summary: str):
        """Saves findings to a temp file and triggers the ingestion pipeline."""
        from gateway.knowledge import ingest_file
        import tempfile
        
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                f.write(f"# Deep Research: {topic}\n\n## Summary\n{summary}\n\n## Raw Findings\n{findings}")
                tmp_path = f.name
                
            ingest_file(
                tmp_path, 
                source_label=f"research_{topic.replace(' ', '_')}",
                doc_type="technical_research"
            )
            Path(tmp_path).unlink(missing_ok=True)
            logger.info(f"Ingested research for: {topic}")
        except Exception as e:
            logger.error(f"Ingestion of research failed: {e}")

def deep_dive(topic: str) -> str:
    """Convenience function for Gateway calling."""
    researcher = DeepResearcher()
    return researcher.technical_deep_dive(topic)
