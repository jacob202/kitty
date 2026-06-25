"""Tests for Kitty knowledge base."""
from unittest.mock import MagicMock, patch

import pytest


def test_knowledge_chunk_schema():
    from datetime import datetime

    from contracts.knowledge_chunk import KnowledgeChunk
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


def test_detect_doc_type_service_manual(tmp_path):
    from gateway.knowledge import detect_doc_type
    f = tmp_path / "haynes_honda_civic_repair_manual.pdf"
    assert detect_doc_type(f) == "service_manual"


def test_detect_doc_type_health(tmp_path):
    from gateway.knowledge import detect_doc_type
    f = tmp_path / "blood_results_2025.pdf"
    assert detect_doc_type(f) == "health_record"


def test_detect_doc_type_session_log(tmp_path):
    from gateway.knowledge import detect_doc_type
    f = tmp_path / "session_2025.jsonl"
    assert detect_doc_type(f) == "session_log"


def test_detect_doc_type_content_signals(tmp_path):
    from gateway.knowledge import detect_doc_type
    f = tmp_path / "document.pdf"
    content = "Step 1: Remove the oil drain plug. Torque to 22 ft-lb. Part No: 12345."
    assert detect_doc_type(f, content) == "service_manual"


def test_detect_doc_type_general_fallback(tmp_path):
    from gateway.knowledge import detect_doc_type
    f = tmp_path / "notes.txt"
    assert detect_doc_type(f) == "general"


def test_extract_jsonl_session(tmp_path):
    import json

    from gateway.knowledge import _extract_jsonl_session
    f = tmp_path / "session.jsonl"
    lines = [
        json.dumps({"role": "user", "content": "How do I fix my car?"}),
        json.dumps({"role": "assistant", "content": "Check the brake pads first."}),
    ]
    f.write_text("\n".join(lines))
    result = _extract_jsonl_session(f)
    assert "How do I fix my car?" in result
    assert "brake pads" in result


def test_get_knowledge_block_empty_on_no_results():
    mock_instance = MagicMock()
    mock_instance.count.return_value = 0
    mock_instance.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    from gateway import knowledge as kb
    with patch("gateway.archivist._get_collection", return_value=mock_instance), \
         patch("gateway.archivist._embed_cached", return_value=tuple([0.1] * 768)):
        result = kb.get_knowledge_block("anything")
    assert result == ""


def test_get_knowledge_block_formats_with_source():
    mock_results = {
        "documents": [["Jacob owns a 2010 Honda Civic. He bought it used."]],
        "metadatas": [[{"source": "car_history.txt", "sensitivity": "low", "chunk_index": 0}]],
        "distances": [[0.1]],
    }
    mock_instance = MagicMock()
    mock_instance.count.return_value = 1
    mock_instance.query.return_value = mock_results
    from gateway import knowledge as kb
    with patch("gateway.archivist._get_collection", return_value=mock_instance), \
         patch("gateway.archivist._embed_cached", return_value=tuple([0.1] * 768)):
        result = kb.get_knowledge_block("Honda")
    assert "car_history.txt" in result
    assert "Honda Civic" in result


def test_query_embedding_uses_short_timeout():
    from gateway import archivist

    response = MagicMock()
    response.json.return_value = {"embeddings": [[0.1]]}
    archivist._embed_cached.cache_clear()

    try:
        with patch("requests.post", return_value=response) as post:
            assert archivist._embed_cached("quick lookup") == (0.1,)
    finally:
        archivist._embed_cached.cache_clear()

    assert post.call_args.kwargs["timeout"] == 5


def test_extract_chatgpt_json_returns_text(tmp_path):
    import json

    from gateway.knowledge import _extract_chatgpt_json
    conv = {
        "title": "Test Chat",
        "id": "abc",
        "mapping": {
            "node1": {"id": "node1", "parent": None, "children": ["node2"],
                      "message": {"author": {"role": "user"}, "create_time": 1.0,
                                  "content": {"content_type": "text", "parts": ["Hello Kitty"]}}},
            "node2": {"id": "node2", "parent": "node1", "children": [],
                      "message": {"author": {"role": "assistant"}, "create_time": 2.0,
                                  "content": {"content_type": "text", "parts": ["Hi Jacob!"]}}}
        }
    }
    f = tmp_path / "conversations-000.json"
    f.write_text(json.dumps([conv]))
    text = _extract_chatgpt_json(f)
    assert "Hello Kitty" in text
    assert "Hi Jacob!" in text
    assert "USER:" in text
    assert "ASSISTANT:" in text


def test_extract_chatgpt_json_skips_empty_parts(tmp_path):
    import json

    from gateway.knowledge import _extract_chatgpt_json
    conv = {
        "title": "Empty",
        "id": "xyz",
        "mapping": {
            "n1": {"id": "n1", "parent": None, "children": [],
                   "message": {"author": {"role": "user"}, "create_time": 1.0,
                               "content": {"content_type": "text", "parts": [""]}}}
        }
    }
    f = tmp_path / "conversations-001.json"
    f.write_text(json.dumps([conv]))
    text = _extract_chatgpt_json(f)
    assert text == ""


def test_extract_sqlite_journal_returns_text(tmp_path):
    import sqlite3

    from gateway.knowledge import _extract_sqlite_journal
    db_path = tmp_path / "journal.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE journal (id INTEGER PRIMARY KEY, timestamp TEXT, role TEXT, content TEXT, content_hash TEXT)")
    conn.execute("INSERT INTO journal VALUES (1,'2026-01-01','user','What is up?','hash1')")
    conn.execute("INSERT INTO journal VALUES (2,'2026-01-01','assistant','Not much.','hash2')")
    conn.commit()
    conn.close()
    text = _extract_sqlite_journal(db_path)
    assert "USER: What is up?" in text
    assert "ASSISTANT: Not much." in text


def test_extract_text_dispatches_chatgpt_json(tmp_path):
    import json

    from gateway.knowledge import _extract_text
    conv = {
        "title": "Dispatch test",
        "id": "d1",
        "mapping": {
            "n1": {"id": "n1", "parent": None, "children": [],
                   "message": {"author": {"role": "user"}, "create_time": 1.0,
                               "content": {"content_type": "text", "parts": ["dispatch works"]}}}
        }
    }
    f = tmp_path / "conversations-002.json"
    f.write_text(json.dumps([conv]))
    text = _extract_text(f)
    assert "dispatch works" in text


def test_librarian_defaults_to_free_ingest_lane(monkeypatch):
    from gateway.librarian import generate_source_summary

    monkeypatch.delenv("KITTY_INGEST_LLM_MODEL", raising=False)

    fake_report = (
        '{"summary":"manual","authority_score":0.9,"relevance_period":"persistent",'
        '"needs_vision":true,"primary_topic":"service_manual"}'
    )
    with patch("gateway.librarian.call_llm", return_value=fake_report) as mock_call:
        generate_source_summary(
            source_name="manual.pdf",
            text_preview="Torque specs and disassembly steps.",
            doc_type="service_manual",
        )

    assert mock_call.call_args.kwargs["model"] == "kitty-default"


@pytest.mark.integration
def test_ingest_and_search_roundtrip(tmp_path):
    """Write a text file, ingest it, search for it. Requires Ollama."""
    from gateway.knowledge import _get_collection, ingest_file, search_knowledge
    _get_collection.cache_clear()

    test_file = tmp_path / "test_roundtrip.txt"
    test_file.write_text("Kitty integration test: Jacob has a purple mountain bicycle he uses on weekends.")

    n = ingest_file(test_file, sensitivity="low", source_label="test_roundtrip.txt")
    assert n > 0, "Expected at least one chunk to be ingested"

    results = search_knowledge("bicycle", limit=3)
    texts = [r["text"] for r in results]
    assert any("bicycle" in t.lower() for t in texts), f"Expected 'bicycle' in results: {texts}"
