from gateway import council_graph


def test_librarian_node_raises_for_unknown_specialist(monkeypatch):
    monkeypatch.setattr(council_graph, "call_llm", lambda **kwargs: '["ghost_specialist"]')

    try:
        council_graph.librarian_node({"query": "mystery", "messages": []})
    except KeyError as exc:
        assert "ghost_specialist" in str(exc)
    else:
        raise AssertionError("Expected librarian_node to reject unknown specialists")


def test_specialist_node_records_retrieval_diagnostics(monkeypatch):
    monkeypatch.setattr(
        council_graph.search_client,
        "search_kb",
        lambda kb_name, query, *args: {
            "summary": "[Source: service-manual.pdf]\nCheck driver transistors first.",
            "hit_count": 1,
            "sources": ["service-manual.pdf"],
            "status": "ok",
            "kb_name": kb_name,
            "kb_id": "kb-123",
            "query": query,
        },
    )

    result = council_graph.specialist_node(
        {
            "query": "Sansui amp blown MOSFET",
            "target_specialists": ["audio_repair"],
            "context_pool": [],
        }
    )

    assert result["retrieval_debug"]["specialist"] == "audio_repair"
    assert result["retrieval_debug"]["hit_count"] == 1
    assert result["retrieval_debug"]["sources"] == ["service-manual.pdf"]
    assert result["synthesis_allowed"] is False
    assert result["context_pool"][0]["content"].startswith("[Source: service-manual.pdf]")
    assert result["retrieval_debug"]["searched_specialists"] == ["audio_repair"]
    assert result["retrieval_debug"]["total_hit_count"] == 1


def test_specialist_node_aggregates_multiple_specialists(monkeypatch):
    def fake_search(kb_name, query, *args):
        if kb_name == "electronics":
            return {
                "summary": "[Source: electronics.pdf]\nCheck gate resistors.",
                "hit_count": 2,
                "sources": ["electronics.pdf"],
                "status": "ok",
                "kb_name": kb_name,
                "kb_id": "kb-elec",
                "query": query,
            }
        return {
            "summary": "[Source: repair.pdf]\nCompare with the good channel.",
            "hit_count": 1,
            "sources": ["repair.pdf"],
            "status": "ok",
            "kb_name": kb_name,
            "kb_id": "kb-repair",
            "query": query,
        }

    monkeypatch.setattr(council_graph.search_client, "search_kb", fake_search)

    result = council_graph.specialist_node(
        {
            "query": "Sansui amp blown MOSFET",
            "target_specialists": ["electronics", "audio_repair"],
            "context_pool": [],
        }
    )

    assert result["synthesis_allowed"] is True
    assert len(result["context_pool"]) == 2
    assert result["retrieval_debug"]["specialist"] == "electronics"
    assert result["retrieval_debug"]["searched_specialists"] == ["electronics", "audio_repair"]
    assert result["retrieval_debug"]["total_hit_count"] == 3
    assert len(result["retrieval_debug"]["attempts"]) == 2


def test_synthesis_node_demands_inline_citations(monkeypatch):
    seen = {}

    def fake_call_llm(**kwargs):
        seen["prompt"] = kwargs["messages"][0]["content"]
        return "Grounded answer with citations."

    monkeypatch.setattr(council_graph, "call_llm", fake_call_llm)

    result = council_graph.synthesis_node(
        {
            "query": "Sansui amp blown MOSFET",
            "context_pool": [{"specialist": "electronics", "content": "[Source: service-manual.pdf]\nCheck gate resistors."}],
            "synthesis_allowed": True,
            "retrieval_debug": {
                "specialist": "electronics",
                "kb_name": "electronics",
                "hit_count": 3,
                "total_hit_count": 3,
                "sources": ["service-manual.pdf"],
                "status": "ok",
            },
        }
    )

    assert "inline citations" in seen["prompt"].lower()
    assert "[electronics:" in seen["prompt"].lower()
    assert result["final_response"] == "Grounded answer with citations."


def test_synthesis_node_blocks_when_retrieval_is_empty():
    result = council_graph.synthesis_node(
        {
            "query": "Sansui amp blown MOSFET",
            "context_pool": [{"specialist": "audio repair", "content": "No relevant context found."}],
            "synthesis_allowed": False,
            "retrieval_debug": {
                "specialist": "audio_repair",
                "kb_name": "audio_repair",
                "hit_count": 0,
                "total_hit_count": 0,
                "sources": [],
                "status": "ok",
                "searched_specialists": ["electronics", "audio_repair"],
            },
        }
    )

    assert result["final_response"] == "Insufficient evidence. Please refine your query or ingest more documents."
