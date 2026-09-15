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


@pytest.mark.asyncio
async def test_ingest_and_search_roundtrip_uses_ephemeral_store(tmp_path, monkeypatch):
    """Ingest and retrieve through real ephemeral Chroma, without network or user data."""
    import chromadb

    from contracts.knowledge_pipeline import LibrarianReport
    from gateway import knowledge

    collection = chromadb.EphemeralClient().get_or_create_collection(
        "kitty_test_knowledge", metadata={"hnsw:space": "cosine"}
    )

    def deterministic_embedding(text: str) -> list[float]:
        lowered = text.lower()
        if "bicycle" in lowered:
            return [1.0, 0.0, 0.0]
        if "volcano" in lowered:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    monkeypatch.setattr(knowledge.archivist, "_get_collection", lambda: collection)
    monkeypatch.setattr(
        knowledge.archivist,
        "_embed",
        lambda texts, timeout=120: [deterministic_embedding(text) for text in texts],
    )
    monkeypatch.setattr(
        knowledge.archivist,
        "_embed_cached",
        lambda text: tuple(deterministic_embedding(text)),
    )
    monkeypatch.setattr(
        knowledge.librarian,
        "generate_source_summary",
        lambda *args: LibrarianReport(
            summary="A deterministic test source.",
            authority_score=0.8,
            relevance_period="persistent",
            primary_topic="test",
            needs_vision=False,
        ),
    )

    bicycle_file = tmp_path / "bicycle_notes.txt"
    bicycle_file.write_text(
        "The workshop inventory includes a purple mountain bicycle with hydraulic brakes."
    )
    volcano_file = tmp_path / "volcano_notes.txt"
    volcano_file.write_text(
        "The geology notebook describes a dormant volcano and layers of basalt rock."
    )

    bicycle_ingest = await knowledge.ingest_file(
        bicycle_file,
        sensitivity="low",
        source_label="bicycle_notes.txt",
        collection="cycling",
    )
    volcano_ingest = await knowledge.ingest_file(
        volcano_file,
        sensitivity="low",
        source_label="volcano_notes.txt",
        collection="geology",
    )

    assert bicycle_ingest.status == "success"
    assert volcano_ingest.status == "success"
    stored = collection.get(where={"source": "bicycle_notes.txt"})
    assert len(stored["ids"]) == bicycle_ingest.chunks_count
    assert any("purple mountain bicycle" in text.lower() for text in stored["documents"])

    results = await knowledge.search_knowledge(
        "bicycle", limit=1, stitch_context=False
    )
    assert len(results) == 1
    assert results[0]["source"] == "bicycle_notes.txt"
    assert "purple mountain bicycle" in results[0]["text"].lower()

    filtered = await knowledge.search_knowledge(
        "volcano", collections=["cycling"], limit=3, stitch_context=False
    )
    assert filtered
    assert {row["source"] for row in filtered} == {"bicycle_notes.txt"}
    assert {row["metadata"]["collection"] for row in filtered} == {"cycling"}


@pytest.mark.asyncio
async def test_ingest_replacement_stores_new_chunks_before_deleting_old(tmp_path, monkeypatch):
    from contracts.knowledge_pipeline import LibrarianReport
    from gateway import knowledge

    path = tmp_path / "manual.txt"
    path.write_text("new manual content", encoding="utf-8")
    events = []

    class Store:
        def get(self, *, where):
            if "content_hash" in where:
                return {"ids": []}
            return {"ids": ["old-1", "old-2"]}

        def add(self, *, documents, embeddings, ids, metadatas):
            events.append(("add", list(ids)))

        def delete(self, *, ids):
            events.append(("delete", list(ids)))

    store = Store()
    monkeypatch.setattr(knowledge.archivist, "_get_collection", lambda: store)
    monkeypatch.setattr(knowledge.clerk, "_extract_text", lambda _p: "new manual content")
    monkeypatch.setattr(knowledge.archivist, "_get_content_hash", lambda _text: "new-hash")
    monkeypatch.setattr(knowledge.librarian, "detect_doc_type", lambda *_args: "general")
    monkeypatch.setattr(
        knowledge.librarian,
        "generate_source_summary",
        lambda *_args: LibrarianReport(
            summary="summary",
            authority_score=0.8,
            relevance_period="persistent",
            primary_topic="test",
            needs_vision=False,
        ),
    )

    async def pipeline(*_args):
        return ["replacement chunk"], [{"chunk_index": 0, "is_visual": False}]

    monkeypatch.setattr(knowledge, "_run_pipeline", pipeline)
    monkeypatch.setattr(knowledge.archivist, "_embed", lambda _chunks: [[0.1, 0.2]])

    result = await knowledge.ingest(path, source_label="manual.txt", force_refresh=True)

    assert result.status == "success"
    assert events[0][0] == "add"
    assert events[1] == ("delete", ["old-1", "old-2"])


@pytest.mark.asyncio
async def test_ingest_skipped_replacement_preserves_old_source(tmp_path, monkeypatch):
    from contracts.knowledge_pipeline import LibrarianReport
    from gateway import knowledge

    path = tmp_path / "manual.txt"
    path.write_text("new manual content", encoding="utf-8")
    deleted = []

    class Store:
        def get(self, *, where):
            if "content_hash" in where:
                return {"ids": []}
            return {"ids": ["old-1"]}

        def add(self, **_kwargs):
            raise AssertionError("skipped replacement must not add")

        def delete(self, *, ids):
            deleted.extend(ids)

    monkeypatch.setattr(knowledge.archivist, "_get_collection", lambda: Store())
    monkeypatch.setattr(knowledge.clerk, "_extract_text", lambda _p: "new manual content")
    monkeypatch.setattr(knowledge.archivist, "_get_content_hash", lambda _text: "new-hash")
    monkeypatch.setattr(knowledge.librarian, "detect_doc_type", lambda *_args: "general")
    monkeypatch.setattr(
        knowledge.librarian,
        "generate_source_summary",
        lambda *_args: LibrarianReport(
            summary="summary",
            authority_score=0.8,
            relevance_period="persistent",
            primary_topic="test",
            needs_vision=False,
        ),
    )

    async def empty_pipeline(*_args):
        return [], []

    monkeypatch.setattr(knowledge, "_run_pipeline", empty_pipeline)

    result = await knowledge.ingest(path, source_label="manual.txt", force_refresh=True)

    assert result.status == "skipped"
    assert deleted == []


@pytest.mark.asyncio
async def test_ingest_add_failure_never_deletes_old_source(tmp_path, monkeypatch):
    from contracts.knowledge_pipeline import LibrarianReport
    from gateway import knowledge

    path = tmp_path / "manual.txt"
    path.write_text("new manual content", encoding="utf-8")
    deleted = []

    class Store:
        def get(self, *, where):
            if "content_hash" in where:
                return {"ids": []}
            return {"ids": ["old-1"]}

        def add(self, **_kwargs):
            raise RuntimeError("store unavailable")

        def delete(self, *, ids):
            deleted.extend(ids)

    monkeypatch.setattr(knowledge.archivist, "_get_collection", lambda: Store())
    monkeypatch.setattr(knowledge.clerk, "_extract_text", lambda _p: "new manual content")
    monkeypatch.setattr(knowledge.archivist, "_get_content_hash", lambda _text: "new-hash")
    monkeypatch.setattr(knowledge.librarian, "detect_doc_type", lambda *_args: "general")
    monkeypatch.setattr(
        knowledge.librarian,
        "generate_source_summary",
        lambda *_args: LibrarianReport(
            summary="summary",
            authority_score=0.8,
            relevance_period="persistent",
            primary_topic="test",
            needs_vision=False,
        ),
    )

    async def pipeline(*_args):
        return ["replacement chunk"], [{"chunk_index": 0, "is_visual": False}]

    monkeypatch.setattr(knowledge, "_run_pipeline", pipeline)
    monkeypatch.setattr(knowledge.archivist, "_embed", lambda _chunks: [[0.1, 0.2]])

    with pytest.raises(RuntimeError, match="store unavailable"):
        await knowledge.ingest(path, source_label="manual.txt", force_refresh=True)

    assert deleted == []

@pytest.mark.asyncio
async def test_ingest_same_second_refresh_uses_disjoint_replacement_ids(tmp_path, monkeypatch):
    from contracts.knowledge_pipeline import LibrarianReport
    from gateway import knowledge

    path = tmp_path / "manual.txt"
    path.write_text("replacement", encoding="utf-8")
    old_ids = ["manual.txt__chunk_0_1234"]
    added_ids = []
    class Store:
        def get(self, *, where):
            return {"ids": []} if "content_hash" in where else {"ids": old_ids}
        def add(self, *, documents, embeddings, ids, metadatas):
            added_ids.extend(ids)
        def delete(self, *, ids):
            pass
    monkeypatch.setattr(knowledge.archivist, "_get_collection", lambda: Store())
    monkeypatch.setattr(knowledge.clerk, "_extract_text", lambda _p: "replacement")
    monkeypatch.setattr(knowledge.archivist, "_get_content_hash", lambda _text: "new-hash")
    monkeypatch.setattr(knowledge.librarian, "detect_doc_type", lambda *_args: "general")
    monkeypatch.setattr(knowledge.librarian, "generate_source_summary", lambda *_args: LibrarianReport(summary="summary", authority_score=0.8, relevance_period="persistent", primary_topic="test", needs_vision=False))
    async def pipeline(*_args):
        return ["replacement chunk"], [{"chunk_index": 0, "is_visual": False}]
    monkeypatch.setattr(knowledge, "_run_pipeline", pipeline)
    monkeypatch.setattr(knowledge.archivist, "_embed", lambda _chunks: [[0.1, 0.2]])
    monkeypatch.setattr(knowledge.time, "time", lambda: 1234)
    result = await knowledge.ingest(path, source_label="manual.txt", force_refresh=True)
    assert result.status == "success"
    assert added_ids
    assert set(added_ids).isdisjoint(old_ids)


@pytest.mark.asyncio
async def test_search_returns_typed_evidence_metadata(tmp_path, monkeypatch):
    import chromadb

    from contracts.knowledge_pipeline import EvidenceMetadata, LibrarianReport
    from gateway import knowledge

    collection = chromadb.EphemeralClient().get_or_create_collection(
        "kitty_test_evidence_metadata", metadata={"hnsw:space": "cosine"}
    )
    monkeypatch.setattr(knowledge.archivist, "_get_collection", lambda: collection)
    monkeypatch.setattr(knowledge.archivist, "_embed", lambda texts, timeout=120: [[1.0, 0.0] for _ in texts])
    monkeypatch.setattr(knowledge.archivist, "_embed_cached", lambda text: (1.0, 0.0))
    monkeypatch.setattr(
        knowledge.librarian,
        "generate_source_summary",
        lambda *args: LibrarianReport(summary="source", authority_score=0.5),
    )

    source = tmp_path / "herbal.txt"
    source.write_text("Herbal reference material discussing botanical preparations and safety context.")
    evidence = EvidenceMetadata(
        source_id="health-src",
        source_sha256="b" * 64,
        logical_unit_id="work:health-src",
        retrieval_title="Historical Herbal Reference",
        domains=["health_biology_medicine"],
        expert_profiles=["health_biology"],
        authority_tier="contextual_or_traditional_health_reference",
        authority_status="named_author_needs_bibliographic_review",
        currency_sensitivity="high_health_or_clinical",
        currency_status="authority_and_recency_review_required",
        clinical_use_policy="verify_current_clinical_guidance_externally_before_action",
    )
    result = await knowledge.ingest(source, source_label="Historical Herbal Reference", evidence=evidence)
    assert result.status == "success"

    hits = await knowledge.search("botanical preparations", limit=1, stitch_context=False)
    assert hits[0]["evidence"]["source_id"] == "health-src"
    assert hits[0]["evidence"]["logical_unit_id"] == "work:health-src"
    assert hits[0]["evidence"]["authority_tier"] == "contextual_or_traditional_health_reference"
    assert hits[0]["evidence"]["clinical_use_policy"] == "verify_current_clinical_guidance_externally_before_action"


@pytest.mark.asyncio
async def test_search_uses_active_corpus_fts_when_vector_embedding_fails(tmp_path, monkeypatch):
    import json
    import sqlite3

    from gateway import knowledge

    db = tmp_path / "corpus.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE VIRTUAL TABLE chunks USING fts5("
            "chunk_id UNINDEXED, source_id UNINDEXED, logical_unit_id UNINDEXED, "
            "source_title, retrieval_title, work_id UNINDEXED, work_title, domains, subjects, "
            "doc_type UNINDEXED, locator_start UNINDEXED, locator_end UNINDEXED, text, "
            "tokenize='porter unicode61')"
        )
        conn.execute(
            "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "chunk-1",
                "health-src",
                "work:health-src",
                "Historical Herbal Reference",
                "Historical Herbal Reference",
                "work:health-src",
                "Historical Herbal Reference",
                "health_biology_medicine",
                "botanical_medicine",
                "textbook",
                "12",
                "13",
                "Herbal medicine adverse effects interactions and pharmacology require careful safety review.",
            ),
        )

    manifest = tmp_path / "sources.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "source_id": "health-src",
                "sha256": "c" * 64,
                "logical_unit_id": "work:health-src",
                "work_id": "work:health-src",
                "series_id": None,
                "series_order": None,
                "retrieval_title": "Historical Herbal Reference",
                "publication_year": 1998,
                "edition": "2",
                "metadata_basis": "curated_bibliographic_review",
                "domains": ["health_biology_medicine"],
                "subjects": ["botanical_medicine"],
                "expert_profiles": ["health_biology"],
                "authority_tier": "contextual_or_traditional_health_reference",
                "authority_status": "named_author_needs_bibliographic_review",
                "currency_sensitivity": "high_health_or_clinical",
                "currency_status": "authority_and_recency_review_required",
                "evidence_role": "contextual_reference_not_current_clinical_authority",
                "clinical_use_policy": "verify_current_clinical_guidance_externally_before_action",
                "work_relation": "unique_or_unresolved",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    projection = tmp_path / "projection.json"
    projection.write_text(
        json.dumps(
            {
                "schema": "kitty.runtime-retrieval-projection.v1",
                "status": "active",
                "fts_db": str(db),
                "source_manifest": str(manifest),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("KITTY_CORPUS_RETRIEVAL_PROJECTION", str(projection))
    monkeypatch.setattr(
        knowledge.archivist,
        "_embed_cached",
        lambda query: (_ for _ in ()).throw(RuntimeError("embedding unavailable")),
    )

    hits = await knowledge.search(
        "herbal medicine adverse effects interactions pharmacology",
        limit=2,
        stitch_context=False,
    )

    assert hits
    assert hits[0]["source"] == "Historical Herbal Reference"
    assert hits[0]["retrieval_method"] == "fts"
    assert hits[0]["evidence"]["source_id"] == "health-src"
    assert hits[0]["evidence"]["logical_unit_id"] == "work:health-src"
    assert hits[0]["evidence"]["clinical_use_policy"] == "verify_current_clinical_guidance_externally_before_action"
    assert hits[0]["metadata"]["locator_start"] == "12"

@pytest.mark.asyncio
async def test_active_corpus_fts_treats_hyphenated_query_as_literal_terms(tmp_path, monkeypatch):
    import json
    import sqlite3

    from gateway import knowledge

    db = tmp_path / "corpus.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE VIRTUAL TABLE chunks USING fts5("
            "chunk_id UNINDEXED, source_id UNINDEXED, logical_unit_id UNINDEXED, "
            "source_title, retrieval_title, work_id UNINDEXED, work_title, domains, subjects, "
            "doc_type UNINDEXED, locator_start UNINDEXED, locator_end UNINDEXED, text, "
            "tokenize='porter unicode61')"
        )
        conn.execute(
            "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "chunk-1", "vehicle-src", "work:vehicle", "Vehicle Manual", "Vehicle Manual",
                "work:vehicle", "Vehicle Manual", "automotive", "fuel_system", "service_manual",
                "44", "45", "Remove the in-tank fuel pump and sending unit from the pickup fuel tank.",
            ),
        )
    manifest = tmp_path / "sources.jsonl"
    manifest.write_text(json.dumps({
        "source_id":"vehicle-src", "sha256":"d"*64, "logical_unit_id":"work:vehicle",
        "work_id":"work:vehicle", "retrieval_title":"Vehicle Manual", "domains":["automotive"],
        "expert_profiles":["automotive"], "metadata_basis":"curated",
    }) + "\n")
    projection = tmp_path / "projection.json"
    projection.write_text(json.dumps({
        "status":"active", "fts_db":str(db), "source_manifest":str(manifest)
    }))
    monkeypatch.setenv("KITTY_CORPUS_RETRIEVAL_PROJECTION", str(projection))

    hits = await knowledge.search(
        "How do I get the in-tank gasoline sending unit out of a pickup?",
        limit=3,
        stitch_context=False,
    )
    assert hits
    assert hits[0]["source"] == "Vehicle Manual"



@pytest.mark.asyncio
async def test_active_corpus_fts_filters_selected_expert_before_ranking(tmp_path, monkeypatch):
    import json
    import sqlite3

    from gateway import knowledge

    db = tmp_path / "corpus.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE VIRTUAL TABLE chunks USING fts5("
            "chunk_id UNINDEXED, source_id UNINDEXED, logical_unit_id UNINDEXED, "
            "source_title, retrieval_title, work_id UNINDEXED, work_title, domains, subjects, "
            "doc_type UNINDEXED, locator_start UNINDEXED, locator_end UNINDEXED, text, "
            "tokenize='porter unicode61')"
        )
        conn.execute(
            "CREATE TABLE expert_membership ("
            "expert TEXT NOT NULL, source_id TEXT NOT NULL, logical_unit_id TEXT NOT NULL, "
            "PRIMARY KEY (expert, source_id))"
        )
        conn.executemany(
            "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("audio", "audio-src", "work:audio", "Audio Manual", "Audio Manual", "work:audio", "Audio Manual", "audio", "power", "manual", "1", "1", "power supply transistor service"),
                ("vehicle", "vehicle-src", "work:vehicle", "Vehicle Manual", "Vehicle Manual", "work:vehicle", "Vehicle Manual", "automotive", "fuel", "service_manual", "44", "45", "power supply fuel service vehicle"),
            ],
        )
        conn.executemany(
            "INSERT INTO expert_membership VALUES (?,?,?)",
            [
                ("electronics_audio", "audio-src", "work:audio"),
                ("automotive", "vehicle-src", "work:vehicle"),
                ("general_research", "audio-src", "work:audio"),
                ("general_research", "vehicle-src", "work:vehicle"),
            ],
        )
    manifest = tmp_path / "sources.jsonl"
    manifest.write_text("\n".join([
        json.dumps({"source_id":"audio-src","sha256":"a"*64,"logical_unit_id":"work:audio","retrieval_title":"Audio Manual","expert_profiles":["electronics_audio","general_research"]}),
        json.dumps({"source_id":"vehicle-src","sha256":"b"*64,"logical_unit_id":"work:vehicle","retrieval_title":"Vehicle Manual","expert_profiles":["automotive","general_research"]}),
    ]) + "\n")
    projection = tmp_path / "projection.json"
    projection.write_text(json.dumps({"status":"active","fts_db":str(db),"source_manifest":str(manifest)}))
    monkeypatch.setenv("KITTY_CORPUS_RETRIEVAL_PROJECTION", str(projection))

    hits = await knowledge.search("power supply service", limit=3, expert_profile="automotive")

    assert [hit["source"] for hit in hits] == ["Vehicle Manual"]
    assert hits[0]["evidence"]["expert_profiles"] == ["automotive", "general_research"]

    general_hits = await knowledge.search(
        "power supply service", limit=3, expert_profile="general_research"
    )
    assert {hit["source"] for hit in general_hits} == {"Audio Manual", "Vehicle Manual"}



@pytest.mark.asyncio
async def test_default_search_keeps_uploaded_chroma_results_with_active_corpus(monkeypatch):
    from gateway import knowledge

    corpus_hit = {
        "text": "factory brake procedure",
        "source": "Factory Manual",
        "score": 1.0,
        "ingested_at": 0,
        "index": 0,
        "metadata": {},
        "evidence": {"logical_unit_id": "work:factory"},
        "retrieval_method": "fts",
    }
    monkeypatch.setattr(knowledge, "_search_active_corpus_fts", lambda *args, **kwargs: [corpus_hit])
    monkeypatch.setattr(knowledge.archivist, "_embed_cached", lambda _query: (0.1, 0.2))

    collection = MagicMock()
    collection.count.return_value = 1
    collection.query.return_value = {
        "documents": [["Jacob's uploaded brake note"]],
        "metadatas": [[{"source": "uploaded-note.txt", "collection": "general", "chunk_index": 0}]],
        "distances": [[0.05]],
    }
    monkeypatch.setattr(knowledge.archivist, "_get_collection", lambda: collection)

    hits = await knowledge.search("brake note", limit=2, stitch_context=False)

    assert [hit["source"] for hit in hits] == ["Factory Manual", "uploaded-note.txt"]
    assert hits[1]["retrieval_method"] == "vector"


@pytest.mark.asyncio
async def test_active_corpus_fts_reads_past_duplicate_logical_unit_window(tmp_path, monkeypatch):
    import json
    import sqlite3

    from gateway import knowledge

    db = tmp_path / "corpus.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE VIRTUAL TABLE chunks USING fts5("
            "chunk_id UNINDEXED, source_id UNINDEXED, logical_unit_id UNINDEXED, "
            "source_title, retrieval_title, work_id UNINDEXED, work_title, domains, subjects, "
            "doc_type UNINDEXED, locator_start UNINDEXED, locator_end UNINDEXED, text, "
            "tokenize='porter unicode61')"
        )
        rows = [
            (f"dup-{i}", "dup-src", "work:dup", "Duplicate Work", "Duplicate Work",
             "work:dup", "Duplicate Work", "electronics", "power", "textbook",
             str(i), str(i), f"power supply service common term {i}")
            for i in range(70)
        ]
        rows.append((
            "other-1", "other-src", "work:other", "Other Work", "Other Work",
            "work:other", "Other Work", "electronics", "power", "textbook",
            "1", "1", "power supply service common term alternate source",
        ))
        conn.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)

    manifest = tmp_path / "sources.jsonl"
    manifest.write_text("\n".join([
        json.dumps({"source_id":"dup-src","sha256":"a"*64,"logical_unit_id":"work:dup","retrieval_title":"Duplicate Work"}),
        json.dumps({"source_id":"other-src","sha256":"b"*64,"logical_unit_id":"work:other","retrieval_title":"Other Work"}),
    ]) + "\n")
    projection = tmp_path / "projection.json"
    projection.write_text(json.dumps({"status":"active","fts_db":str(db),"source_manifest":str(manifest)}))
    monkeypatch.setenv("KITTY_CORPUS_RETRIEVAL_PROJECTION", str(projection))

    hits = knowledge._search_active_corpus_fts("power supply service common term", 2)

    assert hits is not None
    assert [hit["source"] for hit in hits] == ["Duplicate Work", "Other Work"]

def test_active_corpus_experts_are_derived_from_active_manifest(tmp_path, monkeypatch):
    import json
    import sqlite3

    from gateway import knowledge

    db = tmp_path / "corpus.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE expert_membership (expert TEXT, source_id TEXT, logical_unit_id TEXT)")
        conn.executemany("INSERT INTO expert_membership VALUES (?,?,?)", [
            ("automotive", "s1", "work:a"),
            ("automotive", "s2", "work:a"),
            ("automotive", "s3", "work:b"),
        ])
    manifest = tmp_path / "sources.jsonl"
    manifest.write_text("\n".join([
        json.dumps({"source_id":"s1","logical_unit_id":"work:a","retrieval_title":"Manual A","expert_profiles":["automotive"],"subjects":["brakes"],"format":".pdf"}),
        json.dumps({"source_id":"s2","logical_unit_id":"work:a","retrieval_title":"Manual A chapter","expert_profiles":["automotive"],"subjects":["brakes"],"format":".pdf"}),
        json.dumps({"source_id":"s3","logical_unit_id":"work:b","retrieval_title":"Manual B","expert_profiles":["automotive"],"subjects":["fuel_system"],"format":".pdf"}),
    ]) + "\n")
    projection = tmp_path / "projection.json"
    projection.write_text(json.dumps({"status":"active","fts_db":str(db),"source_manifest":str(manifest)}))
    monkeypatch.setenv("KITTY_CORPUS_RETRIEVAL_PROJECTION", str(projection))

    state = knowledge.active_corpus_experts()

    assert state["status"] == "active"
    assert state["experts"] == [
        {
            "id": "automotive",
            "label": "Automotive",
            "book_count": 2,
            "source_count": 3,
            "tags": ["brakes", "fuel_system"],
            "formats": [".pdf"],
            "sample_title": "Manual A",
        },
        {
            "id": "general_research",
            "label": "General Research",
            "book_count": 2,
            "source_count": 3,
            "tags": ["brakes", "fuel_system"],
            "formats": [".pdf"],
            "sample_title": "Manual A",
        },
    ]

@pytest.mark.parametrize(
    ("query", "task_type", "competencies", "freshness", "authority", "diversity"),
    [
        (
            "What is the exact rear caliper bracket torque on a 2010 Honda Ridgeline?",
            "exact_lookup", {"automotive"}, "corpus_ok", "primary_preferred", "single_authoritative_ok",
        ),
        (
            "Derive the electromagnetic wave equation from Maxwell equations in a homogeneous medium.",
            "derivation", {"math_physics", "electronics_audio"}, "corpus_ok", "established_reference_preferred", "multiple_logical_units",
        ),
        (
            "Is this herbal supplement safe to combine with a prescription medicine today?",
            "current_safety", {"health_biology"}, "current_external_required", "current_authoritative_required", "multiple_logical_units",
        ),
        (
            "How do I call the current OpenAI responses API in Python today?",
            "current_api", {"ai_software"}, "current_external_required", "primary_preferred", "single_authoritative_ok",
        ),
        (
            "Compare Popper and Kuhn on scientific progress without treating either position as consensus.",
            "comparison", {"philosophy_humanities"}, "corpus_ok", "source_attribution_required", "preserve_disagreement",
        ),
        (
            "My power amplifier transformer hums mechanically and makes the chassis vibrate. How should I diagnose it?",
            "diagnostic", {"electronics_audio", "mechanical_systems"}, "corpus_ok", "established_reference_preferred", "multiple_logical_units",
        ),
        (
            "A medical paper mentions code allocation. What evidence supports the clinical claim?",
            "evidence_review", {"health_biology"}, "current_external_preferred", "current_authoritative_required", "multiple_logical_units",
        ),
        (
            "What are the current Saskatchewan rules for this benefit?",
            "current_lookup", {"general_research"}, "current_external_required", "primary_preferred", "single_authoritative_ok",
        ),
    ],
)
def test_build_evidence_policy_routes_task_authority_and_freshness(
    query, task_type, competencies, freshness, authority, diversity
):
    from gateway.knowledge import build_evidence_policy

    policy = build_evidence_policy(query)
    assert policy.task_type == task_type
    assert set(policy.competencies) == competencies
    assert policy.freshness == freshness
    assert policy.authority_requirement == authority
    assert policy.diversity == diversity
    assert policy.current_verification_required == (freshness == "current_external_required")


def test_evidence_policy_uses_token_boundaries_not_substring_domain_matches():
    from gateway.knowledge import build_evidence_policy

    policy = build_evidence_policy(
        "Derive the electromagnetic wave equation in a homogeneous medium."
    )
    assert "health_biology" not in policy.competencies
    assert policy.safety == "standard"


def test_evidence_policy_preserves_vehicle_applicability_and_equipment_specificity():
    from gateway.knowledge import build_evidence_policy

    vehicle = build_evidence_policy(
        "What is the exact rear caliper bracket torque on a 2010 Honda Ridgeline?"
    )
    audio = build_evidence_policy(
        "What bias voltage should I set on a Sansui AU-7900 service procedure?"
    )
    assert "vehicle_model_specific" in vehicle.applicability
    assert vehicle.exactness == "exact"
    assert "equipment_model_specific" in audio.applicability
    assert audio.exactness == "exact"
    assert audio.authority_requirement == "service_manual_preferred"



def test_evidence_policy_cross_routes_acoustics_to_physics():
    from gateway.knowledge import build_evidence_policy

    policy = build_evidence_policy(
        "Why does a loudspeaker cabinet resonance couple to room modes?"
    )
    assert set(policy.competencies) == {"electronics_audio", "math_physics"}


def _write_synthetic_corpus_candidate(tmp_path):
    import json
    import sqlite3

    profiles = [
        "electronics_audio", "automotive", "mechanical_systems", "ai_software",
        "math_physics", "mind_learning_communication", "health_biology",
        "philosophy_humanities", "general_research",
    ]
    specialist = profiles[:-1]
    tmp_path.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    ingest_rows = []
    memberships = {profile: [] for profile in profiles}
    for index, profile in enumerate(specialist, start=1):
        source_id = f"source-{index}"
        sha = f"{index:064x}"[-64:]
        row = {
            "source_id": source_id,
            "sha256": sha,
            "logical_unit_id": f"work:{index}",
            "work_id": f"work:{index}",
            "retrieval_title": f"Reference {profile}",
            "domains": [profile],
            "subjects": [f"subject_{index}"],
            "expert_profiles": [profile],
            "publication_year": 2020,
            "edition": "1",
            "clinical_use_policy": "background_only" if profile == "health_biology" else "",
        }
        manifest_rows.append(row)
        memberships[profile].append(source_id)
        memberships["general_research"].append(source_id)
        ingest_rows.append({
            "path": str(tmp_path / f"{source_id}.pdf"),
            "source_label": f"Reference {profile} [src:{source_id}]",
            "tags": [f"expert_{profile}", f"domain_{profile}"],
            "evidence": {
                "source_id": source_id,
                "source_sha256": sha,
                "logical_unit_id": f"work:{index}",
                "retrieval_title": f"Reference {profile}",
                "domains": [profile],
                "subjects": [f"subject_{index}"],
                "expert_profiles": [profile],
                "publication_year": 2020,
                "edition": "1",
                "clinical_use_policy": row["clinical_use_policy"],
            },
        })

    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("\n".join(json.dumps(row) for row in manifest_rows) + "\n")
    ingest = tmp_path / "ingest.jsonl"
    ingest.write_text("\n".join(json.dumps(row) for row in ingest_rows) + "\n")
    collections = tmp_path / "collections.json"
    collections.write_text(json.dumps({
        "profiles": {
            profile: {
                "ready_source_count": len(memberships[profile]),
                "ready_logical_unit_count": len(memberships[profile]),
            }
            for profile in profiles
        },
        "source_memberships": memberships,
    }))
    profile_path = tmp_path / "profiles.json"
    profile_path.write_text(json.dumps({profile: {} for profile in profiles}))
    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text(json.dumps({
        "policy_version": "evidence-policy-2026-09-15.v1",
        "ranking_version": "fts-bm25-logical-diversity-2026-09-15.v1",
        "clinical_policy_version": "clinical-current-guidance-separation-2026-09-15.v1",
        "summary": {"cases": len(profiles), "passed": len(profiles), "failed": 0},
        "results": [
            {"id": f"fixture-{profile}", "profile": profile, "pass": True, "top5": []}
            for profile in profiles
        ],
    }))
    ledger = tmp_path / "correction-ledger.json"
    ledger.write_text(json.dumps({"schema": "kitty.corpus-correction-ledger.v1", "changes": []}))

    db = tmp_path / "corpus.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE VIRTUAL TABLE chunks USING fts5("
            "chunk_id UNINDEXED, source_id UNINDEXED, logical_unit_id UNINDEXED, "
            "source_title, retrieval_title, work_id UNINDEXED, work_title, domains, subjects, "
            "doc_type UNINDEXED, locator_start UNINDEXED, locator_end UNINDEXED, text)"
        )
        conn.execute("CREATE TABLE expert_membership (expert TEXT, source_id TEXT, logical_unit_id TEXT)")
        for index, row in enumerate(manifest_rows, start=1):
            conn.execute(
                "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"chunk-{index}", row["source_id"], row["logical_unit_id"], row["retrieval_title"],
                 row["retrieval_title"], row["logical_unit_id"], row["retrieval_title"],
                 row["domains"][0], row["subjects"][0], "textbook", "1", "2",
                 f"evidence for {row['expert_profiles'][0]}"),
            )
        for profile, source_ids in memberships.items():
            for source_id in source_ids:
                logical = next(row["logical_unit_id"] for row in manifest_rows if row["source_id"] == source_id)
                conn.execute("INSERT INTO expert_membership VALUES (?,?,?)", (profile, source_id, logical))

    return {
        "source_manifest": manifest,
        "collections": collections,
        "ingest_requests": ingest,
        "fts_db": db,
        "profiles": profile_path,
        "benchmark": benchmark,
        "correction_ledger": ledger,
    }


def test_validate_corpus_candidate_requires_one_membership_truth_and_nine_profiles(tmp_path):
    import json

    from gateway import knowledge

    artifacts = _write_synthetic_corpus_candidate(tmp_path)
    summary = knowledge.validate_corpus_candidate(artifacts)
    assert summary["source_count"] == 8
    assert summary["logical_unit_count"] == 8
    assert summary["membership_count"] == 16
    assert summary["chunk_count"] == 8
    assert summary["benchmark_profiles"] == set(knowledge.CORPUS_REQUIRED_PROFILES)

    rows = [json.loads(line) for line in artifacts["ingest_requests"].read_text().splitlines()]
    rows[0]["evidence"]["expert_profiles"] = ["wrong_profile"]
    artifacts["ingest_requests"].write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    with pytest.raises(knowledge.CorpusProjectionUnavailableError, match="ingest evidence"):
        knowledge.validate_corpus_candidate(artifacts)


def test_publish_candidate_is_content_addressed_and_repair_invalidates_proof(tmp_path):
    import json

    from gateway import knowledge

    artifacts = _write_synthetic_corpus_candidate(tmp_path / "inputs")
    publication_root = tmp_path / "published"
    first = knowledge.publish_corpus_candidate(artifacts, publication_root, publisher_git_commit="abc123")
    assert first["candidate_id"]
    receipt = first["receipt_path"]
    assert receipt.exists()
    published_manifest = receipt.parent / json.loads(receipt.read_text())["artifacts"]["source_manifest"]["filename"]
    assert published_manifest.stat().st_mode & 0o222 == 0

    benchmark = json.loads(artifacts["benchmark"].read_text())
    benchmark["results"][0]["note"] = "repair changes candidate bytes"
    artifacts["benchmark"].write_text(json.dumps(benchmark))
    second = knowledge.publish_corpus_candidate(artifacts, publication_root, publisher_git_commit="abc123")
    assert second["candidate_id"] != first["candidate_id"]
    assert second["receipt_sha256"] != first["receipt_sha256"]


def test_activate_published_candidate_requires_exact_binding_and_rolls_back(tmp_path, monkeypatch):
    import json

    from gateway import knowledge

    artifacts = _write_synthetic_corpus_candidate(tmp_path / "inputs")
    published = knowledge.publish_corpus_candidate(artifacts, tmp_path / "published", publisher_git_commit="abc123")
    pointer = tmp_path / "active.json"
    pointer.write_text(json.dumps({"status": "active", "legacy": True}))

    monkeypatch.setattr(knowledge, "CORPUS_PUBLICATION_BINDING", {
        "candidate_id": published["candidate_id"],
        "receipt_sha256": "0" * 64,
    })
    with pytest.raises(knowledge.CorpusProjectionUnavailableError, match="binding"):
        knowledge.activate_published_corpus_candidate(published["receipt_path"], pointer)
    assert json.loads(pointer.read_text())["legacy"] is True

    monkeypatch.setattr(knowledge, "CORPUS_PUBLICATION_BINDING", {
        "candidate_id": published["candidate_id"],
        "receipt_sha256": published["receipt_sha256"],
    })
    projection = knowledge.activate_published_corpus_candidate(published["receipt_path"], pointer)
    assert projection["candidate_id"] == published["candidate_id"]
    assert projection["status"] == "active"
    assert projection["schema"] == "kitty.runtime-retrieval-projection.v2"


def test_published_projection_runtime_rejects_tampered_exact_candidate(tmp_path, monkeypatch):
    import json

    from gateway import knowledge

    artifacts = _write_synthetic_corpus_candidate(tmp_path / "inputs")
    published = knowledge.publish_corpus_candidate(artifacts, tmp_path / "published", publisher_git_commit="abc123")
    monkeypatch.setattr(knowledge, "CORPUS_PUBLICATION_BINDING", {
        "candidate_id": published["candidate_id"],
        "receipt_sha256": published["receipt_sha256"],
    })
    pointer = tmp_path / "active.json"
    knowledge.activate_published_corpus_candidate(published["receipt_path"], pointer)
    monkeypatch.setenv("KITTY_CORPUS_RETRIEVAL_PROJECTION", str(pointer))
    knowledge._verify_published_receipt.cache_clear()
    assert knowledge._active_corpus_projection() is not None

    receipt = json.loads(published["receipt_path"].read_text())
    manifest_path = published["receipt_path"].parent / receipt["artifacts"]["source_manifest"]["filename"]
    manifest_path.chmod(0o644)
    manifest_path.write_text(manifest_path.read_text() + "tamper\n")
    knowledge._verify_published_receipt.cache_clear()
    with pytest.raises(knowledge.CorpusProjectionUnavailableError, match="artifact hash"):
        knowledge._active_corpus_projection()


def test_corpus_diversity_cap_allows_bounded_repeat_for_exact_authority_lookup():
    from gateway.knowledge import _corpus_logical_unit_cap

    assert _corpus_logical_unit_cap("Why does a power amplifier hum?") == 1
    assert _corpus_logical_unit_cap("What is the exact bias voltage on this amplifier?") == 2
