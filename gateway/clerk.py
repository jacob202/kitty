"""Dumb extraction and preprocessing for Kitty's knowledge base."""
import base64
import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("kitty.knowledge.clerk")

from gateway.llm_client import call_llm

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


def _analyze_image_with_claude(base64_image: str, prompt: str) -> str:
    """Send an image to Claude 3.7 Sonnet for visual analysis."""
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ],
    }
    return call_llm(model="anthropic/claude-3.7-sonnet", **payload, timeout=60)


def _extract_visual_descriptions(path: Path) -> list[dict]:
    """Render PDF pages or process image files to get LLM technical descriptions."""
    visual_chunks = []
    suffix = path.suffix.lower()
    
    # Handle Image Files directly
    if suffix in [".jpg", ".jpeg", ".png"]:
        try:
            with open(path, "rb") as f:
                img_data = f.read()
            base64_img = base64.b64encode(img_data).decode("utf-8")
            
            prompt = """Analyze this technical photo or board layout. 
            1. **Identity**: What is this a photo of? (e.g., 'Bottom side of Sansui AU-7900 Main Board').
            2. **Visual Audit**: List all visible components, connectors, and labels. Note any signs of wear, heat, or previous repair.
            3. **Linkage**: Identify which circuit stage this likely belongs to based on the components visible.
            Keep the description technical and dense."""
            
            logger.info("Requesting Visual Analysis for image: %s", path.name)
            description = _analyze_image_with_claude(base64_img, prompt)
            if description:
                visual_chunks.append({
                    "text": f"IMAGE ANALYSIS: {description}",
                    "metadata": {"is_visual": True, "analysis_type": "physical_audit"}
                })
            return visual_chunks
        except Exception as e:
            logger.warning("Image analysis failed for %s: %s", path.name, e)
            return []

    # Handle PDF rendering
    if suffix != ".pdf":
        return []
        
    try:
        import fitz
        doc = fitz.open(str(path))
        
        # Intelligent page selection
        pages_to_check = set()
        for i in range(len(doc)):
            page_text = doc[i].get_text().lower()
            if any(k in page_text for k in ["schematic", "diagram", "circuit", "layout", "wiring", "troubleshooting", "voltage"]):
                pages_to_check.add(i)
                if len(pages_to_check) >= 12: break
        
        if not pages_to_check:
            pages_to_check.update(range(min(5, len(doc))))
            
        for page_num in sorted(list(pages_to_check))[:15]:
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("jpeg")
            base64_img = base64.b64encode(img_data).decode("utf-8")
            
            prompt = """Analyze this technical diagram or schematic. 
            
            1. **Circuit Identification**: What specific section of the device is this? (e.g., 'Main Amplifier Board', 'Power Supply Stage').
            2. **Power Flow**: Trace the primary power rails. Identify voltages, regulators, and rectification points. 
            3. **Signal Flow**: Trace the audio or data signal path from input to output. Identify key coupling caps, gain stages, or buffers.
            4. **Diagnostic Heuristics**: 
               - **Test Points (TP)**: List all test points and their expected voltages/waveforms.
               - **Troubleshooting Logic**: Extract any symptom-to-cause tables or diagnostic flowcharts.
               - **Service Notes**: Capture any production changes, mods, or caution boxes.
            5. **Exhaustive Component Reference**: List all critical components:
               - **Active**: ICs, Transistors, Diodes.
               - **Passive**: Resistors (values/watt), Capacitors (values/volt), Inductors.
               - **Electromechanical**: Relays, Switches, Connectors, Fuses.
               - **Adjustments**: Trimmer pots (VRs).
            
            Capture specific part numbers and values whenever legible. Keep it dense and highly searchable."""
            
            logger.info("Requesting Deep Schematic Analysis for %s [Page %d]", path.name, page_num + 1)
            description = _analyze_image_with_claude(base64_img, prompt)
            
            if description:
                visual_chunks.append({
                    "text": f"DEEP VISUAL ANALYSIS [Page {page_num + 1}]:\n{description}",
                    "metadata": {
                        "page_num": page_num + 1,
                        "is_visual": True,
                        "analysis_type": "schematic_trace"
                    }
                })
        doc.close()
    except Exception as e:
        logger.warning("Visual extraction failed for %s: %s", path.name, e)
        
    return visual_chunks


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
    elif suffix == ".csv":
        return _extract_csv(path)
    elif suffix == ".jsonl":
        return _extract_jsonl_session(path)
    elif suffix == ".json":
        try:
            first_char = path.read_text(errors="ignore").lstrip()[:1]
        except Exception:
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
            return ""


def _extract_epub(path: Path) -> str:
    """Extract text from EPUB files using ebooklib and BeautifulSoup."""
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
        
        # Suppress ebooklib warnings about non-standard EPUBs
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            book = epub.read_epub(str(path))
            
        chapters = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                # Remove script and style elements
                for script_or_style in soup(["script", "style"]):
                    script_or_style.decompose()
                text = soup.get_text(separator=' ')
                # Clean up whitespace
                clean_text = ' '.join(text.split())
                if clean_text:
                    chapters.append(clean_text)
                    
        return "\n\n".join(chapters)
    except Exception as e:
        logger.warning("EPUB extraction failed for %s: %s", path.name, e)
        return ""


def _extract_mobi(path: Path) -> str:
    """Extract text from MOBI/AZW3 files using mobi and BeautifulSoup."""
    try:
        import mobi
        import shutil
        import tempfile
        from bs4 import BeautifulSoup
        
        with tempfile.TemporaryDirectory() as temp_dir:
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
                html_files = list(Path(out_path).rglob("*.html")) + list(Path(out_path).rglob("*.htm"))
                if not html_files:
                    return ""
                # Pick the largest html file as the main content
                actual_file = max(html_files, key=lambda f: f.stat().st_size)
                
            with open(actual_file, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
            
            # Clean up the extracted files/dir
            to_clean = out_path if os.path.isdir(out_path) else os.path.dirname(out_path)
            if os.path.exists(to_clean):
                 shutil.rmtree(to_clean, ignore_errors=True)
            
            soup = BeautifulSoup(html_content, 'html.parser')
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
            text = soup.get_text(separator=' ')
            return ' '.join(text.split())
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
            headers = reader.fieldnames or []
            for row in reader:
                # Format: "Key1: Value1 | Key2: Value2"
                row_str = " | ".join(f"{k}: {v}" for k, v in row.items() if v and v.strip())
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
                parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
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
        lines = [f"{role.upper()}: {content[:600]}" for role, content in rows if content]
        return "\n\n".join(lines)
    except Exception as e:
        logger.warning("SQLite journal extract failed for %s: %s", path.name, e)
        return ""
