"""
Recursive Web Crawler with intelligent summarization and vector storage.
Extends deep search capabilities with multi-level crawling.
"""

import hashlib
import time
import urllib.robotparser
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# Constants matching existing patterns
_SCRAPE_TIMEOUT = 10
_MAX_PAGE_CHARS = 6000
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}
_SKIP_DOMAINS = {
    "reddit.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "tiktok.com",
    "linkedin.com",
}
_SKIP_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".zip", ".exe", ".dmg", ".mp4", ".mp3"}


@dataclass
class CrawledPage:
    """Represents a crawled page with metadata."""

    url: str
    title: str = ""
    content: str = ""
    summary: str = ""
    links: list[str] = field(default_factory=list)
    depth: int = 0
    crawl_time: float = 0.0
    status_code: int | None = None
    error: str | None = None
    content_hash: str = ""


@dataclass
class CrawlResult:
    """Result of a crawl operation."""

    seed_url: str
    pages: list[CrawledPage] = field(default_factory=list)
    total_pages: int = 0
    errors: list[str] = field(default_factory=list)
    crawl_duration: float = 0.0
    unique_domains: set[str] = field(default_factory=set)


class RobotsChecker:
    """Handles robots.txt parsing and caching with respect for crawl delays."""

    def __init__(self, cache_ttl: int = 3600):
        self._cache: dict[str, tuple[urllib.robotparser.RobotFileParser, float]] = {}
        self._cache_ttl = cache_ttl
        self._crawl_delays: dict[str, float] = {}
        self._last_crawl: dict[str, float] = {}

    def _get_robots_url(self, url: str) -> str:
        """Extract robots.txt URL from any page URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        return urlparse(url).netloc

    def _get_robot_parser(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        """Get cached or fresh robot parser for a URL's domain."""
        robots_url = self._get_robots_url(url)
        domain = self._get_domain(url)

        # Check cache
        if domain in self._cache:
            parser, timestamp = self._cache[domain]
            if time.time() - timestamp < self._cache_ttl:
                return parser

        # Fetch fresh robots.txt
        try:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(robots_url)
            parser.read()
            self._cache[domain] = (parser, time.time())

            # Extract crawl delay
            crawl_delay = parser.crawl_delay(_HEADERS["User-Agent"])
            if crawl_delay:
                self._crawl_delays[domain] = crawl_delay

            return parser
        except Exception:
            return None

    def can_fetch(self, url: str) -> bool:
        """Check if crawling is allowed by robots.txt."""
        parser = self._get_robot_parser(url)
        if parser is None:
            return True  # Allow if no robots.txt or error
        return parser.can_fetch(_HEADERS["User-Agent"], url)

    def get_crawl_delay(self, url: str) -> float:
        """Get required crawl delay for domain."""
        domain = self._get_domain(url)

        # Check cached delay
        if domain in self._crawl_delays:
            return self._crawl_delays[domain]

        # Fetch and check
        parser = self._get_robot_parser(url)
        if parser:
            delay = parser.crawl_delay(_HEADERS["User-Agent"])
            if delay:
                self._crawl_delays[domain] = delay
                return delay

        return 0.0  # No delay required

    def respect_crawl_delay(self, url: str):
        """Sleep if needed to respect crawl delay."""
        domain = self._get_domain(url)
        delay = self.get_crawl_delay(url)

        if delay > 0 and domain in self._last_crawl:
            elapsed = time.time() - self._last_crawl[domain]
            if elapsed < delay:
                time.sleep(delay - elapsed)

        self._last_crawl[domain] = time.time()


class WebCrawler:
    """
    Recursive web crawler with content extraction, deduplication, and summarization.

    Features:
    - Multi-level recursive crawling
    - Content deduplication via hashing
    - robots.txt respect with crawl delay handling
    - Intelligent content extraction
    - Optional LLM-based summarization
    - Vector database storage integration
    """

    def __init__(
        self,
        max_depth: int = 2,
        max_pages: int = 50,
        max_links_per_page: int = 20,
        respect_robots: bool = True,
        use_llm_summary: bool = True,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "dolphin-llama3:latest",
        vector_store=None,
    ):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.max_links_per_page = max_links_per_page
        self.respect_robots = respect_robots
        self.use_llm_summary = use_llm_summary
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.vector_store = vector_store

        self._robots_checker = RobotsChecker()
        self._seen_hashes: set[str] = set()
        self._seen_urls: set[str] = set()
        self._crawled_count = 0

    def _should_skip_url(self, url: str) -> bool:
        """Check if URL should be skipped based on domain or extension."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Skip social media and video sites
        if any(skip in domain for skip in _SKIP_DOMAINS):
            return True

        # Skip non-HTML files
        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in _SKIP_EXTENSIONS):
            return True

        return False

    def _normalize_url(self, url: str, base_url: str) -> str | None:
        """Normalize and validate URL."""
        try:
            # Join relative URLs
            full_url = urljoin(base_url, url)
            parsed = urlparse(full_url)

            # Only HTTP/HTTPS
            if parsed.scheme not in ("http", "https"):
                return None

            # Remove fragments and normalize
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                normalized += f"?{parsed.query}"

            return normalized
        except Exception:
            return None

    def _extract_content(self, html: str, url: str) -> tuple[str, str, list[str]]:
        """
        Extract meaningful content from HTML.

        Returns:
            Tuple of (title, content_text, extracted_links)
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Extract title
            title = ""
            if soup.title:
                title = soup.title.get_text(strip=True)
            elif soup.find("h1"):
                title = soup.find("h1").get_text(strip=True)

            # Remove noise tags
            for tag in soup(
                [
                    "script",
                    "style",
                    "nav",
                    "footer",
                    "header",
                    "aside",
                    "form",
                    "noscript",
                    "iframe",
                    "ads",
                ]
            ):
                tag.decompose()

            # Extract main content (prioritize article/main/content areas)
            content_area = (
                soup.find("article")
                or soup.find("main")
                or soup.find(
                    "div",
                    class_=lambda x: (
                        x and any(c in str(x).lower() for c in ["content", "article", "post"])
                    ),
                )
                or soup.find(
                    "div",
                    id=lambda x: (
                        x and any(c in str(x).lower() for c in ["content", "article", "main"])
                    ),
                )
                or soup.find("body")
            )

            if content_area:
                # Get text and clean it
                text = content_area.get_text(" ", strip=True)
                # Normalize whitespace
                text = " ".join(text.split())
                # Truncate to max chars
                text = text[:_MAX_PAGE_CHARS]
            else:
                text = ""

            # Extract links
            links = []
            base_domain = urlparse(url).netloc
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                normalized = self._normalize_url(href, url)
                if normalized:
                    # Prefer same-domain links for crawling
                    link_domain = urlparse(normalized).netloc
                    if link_domain == base_domain:
                        links.insert(0, normalized)  # Prioritize same-domain
                    else:
                        links.append(normalized)

            return title, text, links[: self.max_links_per_page]

        except Exception as e:
            return "", f"Error extracting content: {str(e)}", []

    def _compute_hash(self, content: str) -> str:
        """Compute hash for deduplication."""
        return hashlib.md5(content.encode()).hexdigest()

    def _is_duplicate(self, content: str) -> bool:
        """Check if content is duplicate."""
        content_hash = self._compute_hash(content)
        if content_hash in self._seen_hashes:
            return True
        self._seen_hashes.add(content_hash)
        return False

    def _summarize_with_ollama(
        self, content: str, title: str, url: str, summary_length: str = "standard"
    ) -> str:
        """
        Generate summary using local Ollama LLM.

        Args:
            content: Page content to summarize
            title: Page title
            url: Page URL (for citation)
            summary_length: 'brief' (1-2 sentences), 'standard' (2-3 sentences), or 'detailed' (paragraph)

        Returns:
            Summary text with source citation
        """
        if not self.use_llm_summary:
            return ""

        # Configure summary length
        length_configs = {
            "brief": {
                "sentences": "1-2 sentences",
                "max_tokens": 50,
                "description": "concise summary",
            },
            "standard": {
                "sentences": "2-3 sentences",
                "max_tokens": 150,
                "description": "standard summary",
            },
            "detailed": {
                "sentences": "a detailed paragraph",
                "max_tokens": 400,
                "description": "comprehensive summary",
            },
        }

        config = length_configs.get(summary_length, length_configs["standard"])

        try:
            # Truncate content for summarization based on length
            max_chars = {"brief": 1500, "standard": 3000, "detailed": 6000}
            truncated = (
                content[: max_chars.get(summary_length, 3000)]
                if len(content) > max_chars.get(summary_length, 3000)
                else content
            )

            prompt = f"""Summarize the following web page content in {config["sentences"]}.
Extract the key facts and main points relevant to the topic being researched.

Title: {title}
URL: {url}

Content:
{truncated}

Provide a {config["description"]} that:
- Captures the main findings
- Includes relevant technical details
- Notes any limitations or caveats

Summary:"""

            response = httpx.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": config["max_tokens"]},
                },
                timeout=30,
            )
            response.raise_for_status()

            result = response.json()
            summary = result.get("response", "").strip()

            # Add source citation
            return f"{summary}\n[Source: {url}]"

        except Exception:
            # Return excerpt as fallback
            excerpt = content[:200] if len(content) > 200 else content
            return f"Excerpt: {excerpt}...\n[Source: {url}]"

    def synthesize_multiple_sources(
        self, pages: list[CrawledPage], original_query: str, summary_length: str = "standard"
    ) -> dict[str, Any]:
        """
        Synthesize multiple crawled pages into a coherent research report.

        Args:
            pages: List of CrawledPage objects to synthesize
            original_query: The original search query for context
            summary_length: 'brief', 'standard', or 'detailed'

        Returns:
            Dict with synthesized report and source attribution
        """
        if not pages:
            return {
                "report": "No pages to synthesize.",
                "sources": [],
                "key_findings": [],
            }

        # Build context from pages
        page_contexts = []
        for i, page in enumerate(pages, 1):
            page_contexts.append(
                f"[Source {i}]: {page.title}\nURL: {page.url}\n{page.summary or page.content[:500]}..."
            )

        context_text = "\n\n".join(page_contexts)

        # Determine synthesis prompt based on length
        synthesis_configs = {
            "brief": {"max_tokens": 300, "instruction": "2-3 paragraph synthesis"},
            "standard": {"max_tokens": 600, "instruction": "detailed synthesis with sections"},
            "detailed": {
                "max_tokens": 1200,
                "instruction": "comprehensive research report with all findings",
            },
        }

        config = synthesis_configs.get(summary_length, synthesis_configs["standard"])

        try:
            synthesis_prompt = f"""You are synthesizing research from multiple web sources.
Create a coherent {config["instruction"]} based on the sources below.

ORIGINAL QUERY: {original_query}

SOURCES:
{context_text}

INSTRUCTIONS:
1. Synthesize information from all sources into a coherent report
2. Clearly attribute findings to specific sources (use [Source N] notation)
3. Identify agreements and disagreements between sources
4. Highlight the most relevant findings for the query
5. Note any conflicting information

RESEARCH REPORT:"""

            response = httpx.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": synthesis_prompt,
                    "stream": False,
                    "options": {"num_predict": config["max_tokens"]},
                },
                timeout=60,
            )
            response.raise_for_status()

            result = response.json()
            report = result.get("response", "").strip()

            # Extract key findings
            findings = self._extract_key_findings(report, original_query)

            return {
                "report": report,
                "sources": [
                    {"index": i + 1, "title": p.title, "url": p.url} for i, p in enumerate(pages)
                ],
                "key_findings": findings,
                "source_count": len(pages),
            }

        except Exception as e:
            # Fallback to simple concatenation
            return {
                "report": "\n\n".join(
                    f"## {p.title}\n{p.url}\n{p.summary or p.content[:500]}" for p in pages
                ),
                "sources": [
                    {"index": i + 1, "title": p.title, "url": p.url} for i, p in enumerate(pages)
                ],
                "key_findings": [],
                "error": str(e),
            }

    def _extract_key_findings(self, report: str, query: str) -> list[str]:
        """Extract key findings from synthesized report."""
        try:
            prompt = f"""From this research report, extract 3-5 key findings most relevant to the query.
Format as a bullet list.

Query: {query}

Report:
{report[:2000]}

Key Findings:"""

            response = httpx.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 200},
                },
                timeout=30,
            )
            response.raise_for_status()

            result = response.json()
            findings_text = result.get("response", "").strip()

            # Parse findings (simple extraction of lines starting with - or *)
            findings = [
                line.lstrip("-* ").strip()
                for line in findings_text.split("\n")
                if line.strip().startswith(("-", "*"))
            ]

            return findings[:5]  # Limit to 5 findings

        except Exception:
            return []

    def _store_in_vector_db(self, page: CrawledPage, query_context: str = ""):
        """Store crawled page in vector database if available."""
        if not self.vector_store:
            return

        try:
            # Prepare document for storage
            doc_id = f"crawl_{self._compute_hash(page.url)}"

            # Combine content for embedding
            full_text = f"""Title: {page.title}
URL: {page.url}
Summary: {page.summary}
Content: {page.content[:2000]}"""

            metadata = {
                "url": page.url,
                "title": page.title,
                "summary": page.summary,
                "depth": page.depth,
                "crawl_time": page.crawl_time,
                "query_context": query_context,
            }

            # Store in vector DB (interface depends on implementation)
            if hasattr(self.vector_store, "add_document"):
                self.vector_store.add_document(doc_id, full_text, metadata)
            elif hasattr(self.vector_store, "upsert"):
                self.vector_store.upsert({doc_id: {"content": full_text, **metadata}})

        except Exception:
            # Non-fatal: log but don't fail crawl
            pass

    def _fetch_page(self, url: str) -> tuple[str | None, int | None, str | None]:
        """Fetch page content with error handling."""
        try:
            # Respect robots.txt crawl delay
            if self.respect_robots:
                self._robots_checker.respect_crawl_delay(url)

            response = httpx.get(
                url, headers=_HEADERS, timeout=_SCRAPE_TIMEOUT, follow_redirects=True
            )

            # Check content type
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                return None, response.status_code, f"Non-HTML content: {content_type}"

            return response.text, response.status_code, None

        except httpx.TimeoutException:
            return None, None, "Timeout"
        except httpx.RequestError as e:
            return None, None, f"Request error: {str(e)}"
        except Exception as e:
            return None, None, f"Error: {str(e)}"

    def crawl(
        self, seed_urls: list[str], query_context: str = "", progress_callback=None
    ) -> CrawlResult:
        """
        Crawl starting from seed URLs to specified depth.

        Args:
            seed_urls: Starting URLs to crawl
            query_context: Context for vector storage (e.g., original search query)
            progress_callback: Optional callback(page_count, total_pages, current_url)

        Returns:
            CrawlResult with all crawled pages
        """
        start_time = time.time()
        result = CrawlResult(seed_url=seed_urls[0] if seed_urls else "")

        # Queue items: (url, depth)
        queue: deque[tuple[str, int]] = deque((url, 0) for url in seed_urls)

        for url in seed_urls:
            self._seen_urls.add(url)
            result.unique_domains.add(urlparse(url).netloc)

        while queue and self._crawled_count < self.max_pages:
            url, depth = queue.popleft()

            # Skip if exceeds max depth
            if depth > self.max_depth:
                continue

            # Check robots.txt
            if self.respect_robots and not self._robots_checker.can_fetch(url):
                result.errors.append(f"Blocked by robots.txt: {url}")
                continue

            # Skip unwanted URLs
            if self._should_skip_url(url):
                continue

            # Fetch page
            page_start = time.time()
            html, status_code, error = self._fetch_page(url)

            if error:
                result.errors.append(f"{url}: {error}")
                continue

            if not html:
                continue

            # Extract content
            title, content, links = self._extract_content(html, url)

            # Deduplicate
            if self._is_duplicate(content):
                continue

            # Generate summary
            summary = self._summarize_with_ollama(content, title, url)

            # Create page record
            page = CrawledPage(
                url=url,
                title=title,
                content=content,
                summary=summary,
                links=links,
                depth=depth,
                crawl_time=time.time() - page_start,
                status_code=status_code,
                content_hash=self._compute_hash(content),
            )

            result.pages.append(page)
            self._crawled_count += 1

            # Store in vector DB
            self._store_in_vector_db(page, query_context)

            # Progress callback
            if progress_callback:
                progress_callback(self._crawled_count, self.max_pages, url)

            # Queue child links for next depth
            if depth < self.max_depth:
                for link in links:
                    if link not in self._seen_urls and not self._should_skip_url(link):
                        self._seen_urls.add(link)
                        queue.append((link, depth + 1))
                        result.unique_domains.add(urlparse(link).netloc)

        result.total_pages = len(result.pages)
        result.crawl_duration = time.time() - start_time

        return result

    def crawl_single(self, url: str) -> CrawledPage | None:
        """Crawl a single URL without recursion."""
        if self._should_skip_url(url):
            return None

        if self.respect_robots and not self._robots_checker.can_fetch(url):
            return None

        html, status_code, error = self._fetch_page(url)

        if error or not html:
            return CrawledPage(url=url, error=error or "No content", status_code=status_code)

        title, content, links = self._extract_content(html, url)
        summary = self._summarize_with_ollama(content, title, url)

        return CrawledPage(
            url=url,
            title=title,
            content=content,
            summary=summary,
            links=links[: self.max_links_per_page],
            depth=0,
            status_code=status_code,
            content_hash=self._compute_hash(content),
        )


class CrawlVectorStore:
    """
    Vector storage wrapper for crawled content using ChromaDB.
    Simplified interface for storing and searching crawled documents.
    """

    def __init__(self, collection_name: str = "web_crawls", persist_dir: str = "./data/chromadb"):
        self.collection_name = collection_name
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._collection = None
        self._embedding_dim = 768  # Default for nomic-embed-text

    def _get_collection(self):
        """Lazy initialization of ChromaDB collection."""
        if self._collection is not None:
            return self._collection

        try:
            import chromadb
            from chromadb.config import Settings

            client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=Settings(allow_reset=True, anonymized_telemetry=False),
            )

            self._collection = client.get_or_create_collection(
                name=self.collection_name, metadata={"hnsw:space": "cosine"}
            )

            return self._collection

        except ImportError:
            raise ImportError("chromadb not installed. Run: pip install chromadb")

    def _get_embedding(self, text: str) -> list[float]:
        """Generate embedding using Ollama."""
        try:
            response = httpx.post(
                "http://localhost:11434/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text[:8000]},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception:
            # Fallback: simple hash-based embedding
            import numpy as np

            hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
            np.random.seed(hash_val)
            return np.random.randn(self._embedding_dim).tolist()

    def add_document(self, doc_id: str, text: str, metadata: dict[str, Any]):
        """Add a document to the vector store."""
        collection = self._get_collection()
        embedding = self._get_embedding(text)

        collection.upsert(
            ids=[doc_id], embeddings=[embedding], documents=[text], metadatas=[metadata]
        )

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search for similar documents."""
        collection = self._get_collection()
        query_embedding = self._get_embedding(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )

        # Format results
        formatted = []
        if results and results["ids"]:
            for i in range(len(results["ids"][0])):
                formatted.append(
                    {
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i] if results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                    }
                )

        return formatted

    def get_stats(self) -> dict[str, Any]:
        """Get collection statistics."""
        try:
            collection = self._get_collection()
            count = collection.count()
            return {"document_count": count, "collection": self.collection_name}
        except Exception as e:
            return {"error": str(e)}


def format_crawl_result_for_llm(result: CrawlResult, max_chars: int = 12000) -> str:
    """Format crawl results into a compact block for LLM synthesis."""
    lines = [
        f'Crawl Results for: "{result.seed_url}"',
        f"Pages crawled: {result.total_pages} | Depth: {len(set(p.depth for p in result.pages))} levels | Duration: {result.crawl_duration:.1f}s",
        "",
    ]

    total = 0
    for i, page in enumerate(result.pages, 1):
        block = f"[{i}] {page.title}\n{page.url}\n"

        # Use summary if available, otherwise content
        text = page.summary if page.summary else page.content
        block += text + "\n"

        if total + len(block) > max_chars:
            lines.append(f"... ({result.total_pages - i + 1} more pages)\n")
            break

        lines.append(block)
        total += len(block)

    if result.errors:
        lines.append(f"\nErrors ({len(result.errors)}):")
        for error in result.errors[:5]:
            lines.append(f"  - {error}")

    return "\n".join(lines)


# Convenience function for integration
def crawl_from_search_results(
    search_results: list[dict[str, str]],
    query: str,
    crawl_depth: int = 1,
    max_pages: int = 20,
    store_in_vector_db: bool = True,
) -> CrawlResult:
    """
    Crawl starting from search result URLs.

    Args:
        search_results: List of dicts with 'url' keys from search
        query: Original search query (for context)
        crawl_depth: How many levels to crawl (0 = just results, 1 = results + links, etc.)
        max_pages: Maximum total pages to crawl
        store_in_vector_db: Whether to store in vector database

    Returns:
        CrawlResult with all crawled data
    """
    urls = [r["url"] for r in search_results if "url" in r]

    vector_store = None
    if store_in_vector_db:
        try:
            vector_store = CrawlVectorStore()
        except Exception:
            pass  # Continue without vector store if not available

    crawler = WebCrawler(
        max_depth=crawl_depth,
        max_pages=max_pages,
        respect_robots=True,
        vector_store=vector_store,
    )

    return crawler.crawl(urls, query_context=query)
