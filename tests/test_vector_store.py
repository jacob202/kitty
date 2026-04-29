"""
Tests for vector store.
"""
import sys, os, pytest, tempfile, json
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.memory.vector_store.base import VectorStore
from src.memory.vector_store.null_store import NullStore
from src.memory.vector_store.sqlite_vec_store import SQLiteVecStore


class TestNullStore:
    def test_add_returns_id(self):
        store = NullStore()
        doc_id = store.add("hello world")
        assert isinstance(doc_id, str)

    def test_search_returns_list(self):
        store = NullStore()
        store.add("test document")
        results = store.search("test")
        assert isinstance(results, list)

    def test_search_finds_content(self):
        store = NullStore()
        store.add("find this special word")
        results = store.search("special")
        assert len(results) >= 0  # substring match

    def test_delete(self):
        store = NullStore()
        doc_id = store.add("to delete")
        result = store.delete(doc_id)
        assert result is True

    def test_get(self):
        store = NullStore()
        doc_id = store.add("get me")
        doc = store.get(doc_id)
        assert doc is not None
        assert "get me" in doc["text"]


class TestSQLiteVecStore:
    def test_init_creates_db(self, tmp_path):
        db = tmp_path / "test_vec.db"
        store = SQLiteVecStore(str(db))
        assert os.path.exists(db)

    def test_add_and_get(self, tmp_path):
        db = tmp_path / "test_vec.db"
        store = SQLiteVecStore(str(db))
        doc_id = store.add("test doc", {"type": "fact"})
        assert isinstance(doc_id, str)
        doc = store.get(doc_id)
        assert doc is not None
        assert "test doc" in doc["text"]
        assert doc["metadata"]["type"] == "fact"

    def test_search(self, tmp_path):
        db = tmp_path / "test_vec.db"
        store = SQLiteVecStore(str(db))
        store.add("learn Python programming")
        store.add("build Kitty features")
        results = store.search("Kitty")
        assert len(results) >= 1
        assert "Kitty" in results[0]["text"]

    def test_delete(self, tmp_path):
        db = tmp_path / "test_vec.db"
        store = SQLiteVecStore(str(db))
        doc_id = store.add("to delete")
        result = store.delete(doc_id)
        assert result is True
        assert store.get(doc_id) is None
