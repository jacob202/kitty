#!/usr/bin/env python3
"""Fetch book info for all curated sources across all domains.

Usage:
    python scripts/fetch_books.py                  # research only, no storage
    python scripts/fetch_books.py --store           # research + store in LightRAG
    python scripts/fetch_books.py --domain audio    # single domain only
    python scripts/fetch_books.py --store --domain code

Requires: requests (for free APIs: OpenLibrary, Wikipedia, ArXiv)
Optional: EXA_API_KEY env var for better results via Exa AI
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path so imports work from anywhere
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("fetch_books")


def get_sources() -> dict:
    """Get all curated sources across all domains."""
    from src.core.specialists.knowledge_acquisition import DOMAIN_SOURCES

    return DOMAIN_SOURCES


def research_source(source_type: str, title: str, author: str) -> str:
    """Research a single source via the web research engine."""
    from src.core.specialists.knowledge_researcher import research_source as _research

    return _research(source_type, title, author)


def store_in_lightrag(content: str, title: str, source_type: str, author: str, domain: str) -> bool:
    """Store researched content in LightRAG for future queries."""
    try:
        from src.memory.lightrag_store import LightRAGStore

        store = LightRAGStore()
        doc_text = (
            f"Source type: {source_type}\n"
            f"Title: {title}\n"
            f"Author: {author}\n"
            f"Domain: {domain}\n"
            f"---\n{content}"
        )
        store.add_document(doc_text, metadata={
            "source": title,
            "type": source_type,
            "author": author,
            "domain": domain,
        })
        store.close()
        return True
    except Exception as e:
        logger.warning(f"  ⚠️  LightRAG storage failed: {e}")
        return False


def run_loop(domains: list[str] | None = None, store: bool = False) -> int:
    """Run the book acquisition loop.

    Returns total number of sources successfully researched.
    """
    all_sources = get_sources()

    if domains:
        for d in domains:
            if d not in all_sources:
                logger.warning(f"Unknown domain '{d}' — skipping")
        target_domains = {d: all_sources[d] for d in domains if d in all_sources}
    else:
        target_domains = all_sources

    total_sources = sum(len(srcs) for srcs in target_domains.values())
    researched = 0
    succeeded = 0

    logger.info(f"Found {total_sources} sources across {len(target_domains)} domains")
    if store:
        logger.info("Storage in LightRAG: ENABLED (may be slow due to LLM entity extraction)")

    for domain, sources in sorted(target_domains.items()):
        logger.info(f"\n{'='*60}")
        logger.info(f"Domain: {domain} ({len(sources)} sources)")
        logger.info(f"{'='*60}")

        for i, (source_type, title, author) in enumerate(sources, 1):
            researched += 1
            logger.info(f"  [{researched}/{total_sources}] {title} ({author})")

            try:
                content = research_source(source_type, title, author)
                if "No web research results" in content:
                    logger.info(f"    ⚠️  No results found")
                else:
                    succeeded += 1
                    logger.info(f"    ✅ Got {len(content)} chars")

                # Store in LightRAG if requested
                if store and "No web research results" not in content:
                    logger.info(f"    📦 Storing in LightRAG...")
                    if store_in_lightrag(content, title, source_type, author, domain):
                        logger.info(f"    ✅ Stored in LightRAG")

            except Exception as e:
                logger.error(f"    ❌ Error: {e}")

            # Polite delay between requests
            if i < len(sources):
                time.sleep(0.5)

    logger.info(f"\n{'='*60}")
    logger.info(f"Done! {succeeded}/{total_sources} sources successfully researched.")
    if store:
        logger.info("All successfully researched sources stored in LightRAG.")
    logger.info(f"{'='*60}")

    return succeeded


def main():
    parser = argparse.ArgumentParser(description="Fetch book info for curated sources")
    parser.add_argument(
        "--store",
        action="store_true",
        help="Store researched content in LightRAG (requires Ollama running)",
    )
    parser.add_argument(
        "--domain",
        action="append",
        dest="domains",
        help="Only process specific domain(s) (can be used multiple times)",
    )
    parser.add_argument(
        "--list-domains",
        action="store_true",
        help="List all available domains and exit",
    )
    args = parser.parse_args()

    if args.list_domains:
        sources = get_sources()
        print("Available domains:")
        for domain, srcs in sorted(sources.items()):
            print(f"  {domain}: {len(srcs)} sources")
        return

    run_loop(domains=args.domains, store=args.store)


if __name__ == "__main__":
    main()
