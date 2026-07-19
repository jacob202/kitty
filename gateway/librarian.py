"""High-reasoning judgment for Kitty's knowledge base curation."""
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from contracts.knowledge_pipeline import LibrarianReport
from gateway.llm_client import call_llm

logger = logging.getLogger("kitty.knowledge.librarian")

# Chunk sizes tuned per document type
_CHUNK_PROFILES = {
    "service_manual":  {"size": 256,  "overlap": 32},   # small — preserve numbered steps
    "textbook":        {"size": 768,  "overlap": 128},  # large — prose flows across paragraphs
    "textbook-chapter":{"size": 768,  "overlap": 128},  # alias for textbook
    "session_log":     {"size": 384,  "overlap": 48},   # medium — conversation turns
    "health_record":   {"size": 256,  "overlap": 32},   # small — clinical data is dense
    "data_table":      {"size": 128,  "overlap": 0},    # row-based, no overlap needed
    "general":         {"size": 512,  "overlap": 64},   # default
}

# Signals used to detect document type from filename + first 500 chars of text
_MANUAL_NAME_SIGNALS = {"manual", "service", "repair", "workshop", "haynes", "chilton",
                        "maintenance", "overhaul", "wiring", "schematic", "diagram",
                        "datasheet", "spec", "specification"}
_MANUAL_TEXT_SIGNALS = re.compile(
    r"(step \d+|torque|ft.?lb|nm\b|part\s+no|oem|exploded\s+view|"
    r"remove\s+and\s+replace|disconnect|reconnect|tighten|loosen|"
    r"warning:|caution:|note:|procedure|specification)", re.I
)
_HEALTH_NAME_SIGNALS = {"blood", "lab", "result", "medical", "health", "rx",
                        "prescription", "biopsy", "pathology", "ecg", "ekg"}
_BOOK_NAME_SIGNALS = {"textbook", "book", "chapter", "edition", "introduction",
                      "fundamentals", "principles", "guide", "handbook", "lesson", "lecture"}
_BOOK_TEXT_SIGNALS = re.compile(r"(chapter \d+|table of contents|bibliography|references|abstract|index|appendix)", re.I)
_SESSION_EXTENSIONS = {".jsonl", ".json"}


def detect_doc_type(path: Path, text_preview: str = "") -> str:
    """Infer document type from filename and content preview."""
    name_lower = path.stem.lower()
    name_words = set(re.split(r"[\s_\-\.]+", name_lower))
    suffix = path.suffix.lower()

    if suffix in _SESSION_EXTENSIONS:
        return "session_log"
    if suffix == ".csv":
        return "data_table"
    if name_words & _HEALTH_NAME_SIGNALS:
        return "health_record"
    if name_words & _MANUAL_NAME_SIGNALS:
        return "service_manual"
    if name_words & _BOOK_NAME_SIGNALS:
        return "textbook"
    # Content-based fallback for PDFs with generic names
    if text_preview:
        if _MANUAL_TEXT_SIGNALS.search(text_preview[:1000]):
            return "service_manual"
        if _BOOK_TEXT_SIGNALS.search(text_preview[:1000]):
            return "textbook"
    return "general"


_FAST_PATH_TYPES = {"session_log", "data_table"}


def generate_source_summary(source_name: str, text_preview: str, doc_type: str) -> LibrarianReport:
    """Assess the quality and authority of a document before ingestion.

    Fast-paths session logs and data tables — no LLM needed for those.
    """
    default_data = {
        "summary": f"A {doc_type} titled {source_name}.",
        "authority_score": 0.5,
        "relevance_period": "unknown",
        "pollution_warning": None,
        "needs_vision": (doc_type in ("service_manual", "textbook")),
        "primary_topic": "general",
    }

    if doc_type in _FAST_PATH_TYPES:
        return LibrarianReport(**default_data)

    prompt = f"""Analyze this source preview for a high-leverage personal knowledge base.

    SOURCE NAME: {source_name}
    TYPE: {doc_type}
    CONTENT PREVIEW:
    {text_preview[:4000]}

    TASK 1: SUMMARY
    Write a 2-3 sentence 'Source Brief' explaining what this is and its primary purpose.

    TASK 2: TASTE CHECK (Knowledge Quality & Safety)
    Assess the content against modern engineering and safety standards:
    1. AUTHORITY: Is this a gold-standard reference (e.g. factory service manual, academic textbook), or secondary/informal? (Score 0.0-1.0)
    2. RECENCY: Is the knowledge likely outdated or superseded?
    3. SAFETY CRITICAL: Does this document contain high-voltage warnings, hazardous material handling, or safety-critical procedures?
    4. POLLUTION RISK: Does this contain outdated theories that could lead to incorrect or dangerous repair actions today?

    Respond in JSON format:
    {{
      "summary": "...",
      "authority_score": 0.0-1.0,
      "relevance_period": "...",
      "safety_level": "high/medium/low",
      "pollution_warning": "...",
      "needs_vision": true/false,
      "primary_topic": "..."
    }}
    """

    payload: dict[str, Any] = {
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "max_tokens": 800,
        "temperature": 0.1,
    }

    ingest_model = os.environ.get("KITTY_INGEST_LLM_MODEL", "kitty-default")

    response_text = call_llm(
        messages=payload["messages"],
        response_format=payload["response_format"],
        max_tokens=800,
        temperature=0.1,
        timeout=45,
        model=ingest_model,
        operation="knowledge.librarian",
        metadata={"doc_type": doc_type, "source": source_name[:240]},
    )

    if not response_text:
        return LibrarianReport(**default_data)

    try:
        data = json.loads(response_text)

        # Normalize authority_score if it's on a 1-5 scale
        if "authority_score" in data:
            try:
                score = float(data["authority_score"])
                if score > 1.0:
                    data["authority_score"] = score / 5.0
            except (ValueError, TypeError):
                logger.warning(
                    "librarian authority_score normalization failed for %s: score=%r",
                    source_name, data.get("authority_score"),
                )

        # Ensure all keys exist
        return LibrarianReport(**{**default_data, **data})
    except Exception:
        logger.warning("librarian JSON parse or validation failed for %s", source_name)
        return LibrarianReport(**default_data)
