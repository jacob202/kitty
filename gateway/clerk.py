"""Dumb extraction and preprocessing for Kitty's knowledge base."""

import hashlib
import json
import logging
import os
import re
from pathlib import Path

from contracts.knowledge_pipeline import VisualExtraction
from gateway import vision

logger = logging.getLogger("kitty.knowledge.clerk")


def preprocess_text(text: str) -> str:
    """Clean and normalize text before chunking."""
    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    # Remove excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip non-printable characters except basic ones
    text = "".join(c for c in text if c.isprintable() or c in "\n\r\t")
    return text.strip()


def _get_content_hash(text: str) -> str:
    """Generate SHA-256 hash of text."""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _extract_visual_descriptions(path: Path) -> list[VisualExtraction]:
    """Render PDF pages or process image files to get LLM technical descriptions."""
    description = vision.analyze_file(path)
    if not description:
        return []
    return [VisualExtraction(text=description)]


def _extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    """Extract text from PDF page by page using PyMuPDF."""
    pages = []
    try:
        import fitz

        doc = fitz.open(str(path))
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                pages.append((i + 1, text))
        doc.close()
    except Exception as e:
        logger.warning("PDF page extraction failed for %s: %s", path.name, e)
    return pages


def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    elif suffix == ".epub":
        return _extract_epub(path)
    elif suffix in {".mobi", ".azw3"}:
        return _extract_mobi(path)
    elif suffix == ".docx":
        return _extract_docx(path)
    elif suffix == ".rtf":
        return _extract_rtf(path)
    elif suffix == ".csv":
        return _extract_csv(path)
    elif suffix == ".jsonl":
        return _extract_jsonl_session(path)
    elif suffix == ".json":
        try:
            first_char = path.read_text(errors="ignore").lstrip()[:1]
        except Exception:
            logger.warning("Cannot read first char of %s for JSON type detection", path.name)
            first_char = ""
        if first_char == "[":
            return _extract_chatgpt_json(path)
        return _extract_jsonl_session(path)
    elif suffix in {".txt", ".md", ".rst"}:
        return path.read_text(errors="ignore")
    else:
        try:
            return path.read_text(errors="ignore")
        except Exception:
            logger.warning("Cannot read file %s", path.name)
            return ""


def _extract_docx(path: Path) -> str:
    """Extract text from Word .docx files."""
    try:
        from docx import Document

        doc = Document(path)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    except Exception as e:
        logger.warning("DOCX extraction failed for %s: %s", path.name, e)
        return ""


def _extract_rtf(path: Path) -> str:
    """Extract text from .rtf files using striprtf."""
    try:
        from striprtf.striprtf import rtf_to_text

        content = path.read_text(errors="ignore")
        return rtf_to_text(content)
    except Exception as e:
        logger.warning("RTF extraction failed for %s: %s", path.name, e)
        return ""


def _extract_epub(path: Path) -> str:
    """Extract text from EPUB files using ebooklib and BeautifulSoup."""
    try:
        # Suppress ebooklib warnings about non-standard EPUBs
        import warnings

        import ebooklib
        from bs4 import BeautifulSoup
        from ebooklib import epub

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            book = epub.read_epub(str(path))

        chapters = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), "html.parser")
                # Remove script and style elements
                for script_or_style in soup(["script", "style"]):
                    script_or_style.decompose()
                text = soup.get_text(separator=" ")
                # Clean up whitespace
                clean_text = " ".join(text.split())
                if clean_text:
                    chapters.append(clean_text)

        return "\n\n".join(chapters)
    except Exception as e:
        logger.warning("EPUB extraction failed for %s: %s", path.name, e)
        return ""


def _extract_mobi(path: Path) -> str:
    """Extract text from MOBI/AZW3 files using mobi and BeautifulSoup."""
    try:
        import shutil
        import tempfile

        import mobi
        from bs4 import BeautifulSoup

        with tempfile.TemporaryDirectory():
            try:
                out_path, _ = mobi.extract(str(path))
            except Exception as e:
                logger.warning("mobi.extract internal failure for %s: %s", path.name, e)
                return ""

            if not out_path or not os.path.exists(out_path):
                return ""

            # If out_path is a directory, look for html files inside
            actual_file = out_path
            if os.path.isdir(out_path):
                html_files = list(Path(out_path).rglob("*.html")) + list(
                    Path(out_path).rglob("*.htm")
                )
                if not html_files:
                    return ""
                # Pick the largest html file as the main content
                actual_file = max(html_files, key=lambda f: f.stat().st_size)

            with open(actual_file, "r", encoding="utf-8", errors="ignore") as f:
                html_content = f.read()

            # Clean up the extracted files/dir
            to_clean = (
                out_path if os.path.isdir(out_path) else os.path.dirname(out_path)
            )
            if os.path.exists(to_clean):
                shutil.rmtree(to_clean, ignore_errors=True)

            soup = BeautifulSoup(html_content, "html.parser")
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
            text = soup.get_text(separator=" ")
            return " ".join(text.split())
    except Exception as e:
        logger.warning("MOBI extraction failed for %s: %s", path.name, e)
        return ""


def _extract_pdf(path: Path) -> str:
    """PDF extraction via Phase 9 pipeline (LlamaParse → PyMuPDF → pdfplumber + vision)."""
    from gateway.pdf_pipeline import extract_pdf_enhanced

    chunks = extract_pdf_enhanced(path)
    return "\n\n".join(chunk.combined_text() for chunk in chunks)


def _extract_csv(path: Path) -> str:
    """Extract CSV records, ensuring headers are preserved in each row-string for context."""
    import csv

    lines = []
    try:
        with open(path, mode="r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Format: "Key1: Value1 | Key2: Value2"
                row_str = " | ".join(
                    f"{k}: {v}" for k, v in row.items() if v and v.strip()
                )
                if row_str:
                    lines.append(row_str)
        return "\n".join(lines)
    except Exception as e:
        logger.warning("CSV extraction failed for %s: %s", path.name, e)
        return ""


def _extract_jsonl_session(path: Path) -> str:
    """Extract human-readable text from Claude Code .jsonl session transcripts."""
    lines = []
    try:
        for raw in path.read_text(errors="ignore").splitlines():
            if not raw.strip():
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            role = obj.get("role", "")
            # Claude Code transcript format: {role, content} or nested message
            msg = obj.get("message", obj)
            content = msg.get("content", "")
            if isinstance(content, list):
                # Multi-part content blocks
                parts = [
                    c.get("text", "")
                    for c in content
                    if isinstance(c, dict) and c.get("type") == "text"
                ]
                content = " ".join(parts)
            if role and content:
                lines.append(f"{role.upper()}: {content[:800]}")
    except Exception as e:
        logger.warning("JSONL parse failed for %s: %s", path.name, e)
    return "\n\n".join(lines)


def _extract_chatgpt_json(path: Path) -> str:
    """Extract text from OpenAI ChatGPT export JSON (list of conversations)."""
    try:
        data = json.loads(path.read_text(errors="ignore"))
    except Exception as e:
        logger.warning("ChatGPT JSON parse failed for %s: %s", path.name, e)
        return ""
    if not isinstance(data, list):
        return ""
    blocks = []
    for conv in data:
        title = conv.get("title", "Untitled")
        mapping = conv.get("mapping", {})
        messages = []
        for node in mapping.values():
            msg = node.get("message")
            if not msg:
                continue
            role = msg.get("author", {}).get("role", "")
            if role not in {"user", "assistant"}:
                continue
            content = msg.get("content", {})
            parts = content.get("parts", []) if isinstance(content, dict) else []
            text = " ".join(str(p) for p in parts if isinstance(p, str) and p.strip())
            if not text:
                continue
            create_time = msg.get("create_time") or 0
            messages.append((create_time, role.upper(), text[:600]))
        messages.sort(key=lambda x: x[0])
        if messages:
            lines = [f"CONVERSATION: {title}"]
            lines += [f"{role}: {text}" for _, role, text in messages]
            blocks.append("\n".join(lines))
    return "\n\n---\n\n".join(blocks)


def _extract_sqlite_journal(path: Path) -> str:
    """Extract role/content pairs from a SQLite journal table."""
    import sqlite3

    try:
        conn = sqlite3.connect(str(path))
        rows = conn.execute(
            "SELECT role, content FROM journal ORDER BY timestamp, id"
        ).fetchall()
        conn.close()
        lines = [
            f"{role.upper()}: {content[:600]}" for role, content in rows if content
        ]
        return "\n\n".join(lines)
    except Exception as e:
        logger.warning("SQLite journal extract failed for %s: %s", path.name, e)
        return ""
