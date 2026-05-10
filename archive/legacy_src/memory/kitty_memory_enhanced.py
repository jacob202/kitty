"""
Kitty Enhanced Memory System
Persistent, vector-based memory with fact extraction
Combines ChromaDB (vectors) + DuckDB (structured)
"""

import hashlib
import json
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings

    CHROMA_AVAILABLE = True
    from .chroma_manager import ChromaDBManager
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("ChromaDB not installed. Memory system disabled.")

try:
    from sentence_transformers import SentenceTransformer

    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence-transformers not installed. Embeddings disabled.")


@dataclass
class MemoryEntry:
    """Single memory entry"""

    id: str
    content: str
    source: str  # 'conversation', 'fact', 'document'
    timestamp: str
    metadata: dict[str, Any]


class KittyMemoryEnhanced:
    """
    Enhanced memory system for Kitty AI
    - Conversations: Full dialogue history
    - Facts: Extracted knowledge about user
    - Documents: Ingested files and notes
    """

    def __init__(
        self, persist_dir: str = "./data/chroma", embedding_model: str = "paraphrase-MiniLM-L3-v2"
    ):
        """
        Initialize enhanced memory

        Args:
            persist_dir: Where to store memory
            embedding_model: Sentence transformer model for embeddings
        """
        self.persist_dir = persist_dir
        self.embedding_model_name = embedding_model
        self.embedding_model = None
        self.embedding_backend = "uninitialized"
        self.embedding_dimension = 384
        self.client = None

        # Collections
        self.conversations = None
        self.facts = None
        self.documents = None

        self._initialize()

    def _initialize(self):
        """Initialize ChromaDB and embedding model"""
        if not CHROMA_AVAILABLE:
            logger.error("ChromaDB not available")
            return

        try:
            # Initialize ChromaDB using shared manager
            settings = Settings(anonymized_telemetry_enabled=False)
            self.client = ChromaDBManager.get_client(self.persist_dir, settings)

            # Get or create collections
            self.conversations = ChromaDBManager.get_collection(
                self.persist_dir, "conversations", settings
            )
            self.facts = ChromaDBManager.get_collection(
                self.persist_dir, "user_facts", settings
            )
            self.documents = ChromaDBManager.get_collection(
                self.persist_dir, "documents", settings
            )

            # Initialize embedding model. Prefer cached local models; fall back to
            # deterministic embeddings so local-first memory still works offline.
            if EMBEDDINGS_AVAILABLE:
                try:
                    logger.info("Loading embedding model: %s", self.embedding_model_name)
                    self.embedding_model = SentenceTransformer(
                        self.embedding_model_name, local_files_only=True
                    )
                    self.embedding_dimension = int(self._embedding_model_dimension())
                    self.embedding_backend = self.embedding_model_name
                    logger.info("Memory system initialized (%s)", self.embedding_model_name)
                except TypeError:
                    try:
                        self.embedding_model = SentenceTransformer(self.embedding_model_name)
                        self.embedding_dimension = int(self._embedding_model_dimension())
                        self.embedding_backend = self.embedding_model_name
                        logger.info("Memory system initialized (%s)", self.embedding_model_name)
                    except Exception as e:
                        logger.warning("Embedding model unavailable offline: %s", e)
                        self.embedding_backend = "deterministic-hash"
                except Exception as e:
                    logger.warning("Embedding model unavailable offline: %s", e)
                    self.embedding_backend = "deterministic-hash"
            else:
                logger.warning("Embeddings not available")
                self.embedding_backend = "deterministic-hash"

        except Exception as e:
            logger.exception("Memory initialization error: %s", e)
            self.client = None

    def add_conversation(
        self, user_message: str, kitty_response: str, metadata: dict = None, domain: str = "general"
    ) -> str:
        """
        Store a conversation turn

        Args:
            user_message: What user said
            kitty_response: What Kitty replied
            metadata: Additional context
            domain: Specialist domain for memory isolation (e.g., 'automotive', 'fitness')

        Returns:
            Memory ID
        """
        if not self._is_ready():
            return None

        # Create entry
        text = f"User: {user_message}\nKitty: {kitty_response}"
        entry_id = hashlib.md5(f"{text}{datetime.now()}".encode()).hexdigest()
        timestamp = datetime.now().isoformat()

        # Get embedding
        embedding = self._get_embedding(text)
        if embedding is None:
            return None

        # Store
        meta = {
            "timestamp": timestamp,
            "user_message": user_message,
            "kitty_response": kitty_response,
            "domain": domain,
            **(metadata or {}),
        }

        self.conversations.add(
            documents=[text], embeddings=[embedding], ids=[entry_id], metadatas=[meta]
        )

        return entry_id

    def add_user_fact(self, fact: str, category: str = "general", domain: str = "general") -> str:
        """
        Store a fact about the user

        Args:
            fact: The fact to store (e.g., "User likes sci-fi movies")
            category: Type of fact (likes, work, family, etc.)
            domain: Specialist domain for memory isolation

        Returns:
            Memory ID
        """
        if not self._is_ready():
            return None

        entry_id = hashlib.md5(fact.encode()).hexdigest()
        timestamp = datetime.now().isoformat()

        embedding = self._get_embedding(fact)
        if embedding is None:
            return None

        self.facts.add(
            documents=[fact],
            embeddings=[embedding],
            ids=[entry_id],
            metadatas=[{"timestamp": timestamp, "category": category, "fact": fact, "domain": domain}],
        )

        return entry_id

    def ingest_document(
        self, file_path: str, chunk_size: int = 500, chunk_overlap: int = 50
    ) -> list[str]:
        """
        Ingest a document into memory

        Args:
            file_path: Path to document
            chunk_size: Size of each chunk
            chunk_overlap: Overlap between chunks

        Returns:
            List of chunk IDs
        """
        if not self._is_ready():
            return []

        if not os.path.exists(file_path):
            logger.error("File not found: %s", file_path)
            return []

        try:
            text = self._read_document_text(file_path)
            if not text.strip():
                logger.error("No readable text found in %s", file_path)
                return []

            # Simple chunking (can be improved with better splitter)
            chunks = self._chunk_text(text, chunk_size, chunk_overlap)

            ids = []
            batch_size = 64
            for batch_start in range(0, len(chunks), batch_size):
                batch_chunks = chunks[batch_start : batch_start + batch_size]
                batch_embeddings = self._get_embeddings(batch_chunks)
                batch_ids = []
                batch_metadata = []

                for offset, chunk in enumerate(batch_chunks):
                    i = batch_start + offset
                    chunk_id = hashlib.md5(f"{file_path}{chunk}{i}".encode()).hexdigest()
                    batch_ids.append(chunk_id)
                    batch_metadata.append(
                        {
                            "source": os.path.basename(file_path),
                            "source_path": str(file_path),
                            "domain": os.path.basename(os.path.dirname(file_path)),
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "timestamp": datetime.now().isoformat(),
                            "embedding_backend": self.embedding_backend,
                        }
                    )

                self.documents.upsert(
                    documents=batch_chunks,
                    embeddings=batch_embeddings,
                    ids=batch_ids,
                    metadatas=batch_metadata,
                )
                ids.extend(batch_ids)

            logger.info("Ingested %s chunks from %s", len(chunks), file_path)
            return ids

        except Exception as e:
            logger.exception("Document ingestion error: %s", e)
            return []

    def has_document_source(self, file_path: str) -> bool:
        """Return True if chunks for this exact source path are already stored."""
        if not self._is_ready() or self.documents is None:
            return False
        try:
            result = self.documents.get(where={"source_path": str(file_path)}, limit=1)
            return bool(result and result.get("ids"))
        except Exception:
            return False

    def retrieve_context(
        self, query: str, n_conversations: int = 3, n_facts: int = 3, n_documents: int = 2,
        domain: str | None = None,
    ) -> dict[str, list[str]]:
        """
        Retrieve relevant context for a query

        Args:
            query: The query to find context for
            n_conversations: Number of conversation turns to retrieve
            n_facts: Number of facts to retrieve
            n_documents: Number of document chunks to retrieve
            domain: Filter memories by domain. If None, retrieves from all domains.
                    If set, retrieves only memories matching this domain or 'general'.

        Returns:
            Dict with 'conversations', 'facts', 'documents' lists
        """
        if not self._is_ready():
            return {"conversations": [], "facts": [], "documents": []}

        query_embedding = self._get_embedding(query)
        if query_embedding is None:
            return {"conversations": [], "facts": [], "documents": []}

        results = {"conversations": [], "facts": [], "documents": []}

        # Build domain filter: match the specified domain OR 'general'
        # ChromaDB uses $or for this pattern
        where_filter = None
        if domain:
            where_filter = {"$or": [{"domain": domain}, {"domain": "general"}]}

        try:
            # Search conversations
            if self.conversations.count() > 0:
                conv_kwargs = {"query_embeddings": [query_embedding], "n_results": n_conversations}
                if where_filter:
                    conv_kwargs["where"] = where_filter
                conv_results = self.conversations.query(**conv_kwargs)
                if conv_results["documents"][0]:
                    results["conversations"] = conv_results["documents"][0]

            # Search facts
            if self.facts.count() > 0:
                fact_kwargs = {"query_embeddings": [query_embedding], "n_results": n_facts}
                if where_filter:
                    fact_kwargs["where"] = where_filter
                fact_results = self.facts.query(**fact_kwargs)
                if fact_results["documents"][0]:
                    results["facts"] = fact_results["documents"][0]

            # Search documents (already has domain in metadata from ingest)
            if self.documents.count() > 0:
                doc_kwargs = {"query_embeddings": [query_embedding], "n_results": n_documents}
                if where_filter:
                    doc_kwargs["where"] = where_filter
                doc_results = self.documents.query(**doc_kwargs)
                if doc_results["documents"][0]:
                    results["documents"] = doc_results["documents"][0]

        except Exception as e:
            logger.exception("Retrieval error: %s", e)

        return results

    def format_context_for_prompt(self, query: str, domain: str | None = None) -> str:
        """
        Retrieve and format context for inclusion in LLM prompt

        Args:
            query: Current user query
            domain: Filter memories by domain for isolation

        Returns:
            Formatted context string
        """
        context = self.retrieve_context(query, domain=domain)

        sections = []

        if context["facts"]:
            sections.append(
                "### Facts About You:\n" + "\n".join(f"- {f}" for f in context["facts"])
            )

        if context["conversations"]:
            sections.append("### Recent Conversations:\n" + "\n".join(context["conversations"]))

        if context["documents"]:
            sections.append("### Relevant Information:\n" + "\n".join(context["documents"]))

        return "\n\n".join(sections) if sections else ""

    def get_stats(self) -> dict:
        """Get memory statistics"""
        if not self._is_ready():
            return {"error": "Memory not initialized"}

        return {
            "conversations": self.conversations.count() if self.conversations else 0,
            "facts": self.facts.count() if self.facts else 0,
            "documents": self.documents.count() if self.documents else 0,
            "embedding_model": self.embedding_model_name,
            "embedding_backend": self.embedding_backend,
            "embedding_dimension": self.embedding_dimension,
            "persist_dir": self.persist_dir,
        }

    def is_available(self) -> bool:
        """Return True when ChromaDB and an embedding backend are usable."""
        return self._is_ready()

    def _is_ready(self) -> bool:
        """Check if memory system is ready"""
        return (
            self.client is not None
            and self.embedding_backend != "uninitialized"
            and self.conversations is not None
        )

    def _get_embedding(self, text: str) -> list[float] | None:
        """Get embedding for text"""
        try:
            if self.embedding_model is not None:
                return self.embedding_model.encode(text).tolist()
            return self._fallback_embedding(text)
        except Exception as e:
            logger.exception("Embedding error: %s", e)
            return self._fallback_embedding(text)

    def _embedding_model_dimension(self) -> int:
        if hasattr(self.embedding_model, "get_embedding_dimension"):
            return self.embedding_model.get_embedding_dimension()
        return self.embedding_model.get_sentence_embedding_dimension()

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for a batch of texts."""
        try:
            if self.embedding_model is not None:
                return self.embedding_model.encode(texts).tolist()
        except Exception as e:
            logger.exception("Batch embedding error: %s", e)
        return [self._fallback_embedding(text) for text in texts]

    def _fallback_embedding(self, text: str) -> list[float]:
        """Deterministic local embedding used when sentence-transformers is offline."""
        vector = [0.0] * self.embedding_dimension
        tokens = text.lower().split()
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for offset in range(0, min(len(digest), 16), 2):
                index = int.from_bytes(digest[offset : offset + 2], "big") % self.embedding_dimension
                sign = 1.0 if digest[offset] % 2 == 0 else -1.0
                vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def _read_document_text(self, file_path: str) -> str:
        """Read text from supported KB document formats."""
        suffix = os.path.splitext(file_path)[1].lower()
        if suffix == ".pdf":
            try:
                import fitz

                doc = fitz.open(file_path)
                try:
                    return "\n".join(page.get_text() for page in doc)
                finally:
                    doc.close()
            except Exception as e:
                logger.exception("PDF extraction error for %s: %s", file_path, e)
                return ""

        if suffix == ".json":
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                return json.dumps(data, ensure_ascii=False, indent=2)
            except Exception as e:
                logging.getLogger(__name__).warning(f"Error: {e}")

        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        """Simple text chunking"""
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Try to break at sentence or paragraph
            if end < len(text):
                # Look for sentence break
                for breaker in [".\n", "\n\n", ". ", " "]:
                    last_break = chunk.rfind(breaker)
                    if last_break > chunk_size * 0.5:  # At least half the chunk
                        end = start + last_break + len(breaker)
                        chunk = text[start:end]
                        break

            chunks.append(chunk.strip())
            next_start = end - overlap
            if next_start <= start:
                next_start = end
            start = next_start

        return [chunk for chunk in chunks if chunk]


# Quick test
if __name__ == "__main__":
    print("🧠 Testing Kitty Memory\n")

    memory = KittyMemoryEnhanced()

    if not memory._is_ready():
        print("❌ Memory system not available")
        print("Install: pip install chromadb sentence-transformers")
        exit(1)

    # Add test data
    print("Adding test conversations...")
    memory.add_conversation("Hello Kitty!", "Hello! Nice to meet you!")
    memory.add_conversation("I like sci-fi movies", "That's cool! Any favorites?")

    print("Adding test facts...")
    memory.add_user_fact("User likes sci-fi movies", "likes")
    memory.add_user_fact("User works as an electrician", "work")

    # Test retrieval
    print("\n🔍 Testing retrieval...")
    query = "What do I like?"
    context = memory.format_context_for_prompt(query)

    print(f"\nQuery: {query}")
    print(f"Context found:\n{context}\n")

    # Stats
    stats = memory.get_stats()
    print("Memory stats:", stats)
