"""
LightRAG wrapper — delegates to LightRAGStore (Ollama backend, data/lightrag/).
Keeps the same public interface (search, ingest_pdf) for backward compat.
"""
import sys
from pathlib import Path

# Ensure src/ is on path so LightRAGStore can be imported
_root = Path(__file__).resolve().parent.parent
for _p in [str(_root), str(_root / "src"), str(_root / "scripts")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


class LightRAGWrapper:
    def __init__(self, working_dir=None):
        self._store = None
        try:
            from src.memory.lightrag_store import LightRAGStore
            self._store = LightRAGStore()
            print("[LightRAGWrapper] LightRAG initialized.")
        except Exception as e:
            print(f"[LightRAGWrapper] LightRAG not available ({e}), using fallback store.")
            self._fallback = []

    def ingest_pdf(self, pdf_path, manual_name=""):
        try:
            import pypdf
            reader = pypdf.PdfReader(pdf_path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            with open(pdf_path, "rb") as f:
                text = f.read().decode("utf-8", errors="ignore")
        if self._store:
            self._store.add_document(text, metadata={"source": manual_name})
        else:
            self._fallback.append({"name": manual_name, "text": text})
        return len(text)

    def search(self, query, top_k=5):
        if self._store:
            try:
                return self._store.search(query, top_k=top_k)
            except Exception as e:
                print(f"[LightRAGWrapper] Query failed: {e}")
        if hasattr(self, "_fallback"):
            results = []
            for doc in self._fallback:
                if query.lower() in doc["text"].lower():
                    idx = doc["text"].lower().find(query.lower())
                    results.append(doc["text"][max(0, idx - 100): idx + 300])
            return results[:top_k] if results else ["No results found."]
        return ["No results found."]
