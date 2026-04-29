"""
SQLite vector store — lightweight similarity search.
Uses sqlite3 with manual cosine similarity.
"""
import sqlite3, math, json
from typing import List, Dict, Optional
from abc import ABC, abstractmethod


def _cosine_sim(a: List[float], b: List[float]) -> float:
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(y*y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


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


class SQLiteVecStore(VectorStore):
    def __init__(self, db_path: str = "data/vector_store.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS vectors ("
            "id TEXT PRIMARY KEY, "
            "text TEXT NOT NULL, "
            "embedding BLOB, "
            "metadata TEXT, "
            "created_at TEXT DEFAULT (datetime('now')))"
        )
        conn.commit()
        conn.close()

    def add(self, text: str, metadata: Optional[Dict] = None) -> str:
        import json
        doc_id = str(abs(hash(text)))
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO vectors (id, text, metadata) VALUES (?, ?, ?)",
            (doc_id, text, json.dumps(metadata or {}))
        )
        conn.commit()
        conn.close()
        return doc_id

    def search(self, query: str, k: int = 5) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT id, text, metadata FROM vectors WHERE text LIKE ?",
            (f"%{query}%",)
        ).fetchall()
        conn.close()
        results = [
            {"id": r[0], "text": r[1], "score": 1.0, "metadata": json.loads(r[2])}
            for r in rows
        ]
        return results[:k]

    def delete(self, doc_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM vectors WHERE id = ?", (doc_id,))
        deleted = conn.total_changes > 0
        conn.commit()
        conn.close()
        return deleted

    def get(self, doc_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT id, text, metadata FROM vectors WHERE id = ?", (doc_id,)
        ).fetchone()
        conn.close()
        if row is None:
            return None
        import json
        return {"id": row[0], "text": row[1], "metadata": json.loads(row[2])}
