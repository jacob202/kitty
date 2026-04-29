"""
Memory inspect/forget — list and delete memories.
"""
from typing import List, Dict, Optional
from .vector_store import SQLiteVecStore, NullStore


def list_memories(store: object = None, limit: int = 10) -> List[Dict]:
    """List recent memories."""
    if store is None:
        store = SQLiteVecStore()
    # Simple: return all (no real timestamp yet)
    conn = __import__('sqlite3').connect(store.db_path)
    rows = conn.execute(
        "SELECT id, text, metadata FROM vectors LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [{"id": r[0], "text": r[1][:50] + "...", "metadata": eval(r[2])} for r in rows]


def forget(store: object = None, doc_id: str = None, query: str = None) -> Dict:
    """Forget a memory by ID or query match."""
    if store is None:
        store = SQLiteVecStore()
    if doc_id:
        deleted = store.delete(doc_id)
        return {"deleted": deleted, "id": doc_id}
    if query:
        results = store.search(query, k=1)
        if results:
            doc_id = results[0]["id"]
            store.delete(doc_id)
            return {"deleted": True, "id": doc_id, "query": query}
    return {"deleted": False, "reason": "No ID or query provided"}
