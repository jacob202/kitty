"""
Search Index Management for Deep Search Results

Provides vector database storage and retrieval for deep search/crawl results.
Uses ChromaDB for vector storage with deduplication and metadata tracking.

Usage:
    index = SearchIndex()
    index.store_search_result(query, crawled_pages)
    results = index.semantic_search("specific question", top_k=5)
"""

import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Global index instance
_search_index: Optional["SearchIndex"] = None


def get_search_index() -> "SearchIndex":
    """Get or create the global SearchIndex instance."""
    global _search_index
    if _search_index is None:
        _search_index = SearchIndex()
    return _search_index


class SearchIndex:
    """
    Vector database index for storing and retrieving deep search results.

    Features:
    - ChromaDB-backed vector storage
    - Content deduplication using MD5 hashing
    - Metadata tracking (URL, depth, query, timestamp)
    - Semantic search with filters
    - Chunking for large documents
    """

    def __init__(
        self,
        persist_dir: str = "./data/search_index",
        collection_name: str = "deep_search_results",
        chunk_size: int = 1000,
        embedding_model: str = "nomic-embed-text",
    ):
        """
        Initialize the search index.

        Args:
            persist_dir: Directory for ChromaDB persistence
            collection_name: Name of the ChromaDB collection
            chunk_size: Character size for document chunking
            embedding_model: Ollama embedding model to use
        """
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.chunk_size = chunk_size
        self.embedding_model = embedding_model
        self._collection = None
        self._initialized = False

    def _initialize(self):
        """Lazy initialization of ChromaDB collection."""
        if self._initialized:
            return

        try:
            from chromadb.config import Settings
            from src.memory.chroma_manager import ChromaDBManager

            settings = Settings(allow_reset=True, anonymized_telemetry=False)
            self._collection = ChromaDBManager.get_collection(
                str(self.persist_dir), self.collection_name, settings
            )

            self._initialized = True
            logger.info(f"Search index initialized at {self.persist_dir}")

        except ImportError:
            logger.error("ChromaDB not installed. Run: pip install chromadb")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize search index: {e}")
            raise

    def _compute_content_hash(self, content: str) -> str:
        """Compute MD5 hash for content deduplication."""
        return hashlib.md5(content.encode()).hexdigest()

    def _get_embedding(self, text: str) -> list[float]:
        """Generate embedding using Ollama."""
        try:
            import httpx

            response = httpx.post(
                "http://localhost:11434/api/embeddings",
                json={"model": self.embedding_model, "prompt": text[:8000]},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            logger.warning(f"Embedding failed: {e}, using fallback")
            return self._fallback_embedding(text)

    def _fallback_embedding(self, text: str) -> list[float]:
        """Generate simple hash-based embedding as fallback."""
        import numpy as np

        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        np.random.seed(hash_val)
        dim = 768  # Standard embedding dimension
        return np.random.randn(dim).tolist()

    def _chunk_text(self, text: str) -> list[dict[str, Any]]:
        """Split text into overlapping chunks for better retrieval."""
        if len(text) <= self.chunk_size:
            return [{"text": text, "chunk_index": 0, "total_chunks": 1}]

        chunks = []
        overlap = self.chunk_size // 4  # 25% overlap
        start = 0
        index = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]

            chunks.append(
                {
                    "text": chunk_text,
                    "chunk_index": index,
                    "total_chunks": -1,  # Will be updated
                    "start_char": start,
                    "end_char": end,
                }
            )

            start += self.chunk_size - overlap
            index += 1

        # Update total_chunks
        for chunk in chunks:
            chunk["total_chunks"] = len(chunks)

        return chunks

    def store_search_result(
        self,
        query: str,
        pages: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Store deep search results in the vector index.

        Args:
            query: The original search query
            pages: List of crawled page dicts with 'url', 'title', 'content', 'summary'
            metadata: Optional additional metadata

        Returns:
            Dict with storage statistics
        """
        self._initialize()

        stats = {
            "stored": 0,
            "duplicates": 0,
            "errors": 0,
            "query": query,
            "timestamp": datetime.now().isoformat(),
        }

        for page in pages:
            try:
                url = page.get("url", "")
                title = page.get("title", "")
                content = page.get("content", page.get("body", ""))
                summary = page.get("summary", "")
                depth = page.get("depth", page.get("crawled_depth", 0))

                # Skip empty content
                if not content and not summary:
                    continue

                # Compute content hash for deduplication
                content_hash = self._compute_content_hash(url + content[:1000])

                # Check for duplicate
                existing = self._collection.get(where={"content_hash": content_hash}, limit=1)
                if existing and existing["ids"]:
                    stats["duplicates"] += 1
                    logger.debug(f"Duplicate detected for {url}")
                    continue

                # Prepare document text
                doc_text = f"Title: {title}\nURL: {url}\n\n"
                if summary:
                    doc_text += f"Summary: {summary}\n\n"
                doc_text += f"Content: {content[:5000]}"

                # Chunk the document
                chunks = self._chunk_text(doc_text)

                # Store each chunk
                for chunk in chunks:
                    chunk_id = f"{content_hash}_chunk_{chunk['chunk_index']}"

                    metadata = {
                        "url": url,
                        "title": title,
                        "query": query,
                        "depth": depth,
                        "timestamp": time.time(),
                        "content_hash": content_hash,
                        "chunk_index": chunk["chunk_index"],
                        "total_chunks": chunk["total_chunks"],
                        "source": "deep_search",
                    }

                    if metadata_extra := metadata:
                        metadata.update(metadata_extra)

                    # Get embedding
                    embedding = self._get_embedding(chunk["text"])

                    # Store in ChromaDB
                    self._collection.upsert(
                        ids=[chunk_id],
                        embeddings=[embedding],
                        documents=[chunk["text"]],
                        metadatas=[metadata],
                    )

                    stats["stored"] += 1

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Failed to store page {page.get('url', 'unknown')}: {e}")

        logger.info(
            f"Stored {stats['stored']} chunks ({stats['duplicates']} duplicates, {stats['errors']} errors)"
        )
        return stats

    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for relevant documents using semantic similarity.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_metadata: Optional metadata filters

        Returns:
            List of matching documents with metadata
        """
        self._initialize()

        try:
            # Get query embedding
            query_embedding = self._get_embedding(query)

            # Build where clause for filtering
            where = None
            if filter_metadata:
                where = {k: v for k, v in filter_metadata.items() if v is not None}

            # Search
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["metadatas", "documents", "distances"],
                where=where,
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
                            "score": 1 - results["distances"][0][i] if results["distances"] else 0,
                        }
                    )

            return formatted

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_by_url(self, url: str) -> list[dict[str, Any]]:
        """Get all stored content for a specific URL."""
        self._initialize()

        try:
            results = self._collection.get(
                where={"url": url},
                include=["metadatas", "documents"],
            )

            formatted = []
            if results and results["ids"]:
                for i in range(len(results["ids"])):
                    formatted.append(
                        {
                            "id": results["ids"][i],
                            "content": results["documents"][i] if results["documents"] else "",
                            "metadata": results["metadatas"][i] if results["metadatas"] else {},
                        }
                    )

            # Sort by chunk index
            formatted.sort(key=lambda x: x["metadata"].get("chunk_index", 0))
            return formatted

        except Exception as e:
            logger.error(f"Failed to get by URL: {e}")
            return []

    def get_stats(self) -> dict[str, Any]:
        """Get collection statistics."""
        self._initialize()

        try:
            count = self._collection.count()
            return {
                "document_count": count,
                "collection": self.collection_name,
                "persist_dir": str(self.persist_dir),
            }
        except Exception as e:
            return {"error": str(e)}

    def clear(self) -> bool:
        """Clear all stored documents."""
        self._initialize()

        try:
            self._collection.delete(where={})
            logger.info("Search index cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear index: {e}")
            return False

    def delete_old_results(self, days: int = 7) -> int:
        """
        Delete search results older than specified days.

        Args:
            days: Delete results older than this many days

        Returns:
            Number of deleted documents
        """
        self._initialize()

        try:
            cutoff_time = time.time() - (days * 24 * 60 * 60)

            # Get all documents
            all_docs = self._collection.get(include=["metadatas"])

            if not all_docs or not all_docs["ids"]:
                return 0

            # Find old ones
            to_delete = []
            for i, metadata in enumerate(all_docs.get("metadatas", [])):
                if metadata and metadata.get("timestamp", 0) < cutoff_time:
                    to_delete.append(all_docs["ids"][i])

            # Delete
            if to_delete:
                self._collection.delete(ids=to_delete)
                logger.info(f"Deleted {len(to_delete)} old search results")

            return len(to_delete)

        except Exception as e:
            logger.error(f"Failed to delete old results: {e}")
            return 0


def store_deep_search_results(
    query: str,
    pages: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Convenience function to store deep search results.

    Args:
        query: Original search query
        pages: List of crawled pages
        metadata: Optional metadata

    Returns:
        Storage statistics
    """
    index = get_search_index()
    return index.store_search_result(query, pages, metadata)


def search_crawled_content(
    query: str,
    top_k: int = 5,
    days_limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Search previously stored crawl results.

    Args:
        query: Search query
        top_k: Number of results
        days_limit: Only search results from last N days

    Returns:
        List of matching documents
    """
    index = get_search_index()

    filters = None
    if days_limit:
        cutoff = time.time() - (days_limit * 24 * 60 * 60)
        filters = {"timestamp": {"$gte": cutoff}}

    return index.semantic_search(query, top_k=top_k, filter_metadata=filters)
