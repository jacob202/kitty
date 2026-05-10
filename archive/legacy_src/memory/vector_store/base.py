"""
Vector store base class.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any


class VectorStore(ABC):
    """Abstract base for vector storage."""

    @abstractmethod
    def add(self, text: str, metadata: Optional[Dict] = None) -> str:
        """Add a document, return ID."""
        pass

    @abstractmethod
    def search(self, query: str, k: int = 5) -> List[Dict]:
        """Search by similarity, return list of {id, score, metadata}."""
        pass

    @abstractmethod
    def delete(self, doc_id: str) -> bool:
        """Delete by ID."""
        pass

    @abstractmethod
    def get(self, doc_id: str) -> Optional[Dict]:
        """Get document by ID."""
        pass
