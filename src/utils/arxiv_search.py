#!/usr/bin/env python3
"""
ArXiv Paper Search Tool for Kitty
Search and retrieve academic papers from arXiv API
"""

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

ARXIV_API = "https://export.arxiv.org/api/query"

@dataclass
class Paper:
    """ArXiv paper"""
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    published: str
    categories: list[str]
    pdf_url: str

def search_papers(
    query: str,
    max_results: int = 5,
    sort_by: str = "submittedDate",
    sort_order: str = "descending"
) -> list[Paper]:
    """
    Search arXiv for papers

    Args:
        query: Search query (e.g., "transformer attention", "au:vaswani", "cat:cs.AI")
        max_results: Number of results
        sort_by: submittedDate, relevance, lastUpdatedDate
        sort_order: descending, ascending
    """
    params = {
        "search_query": f"all:{query.replace(' ', '+')}",
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order
    }

    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"

    with urllib.request.urlopen(url, timeout=30) as response:
        root = ET.fromstring(response.read())

    ns = {'a': 'http://www.w3.org/2005/Atom'}
    papers = []

    for entry in root.findall('a:entry', ns):
        arxiv_id = entry.find('a:id', ns).text.strip().split('/abs/')[-1]
        title = entry.find('a:title', ns).text.strip().replace('\n', ' ')

        authors = [
            a.find('a:name', ns).text
            for a in entry.findall('a:author', ns)
        ]

        abstract = entry.find('a:summary', ns).text.strip()
        published = entry.find('a:published', ns).text[:10]

        categories = [
            c.get('term')
            for c in entry.findall('a:category', ns)
        ]

        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

        papers.append(Paper(
            arxiv_id=arxiv_id,
            title=title,
            authors=authors,
            abstract=abstract,
            published=published,
            categories=categories,
            pdf_url=pdf_url
        ))

    return papers

def format_papers(papers: list[Paper]) -> str:
    """Format papers for display"""
    if not papers:
        return "No papers found."

    lines = []
    for i, p in enumerate(papers, 1):
        lines.append(f"{i}. [{p.arxiv_id}] {p.title}")
        lines.append(f"   Authors: {', '.join(p.authors[:3])}{' et al.' if len(p.authors) > 3 else ''}")
        lines.append(f"   Published: {p.published} | Categories: {', '.join(p.categories[:3])}")
        lines.append(f"   Abstract: {p.abstract[:200]}...")
        lines.append(f"   PDF: {p.pdf_url}")
        lines.append("")

    return "\n".join(lines)

def search(query: str, max_results: int = 5) -> str:
    """Convenience function for CLI usage"""
    papers = search_papers(query, max_results)
    return format_papers(papers)


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "transformer attention"
    print(search(q))
