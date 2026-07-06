"""Expert retrieval contracts for packet 008."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from gateway import knowledge


@pytest.mark.asyncio
async def test_search_filters_to_allowed_collections():
    store = MagicMock()
    store.count.return_value = 1
    store.query.return_value = {
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }

    with (
        patch("gateway.knowledge.archivist._get_collection", return_value=store),
        patch(
            "gateway.knowledge.archivist._embed_cached",
            return_value=(0.1, 0.2, 0.3),
        ),
    ):
        assert (
            await knowledge.search(
                "where is the state route?",
                collections=["coding_repo"],
            )
            == []
        )

    assert store.query.call_args.kwargs["where"] == {"collection": {"$in": ["coding_repo"]}}


@pytest.mark.asyncio
async def test_search_raises_when_knowledge_store_is_unavailable():
    with (
        patch(
            "gateway.knowledge.archivist._embed_cached",
            side_effect=RuntimeError("ollama refused connection"),
        ),
        pytest.raises(
            knowledge.KnowledgeSearchError,
            match="ollama refused connection",
        ),
    ):
        await knowledge.search("state route")


@pytest.mark.asyncio
async def test_coding_expert_refuses_when_uploaded_sources_do_not_support_answer():
    answerer = MagicMock(side_effect=AssertionError("model must not be called"))

    async def no_results(*_args, **_kwargs):
        return []

    with patch("gateway.knowledge.search", side_effect=no_results):
        result = await knowledge.answer_as_expert(
            "Which route owns the state console?",
            expert="coding_repo",
            answerer=answerer,
        )

    assert result == {
        "expert": "coding_repo",
        "supported": False,
        "answer": ("Uploaded sources in collection 'coding_repo' do not support this answer."),
        "citations": [],
        "privacy": "local",
    }
    answerer.assert_not_called()


@pytest.mark.asyncio
async def test_coding_expert_uses_only_allowed_collection_and_returns_citations():
    chunks = [
        {
            "text": "The state routes are registered by gateway/routes/register.py.",
            "source": "ARCHITECTURE.md",
            "metadata": {"page_num": 12, "chunk_index": 3},
        }
    ]
    search_calls = []

    async def fake_search(query, **kwargs):
        search_calls.append((query, kwargs))
        return chunks

    answerer = MagicMock(return_value="The route registry owns that wiring [1].")
    with patch("gateway.knowledge.search", side_effect=fake_search):
        result = await knowledge.answer_as_expert(
            "Which route owns the state console?",
            expert="coding_repo",
            answerer=answerer,
        )

    assert search_calls == [
        (
            "Which route owns the state console?",
            {
                "limit": 5,
                "collections": ["coding_repo"],
                "stitch_context": False,
            },
        )
    ]
    assert result["supported"] is True
    assert result["answer"] == "The route registry owns that wiring [1]."
    assert result["privacy"] == "local"
    assert result["citations"] == [
        {
            "id": 1,
            "source": "ARCHITECTURE.md",
            "page_num": 12,
            "chunk_index": 3,
            "label": "ARCHITECTURE.md, page 12",
        }
    ]
    prompt = answerer.call_args.args[0]
    assert "gateway/routes/register.py" in prompt
    assert "Use only the uploaded source excerpts" in prompt


@pytest.mark.asyncio
async def test_coding_expert_rejects_uncited_model_answer():
    chunks = [
        {
            "text": "The route registry owns gateway route wiring.",
            "source": "ARCHITECTURE.md",
            "metadata": {"chunk_index": 3},
        }
    ]

    async def fake_search(*_args, **_kwargs):
        return chunks

    with (
        patch("gateway.knowledge.search", side_effect=fake_search),
        pytest.raises(knowledge.ExpertAnswerError, match="citation"),
    ):
        await knowledge.answer_as_expert(
            "Which route owns the state console?",
            expert="coding_repo",
            answerer=lambda _prompt: "The route registry owns it.",
        )


def test_local_expert_answerer_calls_only_mlx_loopback():
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "choices": [{"message": {"content": "The route registry owns it [1]."}}]
    }

    with patch("gateway.knowledge.httpx.post", return_value=response) as post:
        answer = knowledge._call_local_expert_model("Use source [1].")

    assert answer == "The route registry owns it [1]."
    assert post.call_args.args[0] == ("http://127.0.0.1:8010/v1/chat/completions")
    assert post.call_args.kwargs["json"]["model"] == "default_model"
    assert post.call_args.kwargs["timeout"] == 60


def test_local_expert_answerer_retries_once_then_raises_with_context(caplog):
    request = httpx.Request("POST", knowledge.LOCAL_EXPERT_URL)
    response = httpx.Response(
        503,
        request=request,
        text="model is still loading",
    )
    error = httpx.HTTPStatusError(
        "503 Service Unavailable",
        request=request,
        response=response,
    )

    with (
        patch("gateway.knowledge.httpx.post", side_effect=error) as post,
        pytest.raises(
            knowledge.ExpertAnswerError,
            match="status=503.*model is still loading",
        ),
    ):
        knowledge._call_local_expert_model("Use source [1].")

    assert post.call_count == 2
    assert "retrying once" in caplog.text
