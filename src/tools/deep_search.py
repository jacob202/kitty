"""
Deep search: Tavily search → scrape top pages → synthesize with LLM.
Used by /deepsearch command and as a tool for agents.

Extended with recursive web crawling capabilities.
"""

import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from src.utils.web_crawler import CrawlVectorStore, WebCrawler, format_crawl_result_for_llm

    _CRAWLER_AVAILABLE = True
except ImportError:
    _CRAWLER_AVAILABLE = False
    # Will be imported at runtime when called from cli.py

_SCRAPE_TIMEOUT = 8
_MAX_PAGE_CHARS = 4000
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}
_SKIP_DOMAINS = {
    "reddit.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
}


def _scrape_url(url: str) -> str | None:
    """Fetch URL and return cleaned body text, or None on failure."""
    try:
        domain = url.split("/")[2] if "/" in url else url
        if any(s in domain for s in _SKIP_DOMAINS):
            return None
        r = httpx.get(url, headers=_HEADERS, timeout=_SCRAPE_TIMEOUT, follow_redirects=True)
        if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        # Remove noise tags
        for tag in soup(
            ["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]
        ):
            tag.decompose()
        # Prefer article/main, fallback to body
        body = soup.find("article") or soup.find("main") or soup.find("body")
        if not body:
            return None
        text = " ".join(body.get_text(" ", strip=True).split())
        return text[:_MAX_PAGE_CHARS] if text else None
    except Exception:
        return None


def deep_search(query: str, tavily_client, max_results: int = 5, scrape: bool = True) -> dict:
    """
    Run a Tavily search, optionally scrape top pages, return structured results.

    Returns:
        {
            "query": str,
            "results": [{"title", "url", "snippet", "body"}],
            "scraped_count": int,
        }
    """
    try:
        resp = tavily_client.search(
            query,
            max_results=max_results,
            search_depth="advanced",
            include_raw_content=False,
        )
    except Exception as e:
        return {"query": query, "error": str(e), "results": []}

    results = []
    scraped = 0
    for r in resp.get("results", []):
        entry = {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", "")[:600],
            "body": "",
        }
        if scrape:
            body = _scrape_url(r.get("url", ""))
            if body:
                entry["body"] = body
                scraped += 1
        results.append(entry)

    return {
        "query": query,
        "results": results,
        "scraped_count": scraped,
    }


def format_for_llm(search_result: dict, max_chars: int = 12000) -> str:
    """Format deep search results into a compact block for LLM synthesis."""
    lines = [f'Deep search: "{search_result["query"]}"', ""]
    total = 0
    for i, r in enumerate(search_result.get("results", []), 1):
        block = f"[{i}] {r['title']}\n{r['url']}\n"
        content = r["body"] if r["body"] else r["snippet"]
        block += content + "\n"
        if total + len(block) > max_chars:
            break
        lines.append(block)
        total += len(block)
    return "\n".join(lines)


def deep_search_with_crawl(
    query: str,
    tavily_client,
    crawl_depth: int = 0,
    max_results: int = 5,
    max_crawl_pages: int = 20,
    store_in_vector_db: bool = True,
) -> dict:
    """
    Run Tavily search with optional recursive crawling of results.

    Args:
        query: Search query
        tavily_client: Tavily client instance
        crawl_depth: How many levels to crawl (0 = just search results, 1 = results + links, etc.)
        max_results: Number of search results to fetch
        max_crawl_pages: Maximum pages to crawl total
        store_in_vector_db: Whether to store crawled content in vector DB

    Returns:
        {
            "query": str,
            "results": [{"title", "url", "snippet", "body", "summary"}],
            "scraped_count": int,
            "crawl_result": CrawlResult (if crawl_depth > 0),
            "vector_store_stats": dict (if store_in_vector_db),
        }
    """
    # First, run standard deep search
    search_result = deep_search(
        query, tavily_client, max_results=max_results, scrape=(crawl_depth == 0)
    )

    # If crawling is disabled or not available, return standard results
    if crawl_depth == 0 or not _CRAWLER_AVAILABLE:
        return {
            **search_result,
            "crawl_result": None,
            "vector_store_stats": None,
        }

    # Initialize vector store if requested
    vector_store = None
    vector_stats = None
    if store_in_vector_db:
        try:
            vector_store = CrawlVectorStore()
        except Exception as e:
            print(f"[WARN] Vector store initialization failed: {e}")

    # Run crawler starting from search results
    try:
        crawler = WebCrawler(
            max_depth=crawl_depth,
            max_pages=max_crawl_pages,
            respect_robots=True,
            vector_store=vector_store,
        )

        # Extract URLs from search results
        seed_urls = [r["url"] for r in search_result.get("results", []) if "url" in r]

        if not seed_urls:
            return {
                **search_result,
                "crawl_result": None,
                "vector_store_stats": None,
                "error": "No URLs to crawl from search results",
            }

        # Perform crawl
        crawl_result = crawler.crawl(
            seed_urls=seed_urls,
            query_context=query,
            progress_callback=lambda count, total, url: print(
                f"  Crawling {count}/{total}: {url[:60]}..."
            ),
        )

        # Merge crawl results into search results
        crawled_pages_dict = {p.url: p for p in crawl_result.pages}

        for result in search_result.get("results", []):
            url = result.get("url", "")
            if url in crawled_pages_dict:
                page = crawled_pages_dict[url]
                result["body"] = page.content
                result["summary"] = page.summary

        # Add additional crawled pages that weren't in search results
        existing_urls = {r["url"] for r in search_result.get("results", [])}
        for page in crawl_result.pages:
            if page.url not in existing_urls:
                search_result["results"].append(
                    {
                        "title": page.title or "Crawled Page",
                        "url": page.url,
                        "snippet": page.summary[:300] if page.summary else page.content[:300],
                        "body": page.content,
                        "summary": page.summary,
                        "crawled_depth": page.depth,
                    }
                )

        # Update stats
        search_result["scraped_count"] = len(crawl_result.pages)
        search_result["crawl_result"] = crawl_result
        search_result["crawl_stats"] = {
            "total_pages": crawl_result.total_pages,
            "duration_seconds": round(crawl_result.crawl_duration, 2),
            "unique_domains": len(crawl_result.unique_domains),
            "errors": len(crawl_result.errors),
        }

        # Get vector store stats
        if vector_store:
            try:
                vector_stats = vector_store.get_stats()
                search_result["vector_store_stats"] = vector_stats
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to get vector stats: {e}")

    except Exception as e:
        search_result["crawl_error"] = str(e)
        search_result["crawl_result"] = None
        search_result["vector_store_stats"] = None

    return search_result


def format_crawl_search_for_llm(search_result: dict, max_chars: int = 15000) -> str:
    """
    Format deep search with crawl results for LLM synthesis.
    Includes both search results and crawled content with summaries.
    """
    lines = [f'Crawl Search: "{search_result["query"]}"', ""]

    # Add crawl stats if available
    crawl_stats = search_result.get("crawl_stats")
    if crawl_stats:
        lines.append(
            f"Crawl Stats: {crawl_stats['total_pages']} pages from "
            f"{crawl_stats['unique_domains']} domains in {crawl_stats['duration_seconds']}s"
        )
        lines.append("")

    # Format results
    total = 0
    for i, r in enumerate(search_result.get("results", []), 1):
        block = f"[{i}] {r.get('title', 'Untitled')}\n{r.get('url', '')}\n"

        # Prefer summary, then body, then snippet
        content = r.get("summary", "") or r.get("body", "") or r.get("snippet", "")
        if content:
            block += content + "\n"

        # Add depth indicator if crawled
        if r.get("crawled_depth") is not None:
            block += f"[Crawl depth: {r['crawled_depth']}]\n"

        block += "\n"

        if total + len(block) > max_chars:
            remaining = len(search_result.get("results", [])) - i + 1
            if remaining > 0:
                lines.append(f"... ({remaining} more results)\n")
            break

        lines.append(block)
        total += len(block)

    return "\n".join(lines)
