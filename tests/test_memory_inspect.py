"""
Tests for memory inspect/forget.
"""
import sys, os, pytest, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.memory.inspect import list_memories, forget
from src.memory.vector_store.sqlite_vec_store import SQLiteVecStore


class TestMemoryInspect:
    def test_list_empty(self, tmp_path):
        store = SQLiteVecStore(str(tmp_path / "test_vec.db"))
        result = list_memories(store)
        assert isinstance(result, list)

    def test_list_with_data(self, tmp_path):
        store = SQLiteVecStore(str(tmp_path / "test_vec.db"))
        store.add("memory 1")
        store.add("memory 2")
        result = list_memories(store, limit=5)
        assert len(result) == 2

    def test_forget_by_id(self, tmp_path):
        store = SQLiteVecStore(str(tmp_path / "test_vec.db"))
        doc_id = store.add("to forget")
        result = forget(store, doc_id=doc_id)
        assert result["deleted"] is True
        assert result["id"] == doc_id

    def test_forget_by_query(self, tmp_path):
        store = SQLiteVecStore(str(tmp_path / "test_vec.db"))
        store.add("find this specific thing")
        result = forget(store, query="specific")
        assert result["deleted"] is True

    def test_forget_nothing(self):
        result = forget(None, query="nothing")
        assert result["deleted"] is False
        assert "reason" in result
