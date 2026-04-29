"""
Null vector store — no-op for testing.
"""
from typing import List, Dict, Optional
from .base import VectorStore


class NullStore(VectorStore):
    """No-op vector store."""

    def __init__(self, *args, **kwargs):
        self.docs = {}

    def add(self, text: str, metadata: Optional[Dict] = None) -> str:
        doc_id = str(len(self.docs))
        self.docs[doc_id] = {"text": text, "metadata": metadata or {}}
        return doc_id

    def search(self, query: str, k: int = 5) -> List[Dict]:
        # Simple substring match for testing
        results = []
        for doc_id, doc in self.docs.items():
            if query.lower() in doc["text"].lower():
                results.append({"id": doc_id, "score": 1.0, "metadata": doc["metadata"]})
        return results[:k]

    def delete(self, doc_id: str) -> bool:
        if doc_id in self.docs:
            del self.docs[doc_id]
            return True
        return False

    def get(self, doc_id: str) -> Optional[Dict]:
        return self.docs.get(doc_id)
