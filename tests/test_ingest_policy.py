"""Tests for ingest curation policy."""
from pathlib import Path

from gateway.ingest_policy import bucket_for_path, score_ingest_candidate


def test_core_text_docs_score_high():
    # Avoid `/tmp/...`: ingest policy treats "tmp" as an exclusion marker on the path string.
    p = "/Users/jacobrizinski/Desktop/manuals/Claude Code Context Cleanup Guide.md"
    score, reasons = score_ingest_candidate(p)
    assert score >= 4
    assert bucket_for_path(p) == "core"
    assert "text_ext:.md" in reasons


def test_books_pdf_is_secondary_not_excluded():
    path = "/Users/jacobbrizinski/Desktop/Books/Learning/Speed Reading Workbook.PDF"
    score, reasons = score_ingest_candidate(path)
    assert score >= 1
    assert bucket_for_path(path) == "secondary"
    assert "book_ext:.pdf" in reasons


def test_noise_files_are_excluded():
    assert bucket_for_path("/Users/jacobbrizinski/Desktop/Books/Electronics/Google Search Scraper.csv") == "excluded"
    assert bucket_for_path("/Users/jacobbrizinski/Desktop/Books/FromDocuments/cover.jpg") == "excluded"
