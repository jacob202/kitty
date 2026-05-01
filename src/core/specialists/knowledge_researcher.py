"""Web Research Engine — fetches knowledge about curated sources from the internet.

Strategy priority:
  1. exa.ai (if EXA_API_KEY is set) — best semantic search + page content
  2. Firecrawl (if FIRECRAWL_API_KEY is set) — good web scraping
  3. Free public APIs (Wikipedia, OpenLibrary, ArXiv) — always available fallback
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_USER_AGENT = "KittyKnowledgeAcquisition/1.0 (research-bot; +https://github.com/kitty)"
_REQUEST_TIMEOUT = 15  # seconds
_RATE_LIMIT_DELAY = 0.5  # seconds between requests to be polite

# Shared session for connection pooling
_session = requests.Session()
_session.headers.update({"User-Agent": _USER_AGENT})

# ─── Exa client singleton ───────────────────────────────────────────────────

_EXA_CLIENT = None


def _get_exa():
    """Lazy-init singleton Exa client from EXA_API_KEY env var."""
    global _EXA_CLIENT
    if _EXA_CLIENT is None:
        api_key = os.environ.get("EXA_API_KEY")
        if api_key:
            from exa_py import Exa
            _EXA_CLIENT = Exa(api_key=api_key)
            logger.info("Exa AI client initialized")
    return _EXA_CLIENT


# ─── Firecrawl client singleton ─────────────────────────────────────────────

_FIRECRAWL_CLIENT = None


def _get_firecrawl():
    """Lazy-init singleton Firecrawl client from FIRECRAWL_API_KEY env var."""
    global _FIRECRAWL_CLIENT
    if _FIRECRAWL_CLIENT is None:
        api_key = os.environ.get("FIRECRAWL_API_KEY")
        if api_key:
            from firecrawl import FirecrawlApp
            _FIRECRAWL_CLIENT = FirecrawlApp(api_key=api_key)
            logger.info("Firecrawl client initialized")
    return _FIRECRAWL_CLIENT


# ─── Free API Helpers (backup) ──────────────────────────────────────────────


def _fetch_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any] | None:
    """Fetch JSON from a URL with rate limiting and error handling."""
    try:
        hdrs = {}
        if headers:
            hdrs.update(headers)
        resp = _session.get(url, headers=hdrs, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.debug(f"HTTP fetch failed for {url}: {e}")
        return None


def _fetch_text(url: str) -> str | None:
    """Fetch text content from a URL."""
    try:
        resp = _session.get(url, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.debug(f"HTTP text fetch failed for {url}: {e}")
        return None


def _wikipedia_search(query: str) -> str | None:
    """Search Wikipedia for a topic and return the extract summary."""
    title = query.replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
    data = _fetch_json(url)

    if data and data.get("extract"):
        extract = data["extract"]
        source_url = data.get("content_urls", {}).get("desktop", {}).get("page", url)
        return (
            f"From Wikipedia ({data.get('title', title)}):\n"
            f"{extract[:2000]}\n"
            f"Source: {source_url}"
        )

    # Fallback: search for the query
    search_url = (
        "https://en.wikipedia.org/w/api.php"
        "?action=query&list=search&srsearch={}&format=json&srlimit=3"
    )
    search_data = _fetch_json(search_url.format(query))
    if search_data:
        results = search_data.get("query", {}).get("search", [])
        for result in results[:1]:
            page_title = result.get("title", "")
            if page_title:
                return _wikipedia_search(page_title)

    return None


def _openlibrary_search(title: str, author: str = "") -> str | None:
    """Search OpenLibrary for a book and return description + metadata."""
    query_parts = [f"title:{title}"]
    if author:
        query_parts.append(f"author:{author}")
    query_str = " AND ".join(query_parts)
    url = f"https://openlibrary.org/search.json?q={query_str}&limit=1"

    data = _fetch_json(url)
    if not data:
        return None

    docs = data.get("docs", [])
    if not docs:
        return None

    doc = docs[0]
    ol_title = doc.get("title", title)
    ol_author = ", ".join(doc.get("author_name", [author])) if doc.get("author_name") else author
    ol_year = doc.get("first_publish_year", "")
    ol_subjects = ", ".join(doc.get("subject", [])[:5]) if doc.get("subject") else ""
    ol_key = doc.get("key", "")

    # Fetch full description from the work page
    description = ""
    if ol_key:
        time.sleep(_RATE_LIMIT_DELAY)
        work_url = f"https://openlibrary.org{ol_key}.json"
        work_data = _fetch_json(work_url)
        if work_data:
            desc = work_data.get("description", "")
            if isinstance(desc, dict):
                desc = desc.get("value", "")
            if desc:
                description = desc[:1500]

    parts = [
        f"Book: {ol_title}",
        f"Author: {ol_author}",
    ]
    if ol_year:
        parts.append(f"First published: {ol_year}")
    if ol_subjects:
        parts.append(f"Subjects: {ol_subjects}")
    if description:
        parts.append(f"\nDescription: {description}")
    parts.append(f"Source: https://openlibrary.org{ol_key}" if ol_key else "")

    return "\n".join(p for p in parts if p)


def _arxiv_search(title: str) -> str | None:
    """Search ArXiv for a paper by title and return abstract + metadata."""
    import xml.etree.ElementTree as ET

    url = (
        f"https://export.arxiv.org/api/query"
        f"?search_query=ti:{title}&max_results=1&sortBy=relevance"
    )
    text = _fetch_text(url)
    if not text:
        return None

    try:
        root = ET.fromstring(text)
        ns = {"atom": "http://www.w3.org/2005/Atom",
              "arxiv": "http://arxiv.org/schema/ns"}
        entry = root.find("atom:entry", ns)
        if entry is None:
            return None

        arxiv_title = entry.findtext("atom:title", title, ns).strip()
        arxiv_summary = entry.findtext("atom:summary", "", ns).strip()
        arxiv_id = entry.findtext("atom:id", "", ns)
        arxiv_published = entry.findtext("atom:published", "", ns)[:10] if entry.findtext("atom:published", "", ns) else ""

        authors = []
        for author_elem in entry.findall("atom:author", ns):
            name = author_elem.findtext("atom:name", "", ns)
            if name:
                authors.append(name)
        author_str = ", ".join(authors)

        # Strip arXiv ID from the full URL
        arxiv_id_clean = arxiv_id.split("/")[-1].split("v")[0] if arxiv_id else ""

        parts = [
            f"Paper: {arxiv_title}",
            f"Authors: {author_str}",
            f"Published: {arxiv_published}",
            f"\nAbstract: {arxiv_summary[:2000]}",
            f"Source: https://arxiv.org/abs/{arxiv_id_clean}" if arxiv_id_clean else "",
        ]
        return "\n".join(p for p in parts if p)

    except ET.ParseError as e:
        logger.debug(f"ArXiv XML parse error: {e}")
        return None


def _exa_research(query: str) -> str | None:
    """Use Exa AI to search for and retrieve content about a topic."""
    exa = _get_exa()
    if not exa:
        return None

    try:
        result = exa.search(
            query,
            num_results=3,
            contents={"text": {"maxCharacters": 3000}},
        )
        if not result or not result.results:
            return None

        snippets: list[str] = []
        for i, r in enumerate(result.results[:3], 1):
            title = r.title or "Untitled"
            url = r.url or ""
            text = (r.text or "")[:2000]
            snippets.append(
                f"[{i}] {title}\n"
                f"URL: {url}\n"
                f"{text}\n"
            )
        return "\n---\n".join(snippets)

    except Exception as e:
        logger.debug(f"Exa search failed for '{query}': {e}")
        return None


def _firecrawl_scrape(url: str) -> str | None:
    """Use Firecrawl to scrape a URL and return clean content."""
    fc = _get_firecrawl()
    if not fc:
        return None

    try:
        result = fc.scrape_url(url)
        if not result:
            return None

        if isinstance(result, dict):
            markdown = result.get("markdown") or result.get("content") or ""
        else:
            markdown = str(result)

        return markdown[:3000] if markdown else None

    except Exception as e:
        logger.debug(f"Firecrawl scrape failed for '{url}': {e}")
        return None


# ─── Higher-level research using all strategies ─────────────────────────────


def _free_api_research(source_type: str, title: str, author: str = "") -> str:
    """Research a source using only free public APIs (no API key needed)."""
    results: list[str] = []

    # Strategy 1: Type-specific lookups
    if source_type == "paper":
        result = _arxiv_search(title)
        if result:
            results.append(result)
            time.sleep(_RATE_LIMIT_DELAY)

    elif source_type == "book":
        result = _openlibrary_search(title, author)
        if result:
            results.append(result)
            time.sleep(_RATE_LIMIT_DELAY)

    # Strategy 2: Wikipedia search for all types
    wiki_query = f"{title} {author}".strip()
    result = _wikipedia_search(wiki_query)
    if result:
        results.append(result)
        time.sleep(_RATE_LIMIT_DELAY)

    # Strategy 3: Wikipedia search for just the title
    if not results:
        result = _wikipedia_search(title)
        if result:
            results.append(result)
            time.sleep(_RATE_LIMIT_DELAY)

    if results:
        return "\n\n---\n\n".join(results)

    return (
        f"No web research results found for [{source_type}] {title}"
        f"{' — ' + author if author else ''}. "
        f"Consider adding this source manually via the ingest pipeline."
    )


def research_source(source_type: str, title: str, author: str = "") -> str:
    """Research a single source and return formatted knowledge text.

    Tries Exa AI first (if configured), then free public APIs.

    Args:
        source_type: Type of source (book, paper, standard, reference, etc.)
        title: Title of the source
        author: Author or organization

    Returns:
        Formatted text with research results
    """
    query = f"{title} {author}".strip()

    # Priority 1: Exa AI (best quality, needs API key)
    exa = _get_exa()
    if exa:
        logger.info(f"Researching '{title}' via Exa AI...")
        exa_query = query
        if source_type in ("paper", "book", "standard"):
            exa_query = f"{source_type}: {query}"
        content = _exa_research(exa_query)
        if content:
            header = (
                f"Research results for: {title}\n"
                f"Type: {source_type}\n"
                f"Author: {author}\n"
                f"---\n"
            )
            return header + content

    # Priority 2: Firecrawl (if we can find a good URL to scrape)
    # For books/papers, try Wikipedia URL directly
    fc = _get_firecrawl()
    if fc:
        wiki_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        content = _firecrawl_scrape(wiki_url)
        if content:
            header = (
                f"Research results for: {title}\n"
                f"Type: {source_type}\n"
                f"Author: {author}\n"
                f"---\n"
            )
            return header + content

    # Priority 3: Free public APIs (always works, no key needed)
    logger.info(f"Researching '{title}' via free APIs...")
    return _free_api_research(source_type, title, author)


def research_domain_sources(domain: str) -> dict[str, str]:
    """Research all sources for a domain and return title-to-content mapping.

    Args:
        domain: The domain name (e.g., "audio", "code")

    Returns:
        Dict mapping source title to researched text content
    """
    # Late import to avoid circular dependency with knowledge_acquisition
    from src.core.specialists.knowledge_acquisition import get_sources_for_domain

    sources = get_sources_for_domain(domain)
    if not sources:
        logger.warning(f"No curated sources found for domain '{domain}'")
        return {}

    results: dict[str, str] = {}
    for i, (source_type, title, author) in enumerate(sources):
        logger.info(f"Researching [{i+1}/{len(sources)}] {title}...")
        content = research_source(source_type, title, author)
        results[title] = content
        time.sleep(_RATE_LIMIT_DELAY)

    return results
