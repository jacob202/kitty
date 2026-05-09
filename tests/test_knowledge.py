"""Tests for Kitty knowledge base."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_knowledge_chunk_schema():
    from contracts.knowledge_chunk import KnowledgeChunk
    from datetime import datetime
    chunk = KnowledgeChunk(
        chunk_id="test__chunk_0",
        text="This is a test document about Jacob's car.",
        source="test.txt",
        file_path="/tmp/test.txt",
        chunk_index=0,
    )
    assert chunk.sensitivity == "low"
    assert chunk.allowed_models == ["cloud_ok"]
    assert isinstance(chunk.ingested_at, datetime)


def test_chunk_text_splits_correctly():
    from gateway.knowledge import _chunk_text
    words = ["word"] * 100
    text = " ".join(words)
    chunks = _chunk_text(text, chunk_size=20, overlap=5)
    assert len(chunks) > 1
    # Each chunk should have at most 20 words
    for chunk in chunks:
        assert len(chunk.split()) <= 20


def test_extract_text_reads_txt(tmp_path):
    from gateway.knowledge import _extract_text
    f = tmp_path / "test.txt"
    f.write_text("Hello Kitty world")
    result = _extract_text(f)
    assert "Hello Kitty world" in result


def test_get_knowledge_block_empty_on_no_results():
    with patch("gateway.knowledge._get_collection") as mock_coll:
        mock_instance = MagicMock()
        mock_instance.count.return_value = 0
        mock_instance.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        mock_coll.return_value = mock_instance
        from gateway import knowledge as kb
        with patch.object(kb, "_get_collection", return_value=mock_instance):
            with patch.object(kb, "_embed", return_value=[[0.1] * 768]):
                result = kb.get_knowledge_block("anything")
    assert result == ""


def test_get_knowledge_block_formats_with_source():
    mock_results = {
        "documents": [["Jacob owns a 2010 Honda Civic. He bought it used."]],
        "metadatas": [[{"source": "car_history.txt", "sensitivity": "low", "chunk_index": 0}]],
        "distances": [[0.1]],
    }
    with patch("gateway.knowledge._get_collection") as mock_coll:
        mock_instance = MagicMock()
        mock_instance.count.return_value = 1
        mock_instance.query.return_value = mock_results
        mock_coll.return_value = mock_instance
        from gateway import knowledge as kb
        with patch.object(kb, "_get_collection", return_value=mock_instance):
            with patch.object(kb, "_embed", return_value=[[0.1] * 768]):
                result = kb.get_knowledge_block("Honda")
    assert "car_history.txt" in result
    assert "Honda Civic" in result


@pytest.mark.integration
def test_ingest_and_search_roundtrip(tmp_path):
    """Write a text file, ingest it, search for it. Requires Ollama."""
    from gateway.knowledge import ingest_file, search_knowledge, _get_collection
    _get_collection.cache_clear()

    test_file = tmp_path / "test_roundtrip.txt"
    test_file.write_text("Kitty integration test: Jacob has a purple mountain bicycle he uses on weekends.")

    n = ingest_file(test_file, sensitivity="low", source_label="test_roundtrip.txt")
    assert n > 0, "Expected at least one chunk to be ingested"

    results = search_knowledge("bicycle", limit=3)
    texts = [r["text"] for r in results]
    assert any("bicycle" in t.lower() for t in texts), f"Expected 'bicycle' in results: {texts}"
