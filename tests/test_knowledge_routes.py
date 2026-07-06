"""Tests for the /knowledge routes (packet 008)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes import knowledge as knowledge_route

# --- Fixtures ---


@pytest.fixture
def client():
    """A TestClient around a minimal app that mounts only the knowledge router."""
    app = FastAPI()
    app.include_router(knowledge_route.router)
    return TestClient(app)


@pytest.fixture
def fake_embedding():
    """A 4-dim embedding so the test never needs the real embed server."""
    return [0.1, 0.2, 0.3, 0.4]


@pytest.fixture
def mock_kb_collection():
    """A MagicMock standing in for chromadb's collection."""
    coll = MagicMock()
    coll.count.return_value = 0
    coll.get.return_value = {"ids": [], "metadatas": []}
    coll.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    return coll


def _patched_ingest_with_coll(coll: MagicMock, fake_embedding, ingest_exception=None):
    """Return a context manager stack that lets gateway.knowledge.ingest run
    end-to-end against an in-memory fake collection."""

    def fake_get_content_hash(text: str) -> str:
        return f"hash:{len(text)}"

    def fake_get_collection():
        return coll

    def fake_embed(texts):
        return [list(fake_embedding) for _ in texts]

    def fake_embed_cached(text: str):
        return tuple(fake_embedding)

    def fake_extract_text(path):
        from pathlib import Path

        if not path.exists():
            return ""
        if path.suffix.lower() == ".pdf":
            return ""
        return Path(path).read_text(encoding="utf-8", errors="ignore")

    def fake_preprocess(text: str) -> str:
        return text

    def fake_chunk_text(text: str, size: int, overlap: int):
        if not text.strip():
            return []
        words = text.split()
        chunks = []
        for i in range(0, len(words), max(1, size - overlap)):
            chunks.append(" ".join(words[i : i + size]))
            if i + size >= len(words):
                break
        return [c for c in chunks if c.strip()]

    def fake_detect_doc_type(path, text=""):
        return "general"

    def fake_generate_summary(source, text, doc_type):
        from contracts.knowledge_pipeline import LibrarianReport

        return LibrarianReport(
            summary=f"summary of {source}",
            authority_score=0.7,
            relevance_period="persistent",
            primary_topic="general",
        )

    def fake_is_high_quality(text: str) -> bool:
        return bool(text and len(text.strip()) >= 10)

    cm = [
        patch("gateway.knowledge.archivist._get_content_hash", side_effect=fake_get_content_hash),
        patch("gateway.knowledge.archivist._get_collection", side_effect=fake_get_collection),
        patch("gateway.knowledge.archivist._embed", side_effect=fake_embed),
        patch("gateway.knowledge.archivist._embed_cached", side_effect=fake_embed_cached),
        patch("gateway.knowledge.clerk._extract_text", side_effect=fake_extract_text),
        patch("gateway.knowledge.clerk.preprocess_text", side_effect=fake_preprocess),
        patch("gateway.knowledge.archivist._chunk_text", side_effect=fake_chunk_text),
        patch("gateway.knowledge.archivist.is_high_quality", side_effect=fake_is_high_quality),
        patch("gateway.knowledge.librarian.detect_doc_type", side_effect=fake_detect_doc_type),
        patch(
            "gateway.knowledge.librarian.generate_source_summary",
            side_effect=fake_generate_summary,
        ),
    ]
    if ingest_exception is not None:
        cm.append(patch("gateway.knowledge.ingest", side_effect=ingest_exception))
    return cm


def _enter_all(cms):
    """Enter a list of patch context managers and return a list of mocks."""
    mocks = []
    for cm in cms:
        mocks.append(cm.__enter__())
    return mocks


def _exit_all(cms):
    for cm in reversed(cms):
        cm.__exit__(None, None, None)


# --- Ingest tests ---


def test_ingest_happy_path_with_text_file(client, mock_kb_collection, tmp_path):
    """Sample text file → status=success, source_id matches the label."""
    sample = tmp_path / "kitty_notes.txt"
    body_text = (
        "Jacob's Honda Civic is a 2010 model. The oil drain plug torque is 22 ft-lb. "
        "Always replace the crush washer. The OEM part number is 12345-PLC-000."
    )
    sample.write_text(body_text, encoding="utf-8")

    cms = _patched_ingest_with_coll(mock_kb_collection, [0.1, 0.2, 0.3, 0.4])
    _enter_all(cms)
    try:
        r = client.post(
            "/knowledge/ingest",
            json={"path": str(sample), "source_label": "kitty_notes.txt"},
        )
    finally:
        _exit_all(cms)

    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["status"] == "success"
    assert payload["source_id"] == "kitty_notes.txt"
    assert payload["reason"]
    # collection was actually written to
    assert mock_kb_collection.add.called


def test_ingest_persists_collection_and_normalized_tags(client, mock_kb_collection, tmp_path):
    sample = tmp_path / "architecture.md"
    sample.write_text(
        "Kitty uses FastAPI routes and a local SQLite store for durable state.",
        encoding="utf-8",
    )

    cms = _patched_ingest_with_coll(mock_kb_collection, [0.1, 0.2, 0.3, 0.4])
    _enter_all(cms)
    try:
        response = client.post(
            "/knowledge/ingest",
            json={
                "path": str(sample),
                "collection": "coding_repo",
                "tags": [" Architecture ", "python", "architecture"],
            },
        )
    finally:
        _exit_all(cms)

    assert response.status_code == 200, response.text
    stored = mock_kb_collection.add.call_args.kwargs["metadatas"]
    assert stored
    assert {metadata["collection"] for metadata in stored} == {"coding_repo"}
    assert {tuple(json.loads(metadata["tags_json"])) for metadata in stored} == {
        ("architecture", "python")
    }


def test_ingest_nonexistent_file_returns_failed(client):
    r = client.post(
        "/knowledge/ingest",
        json={"path": "/tmp/definitely-does-not-exist-kitty-12345.txt"},
    )

    assert r.status_code == 200
    payload = r.json()
    assert payload["status"] == "failed"
    assert "not found" in payload["reason"].lower() or "no such file" in payload["reason"].lower()
    assert payload["source_id"]


def test_ingest_missing_both_path_and_url_returns_422(client):
    r = client.post("/knowledge/ingest", json={"sensitivity": "low"})
    assert r.status_code == 422


def test_ingest_url_download_succeeds(client, mock_kb_collection):
    """URL ingest streams into KNOWLEDGE_DIR/inbox and ingests from there."""
    sample_bytes = (
        b"Jacob tunes Sansui amplifiers. The bias voltage is 0.45V per channel. "
        b"Always let the unit warm up for at least 10 minutes before adjusting."
    )
    cms = _patched_ingest_with_coll(mock_kb_collection, [0.1, 0.2, 0.3, 0.4])

    fake_response = MagicMock()
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False
    fake_response.headers = {"content-type": "text/plain"}
    fake_response.raise_for_status.return_value = None
    fake_response.iter_content.return_value = [sample_bytes]

    cms.append(patch("gateway.routes.knowledge.requests.get", return_value=fake_response))
    _enter_all(cms)
    try:
        r = client.post(
            "/knowledge/ingest",
            json={"url": "https://example.com/sansui.txt"},
        )
    finally:
        _exit_all(cms)

    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["status"] == "success"
    assert payload["source_id"].endswith(".txt")


# --- Sources listing tests ---


def test_sources_listing_aggregates_chunks(client, mock_kb_collection):
    metadatas = [
        {
            "source": "kitty_notes.txt",
            "doc_type": "source_summary",
            "chunk_index": -1,
            "collection": "coding_repo",
            "tags_json": '["architecture","python"]',
            "sensitivity": "low",
            "authority_score": 0.8,
            "primary_topic": "Honda Civic maintenance",
            "content_hash": "abc123",
            "file_path": "/data/knowledge/kitty_notes.txt",
            "ingested_at": 1700000000,
            "modified_at": 1690000000,
            "created_at": 1680000000,
        },
        {
            "source": "kitty_notes.txt",
            "doc_type": "general",
            "chunk_index": 0,
            "collection": "coding_repo",
            "tags_json": '["architecture","python"]',
            "sensitivity": "low",
            "authority_score": 0.8,
            "primary_topic": "Honda Civic maintenance",
            "content_hash": "abc123",
            "file_path": "/data/knowledge/kitty_notes.txt",
            "ingested_at": 1700000000,
            "modified_at": 1690000000,
            "created_at": 1680000000,
        },
        {
            "source": "sansui.txt",
            "doc_type": "source_summary",
            "chunk_index": -1,
            "collection": "audio_repair",
            "tags_json": '["amplifier"]',
            "sensitivity": "low",
            "authority_score": 0.6,
            "primary_topic": "Sansui amplifier bias",
            "content_hash": "def456",
            "file_path": "/data/knowledge/sansui.txt",
            "ingested_at": 1700000100,
            "modified_at": 1690000100,
            "created_at": 1680000100,
        },
    ]
    mock_kb_collection.count.return_value = len(metadatas)
    mock_kb_collection.get.return_value = {
        "ids": [f"id-{i}" for i in range(len(metadatas))],
        "metadatas": metadatas,
    }

    with patch("gateway.knowledge.archivist._get_collection", return_value=mock_kb_collection):
        r = client.get("/knowledge/sources")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_chunks"] == 3
    assert body["total_sources"] == 2
    by_name = {s["name"]: s for s in body["sources"]}
    assert by_name["kitty_notes.txt"]["chunks"] == 2
    assert by_name["kitty_notes.txt"]["primary_topic"] == "Honda Civic maintenance"
    assert by_name["kitty_notes.txt"]["collection"] == "coding_repo"
    assert by_name["kitty_notes.txt"]["tags"] == ["architecture", "python"]
    assert by_name["sansui.txt"]["chunks"] == 1
    assert by_name["sansui.txt"]["collection"] == "audio_repair"
    assert by_name["sansui.txt"]["tags"] == ["amplifier"]


def test_sources_listing_empty_collection(client, mock_kb_collection):
    mock_kb_collection.count.return_value = 0
    with patch("gateway.knowledge.archivist._get_collection", return_value=mock_kb_collection):
        r = client.get("/knowledge/sources")
    assert r.status_code == 200
    assert r.json() == {"sources": [], "total_sources": 0, "total_chunks": 0}


# --- Search tests ---


def test_search_with_known_query_returns_chunks(client):
    fake_chunks = [
        {
            "text": "Jacob owns a 2010 Honda Civic with 145,000 miles on it.",
            "source": "kitty_notes.txt",
            "doc_type": "general",
            "score": 0.92,
            "ingested_at": 1700000000,
            "index": 0,
            "metadata": {
                "source": "kitty_notes.txt",
                "chunk_index": 0,
                "page_num": None,
                "is_visual": False,
                "sensitivity": "low",
                "primary_topic": "Honda Civic maintenance",
                "authority_score": 0.8,
                "relevance_period": "persistent",
                "content_hash": "abc123",
            },
        },
        {
            "text": "Source brief: Honda Civic service notes from Jacob's garage.",
            "source": "kitty_notes.txt",
            "doc_type": "source_summary",
            "score": 0.81,
            "ingested_at": 1700000000,
            "index": -1,
            "metadata": {
                "source": "kitty_notes.txt",
                "chunk_index": -1,
                "page_num": None,
                "is_visual": False,
                "sensitivity": "low",
                "primary_topic": "Honda Civic maintenance",
                "authority_score": 0.8,
                "relevance_period": "persistent",
                "content_hash": "abc123",
            },
        },
    ]

    async def fake_search(query, limit=5, **kwargs):
        assert query == "honda civic"
        return fake_chunks

    with patch("gateway.knowledge.search", side_effect=fake_search):
        r = client.get("/knowledge/search", params={"q": "honda civic"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["query"] == "honda civic"
    assert body["count"] == 2
    assert len(body["results"]) == 2
    first = body["results"][0]
    assert first["source"] == "kitty_notes.txt"
    assert first["reference"]["source"] == "kitty_notes.txt"
    assert first["reference"]["chunk_index"] == 0
    assert first["reference"]["is_visual"] is False
    assert "Honda Civic" in first["text"]


def test_search_empty_returns_explicit_message(client):
    async def fake_search(query, limit=5, **kwargs):
        return []

    with patch("gateway.knowledge.search", side_effect=fake_search):
        r = client.get("/knowledge/search", params={"q": "no-such-thing"})

    assert r.status_code == 200
    body = r.json()
    assert body["results"] == []
    assert "no relevant chunks" in body["message"].lower()
    assert body["query"] == "no-such-thing"


def test_search_empty_query_returns_message(client):
    r = client.get("/knowledge/search", params={"q": ""})
    assert r.status_code == 200
    body = r.json()
    assert body["results"] == []
    assert "empty query" in body["message"].lower()


def test_search_rejects_invalid_limit(client):
    r = client.get("/knowledge/search", params={"q": "anything", "limit": 999})
    assert r.status_code == 400


def test_expert_route_forbids_cloud_override(client):
    response = client.post(
        "/knowledge/expert",
        json={
            "query": "Which route owns the state console?",
            "expert": "coding_repo",
            "allow_cloud": True,
        },
    )

    assert response.status_code == 422


def test_expert_route_returns_supported_answer(client):
    expected = {
        "expert": "coding_repo",
        "supported": True,
        "answer": "The route registry owns that wiring [1].",
        "citations": [
            {
                "id": 1,
                "source": "ARCHITECTURE.md",
                "page_num": None,
                "chunk_index": 3,
                "label": "ARCHITECTURE.md, chunk 3",
            }
        ],
        "privacy": "local",
    }

    async def fake_answer(query, expert, limit):
        assert query == "Which route owns the state console?"
        assert expert == "coding_repo"
        assert limit == 5
        return expected

    with patch("gateway.knowledge.answer_as_expert", side_effect=fake_answer):
        response = client.post(
            "/knowledge/expert",
            json={
                "query": "Which route owns the state console?",
                "expert": "coding_repo",
            },
        )

    assert response.status_code == 200, response.text
    assert response.json() == expected


def test_expert_route_rejects_unknown_expert(client):
    response = client.post(
        "/knowledge/expert",
        json={"query": "Use my uploaded manuals", "expert": "not_real"},
    )

    assert response.status_code == 404
    assert "unknown knowledge expert" in response.json()["detail"]


def test_expert_route_rejects_whitespace_query(client):
    response = client.post(
        "/knowledge/expert",
        json={"query": "   ", "expert": "coding_repo"},
    )

    assert response.status_code == 422
