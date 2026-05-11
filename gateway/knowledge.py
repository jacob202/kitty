"""ChromaDB knowledge base for Kitty Gateway."""
from __future__ import annotations
import base64
import hashlib
import io
import json
import logging
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger("kitty.knowledge")

from gateway.paths import DATA_DIR
from gateway.llm_client import call_llm

KNOWLEDGE_DB_PATH = DATA_DIR / "knowledge_db"
COLLECTION_NAME = "kitty_knowledge"
EMBED_MODEL = "nomic-embed-text"
OLLAMA_BASE = "http://localhost:11434"

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


@lru_cache(maxsize=1)
def _get_collection():
    """Lazy-init ChromaDB collection."""
    import chromadb
    KNOWLEDGE_DB_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(KNOWLEDGE_DB_PATH))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed texts using nomic-embed-text via Ollama — batched to prevent timeouts."""
    import requests
    
    batch_size = 50
    all_embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            resp = requests.post(
                f"{OLLAMA_BASE}/api/embed",
                json={"model": EMBED_MODEL, "input": batch},
                timeout=120,
            )
            resp.raise_for_status()
            all_embeddings.extend(resp.json()["embeddings"])
        except Exception as e:
            logger.error("Embedding batch failed at index %d: %s", i, e)
            raise
            
    return all_embeddings


@lru_cache(maxsize=256)
def _embed_cached(text: str) -> tuple[float, ...]:
    """Cache embeddings for individual query strings."""
    result = _embed([text])[0]
    return tuple(result)


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


def delete_source_chunks(source_name: str) -> bool:
    """Delete all chunks belonging to a specific source from ChromaDB."""
    try:
        collection = _get_collection()
        collection.delete(where={"source": source_name})
        logger.info("Deleted existing chunks for source: %s", source_name)
        return True
    except Exception as e:
        logger.error("Failed to delete source %s: %s", source_name, e)
        return False


def is_high_quality(text: str) -> bool:
    """Heuristic check for chunk quality. Rejects junk/OCR noise."""
    if len(text) < 50:
        return False # Too short to be useful context
    
    # Check for excessive non-alphanumeric characters (typical of OCR garble)
    alnum_count = sum(c.isalnum() for c in text)
    if alnum_count / len(text) < 0.6:
        return False
        
    # Check for repetitive patterns (like navigation menus or page numbers)
    if text.count("\n") > (len(text) / 20):
        return False # Too many short lines
        
    return True


def generate_source_summary(source_name: str, text_preview: str, doc_type: str) -> dict:
    """
    Path: Taste (Knowledge Curation)
    Assess the quality, recency, and authority of a document before ingestion.
    """
    prompt = f"""Analyze this source preview for a high-leverage personal knowledge base.
    
    SOURCE NAME: {source_name}
    TYPE: {doc_type}
    CONTENT PREVIEW:
    {text_preview[:4000]}
    
    TASK 1: SUMMARY
    Write a 2-3 sentence 'Source Brief' explaining what this is and its primary purpose.
    
    TASK 2: TASTE CHECK (Knowledge Quality & Safety)
    Assess the content against modern engineering and safety standards:
    1. AUTHORITY: Is this a gold-standard reference (e.g. factory service manual, academic textbook), or secondary/informal? (Score 1-5)
    2. RECENCY: Is the knowledge likely outdated or superseded?
    3. SAFETY CRITICAL: Does this document contain high-voltage warnings, hazardous material handling, or safety-critical procedures?
    4. POLLUTION RISK: Does this contain outdated theories that could lead to incorrect or dangerous repair actions today?
    
    Respond in JSON format:
    {{
      "summary": "...",
      "authority_score": 1-5,
      "relevance_period": "...",
      "safety_level": "high/medium/low",
      "pollution_warning": "...",
      "needs_vision": true/false,
      "primary_topic": "..."
    }}
    """

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "max_tokens": 800,
        "temperature": 0.1,
    }
    
    response_text = call_llm(model="anthropic/claude-3.7-sonnet", **payload, timeout=45)
    
    default_data = {
        "summary": f"A {doc_type} titled {source_name}.",
        "authority_score": 3,
        "relevance_period": "unknown",
        "pollution_warning": None,
        "needs_vision": (doc_type in ("service_manual", "textbook")),
        "primary_topic": "general"
    }

    if not response_text:
        return default_data

    try:
        data = json.loads(response_text)
        # Ensure all keys exist
        return {**default_data, **data}
    except Exception:
        return default_data


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


def ingest_file(
    file_path: str | Path,
    sensitivity: str = "low",
    source_label: Optional[str] = None,
    doc_type: Optional[str] = None,
    force_refresh: bool = False,
) -> int:
    """Ingest a file into ChromaDB with intelligent judgment and rich metadata."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Initial text extraction for summary
    raw_text = _extract_text(path)
    source = source_label or path.name
    
    # 1. Deduplication Check
    content_hash = _get_content_hash(raw_text) if raw_text else _get_content_hash(str(path))
    collection = _get_collection()
    existing_hash = collection.get(where={"content_hash": content_hash})
    if existing_hash["ids"] and not force_refresh:
        logger.info("Content from %s already ingested (hash match), skipping", source)
        return 0

    # 2. Update Check
    existing_source = collection.get(where={"source": source})
    if existing_source["ids"]:
        logger.info("New content detected for %s, pruning old chunks...", source)
        delete_source_chunks(source)

    # 3. Source Summary & Vision Judgment (Path: Taste)
    resolved_type = doc_type or detect_doc_type(path, raw_text[:1000] if raw_text else "")
    taste_data = generate_source_summary(source, raw_text[:4000], resolved_type)
    
    source_brief = taste_data.get("summary", "")
    needs_vision = taste_data.get("needs_vision", False)
    
    profile = _CHUNK_PROFILES.get(resolved_type, _CHUNK_PROFILES["general"])
    chunks = []
    chunk_metadatas = []
    
    # --- SOURCE BRIEF ---
    chunks.append(f"SOURCE BRIEF: {source_brief}")
    chunk_metadatas.append({
        "chunk_index": -1, 
        "is_visual": False, 
        "doc_type": "source_summary",
        "authority_score": taste_data.get("authority_score"),
        "relevance_period": taste_data.get("relevance_period"),
        "primary_topic": taste_data.get("primary_topic"),
        "pollution_warning": taste_data.get("pollution_warning")
    })

    # 4. Content Extraction with Page Tagging
    if path.suffix.lower() == ".pdf":
        pages = _extract_pdf_pages(path)
        for page_num, page_text in pages:
            clean_text = preprocess_text(page_text)
            if not clean_text: continue
            
            page_chunks = _chunk_text(clean_text, profile["size"], profile["overlap"])
            for i, chunk in enumerate(page_chunks):
                if is_high_quality(chunk):
                    chunks.append(chunk)
                    chunk_metadatas.append({
                        "chunk_index": len(chunks),
                        "is_visual": False,
                        "page_num": page_num
                    })
    else:
        # Non-PDF files (Markdown, Text, CSV)
        clean_text = preprocess_text(raw_text)
        if clean_text:
            text_chunks = _chunk_text(clean_text, profile["size"], profile["overlap"])
            for i, chunk in enumerate(text_chunks):
                if is_high_quality(chunk):
                    chunks.append(chunk)
                    chunk_metadatas.append({
                        "chunk_index": i,
                        "is_visual": False
                    })
            
    # 5. Visual Chunks (Conditional based on judgment)
    if needs_vision or resolved_type == "service_manual":
        logger.info("Intelligent Vision triggered for %s (judgment: %s)", source, needs_vision)
        visual_info = _extract_visual_descriptions(path)
        for info in visual_info:
            chunks.append(info["text"])
            chunk_metadatas.append({
                **info["metadata"],
                "chunk_index": len(chunks) + 1000,
                "is_visual": True
            })

    if not chunks:
        logger.warning("No high-quality content found to ingest from %s", path)
        return 0

    # 6. Storage
    embeddings = _embed(chunks)
    ids = [f"{source}__chunk_{i}_{int(time.time())}" for i in range(len(chunks))]
    
    try:
        stat = path.stat()
        mtime = int(stat.st_mtime)
        ctime = int(stat.st_ctime)
    except Exception:
        mtime = ctime = int(time.time())

    def _safe_meta(val):
        """Ensure metadata value is a ChromaDB-compatible primitive."""
        if val is None: return ""
        if isinstance(val, (str, int, float, bool)): return val
        return str(val)

    final_metadatas = []
    for i, meta in enumerate(chunk_metadatas):
        m = {
            "source": _safe_meta(source),
            "file_path": _safe_meta(str(path)),
            "sensitivity": _safe_meta(sensitivity),
            "doc_type": _safe_meta(resolved_type if "doc_type" not in meta else meta["doc_type"]),
            "content_hash": _safe_meta(content_hash),
            "modified_at": mtime,
            "created_at": ctime,
            "ingested_at": int(time.time()),
            "authority_score": _safe_meta(taste_data.get("authority_score")),
            "relevance_period": _safe_meta(taste_data.get("relevance_period")),
            "primary_topic": _safe_meta(taste_data.get("primary_topic")),
        }
        # Merge remaining meta from chunking logic
        for k, v in meta.items():
            if k not in m:
                m[k] = _safe_meta(v)
        final_metadatas.append(m)
        
    collection.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=final_metadatas)
    logger.info("Ingested %d high-quality chunks from %s (type=%s, vision=%s)", 
                len(chunks), source, resolved_type, any(m.get("is_visual") for m in chunk_metadatas))
    return len(chunks)


def search_knowledge(
    query: str, 
    limit: int = 5, 
    sensitivity_filter: Optional[str] = None,
    sort_by: str = "relevance",  # "relevance" or "recency"
    stitch_context: bool = True
) -> list[dict]:
    """Search ChromaDB for chunks relevant to query, with optional context stitching."""
    try:
        collection = _get_collection()
        query_embedding = list(_embed_cached(query))
        where = {"sensitivity": sensitivity_filter} if sensitivity_filter else None
        
        # Get enough results to allow for filtering/sorting
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit * 3, max(1, collection.count())),
            where=where
        )
        
        chunks = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            dist = results["distances"][0][i] if results["distances"] else 1.0
            
            chunk_data = {
                "text": doc,
                "source": meta.get("source", "unknown"),
                "doc_type": meta.get("doc_type", "general"),
                "score": 1.0 - dist,
                "ingested_at": meta.get("ingested_at", 0),
                "index": meta.get("chunk_index", 0),
                "metadata": meta,
            }
            
            # --- CONTEXT STITCHER ---
            if stitch_context and "chunk_index" in meta and meta.get("doc_type") not in ("source_summary", "visual_description"):
                source = meta["source"]
                idx = meta["chunk_index"]
                
                # Fetch neighboring chunks (+/- 1)
                neighbor_results = collection.get(
                    where={"$and": [{"source": source}, {"chunk_index": {"$in": [idx-1, idx+1]}}]}
                )
                
                if neighbor_results["ids"]:
                    # Create a map of index -> text
                    neighbors = {}
                    for n_idx, n_meta in enumerate(neighbor_results["metadatas"]):
                        neighbors[n_meta["chunk_index"]] = neighbor_results["documents"][n_idx]
                    
                    stitched_parts = []
                    if idx - 1 in neighbors: stitched_parts.append(neighbors[idx-1])
                    stitched_parts.append(doc)
                    if idx + 1 in neighbors: stitched_parts.append(neighbors[idx+1])
                    
                    chunk_data["text"] = "\n[...]\n".join(stitched_parts)
                    chunk_data["stitched"] = True

            chunks.append(chunk_data)
        
        if sort_by == "recency":
            chunks.sort(key=lambda x: x["ingested_at"], reverse=True)
        else:
            chunks.sort(key=lambda x: x["score"], reverse=True)
            
        return chunks[:limit]
    except Exception as e:
        logger.warning("Knowledge search failed: %s", e)
        return []


def get_knowledge_block(query: str, limit: int = 5) -> str:
    """Return a formatted context block to inject into the system prompt."""
    chunks = search_knowledge(query, limit=limit)
    if not chunks:
        return ""
    lines = ["## Relevant knowledge from Kitty's knowledge base:"]
    for chunk in chunks:
        source = chunk["source"]
        doc_type = chunk.get("doc_type", "general")
        label = f"[Source: {source}" + (f" | type: {doc_type}]" if doc_type != "general" else "]")
        lines.append(f"\n{label}")
        lines.append(chunk["text"][:400])
    return "\n".join(lines)


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


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Robust text chunking strategy.
    
    Tries to split by paragraphs first, then falls back to word count.
    Ensures structural integrity where possible.
    """
    if not text:
        return []

    # Try splitting by paragraph double-newlines
    paragraphs = re.split(r"\n\n+", text)
    
    final_chunks = []
    current_chunk_words = []
    
    for para in paragraphs:
        para_words = para.split()
        if not para_words:
            continue
            
        # If adding this paragraph exceeds chunk size, and we already have words, emit current chunk
        if len(current_chunk_words) + len(para_words) > chunk_size and current_chunk_words:
            final_chunks.append(" ".join(current_chunk_words))
            # Keep overlap words from the end
            current_chunk_words = current_chunk_words[-overlap:] if overlap < len(current_chunk_words) else current_chunk_words
            
        # If the paragraph itself is larger than chunk size, split it by words
        if len(para_words) > chunk_size:
            # First, add what we have
            if current_chunk_words:
                final_chunks.append(" ".join(current_chunk_words))
                current_chunk_words = []
                
            # Then split the giant paragraph
            i = 0
            while i < len(para_words):
                chunk_slice = para_words[i : i + chunk_size]
                final_chunks.append(" ".join(chunk_slice))
                i += chunk_size - overlap
        else:
            current_chunk_words.extend(para_words)
            
    if current_chunk_words:
        final_chunks.append(" ".join(current_chunk_words))
        
    return [c for c in final_chunks if c.strip()]
