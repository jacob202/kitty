from __future__ import annotations

import json

import httpx
import pytest

from gateway import openviking_shadow as ovs


@pytest.mark.asyncio
async def test_retrieve_returns_bounded_resource_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "status": "ok",
        "result": {
            "resources": [
                {"uri": "viking://resources/kitty-kb/wiki/a.md", "score": 0.9, "content": "A" * 5000},
                {"uri": "viking://resources/kitty-kb/wiki/b.md", "score": 0.8, "content": "B"},
            ]
        },
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["target_uri"] == "viking://resources/kitty-kb"
        assert body["read_content"] is True
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(ovs, "get_http_client", lambda: _async_value(client))
    result = await ovs.retrieve("builder collision", limit=2, max_chars_per_hit=120)
    await client.aclose()

    assert [hit.uri for hit in result.hits] == [
        "viking://resources/kitty-kb/wiki/a.md",
        "viking://resources/kitty-kb/wiki/b.md",
    ]
    assert len(result.hits[0].content) == 120
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_shadow_mode_never_injects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITTY_OPENVIKING_MODE", "shadow")
    monkeypatch.setattr(
        ovs,
        "retrieve",
        lambda *_args, **_kwargs: _async_value(
            ovs.RetrievalResult(hits=(ovs.Hit("viking://x", 0.9, "secret"),), latency_ms=3.0)
        ),
    )
    assert await ovs.context_block("hello") is None


@pytest.mark.asyncio
async def test_context_mode_injects_bounded_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITTY_OPENVIKING_MODE", "context")
    monkeypatch.setattr(
        ovs,
        "retrieve",
        lambda *_args, **_kwargs: _async_value(
            ovs.RetrievalResult(hits=(ovs.Hit("viking://x", 0.9, "useful context"),), latency_ms=3.0)
        ),
    )
    block = await ovs.context_block("hello")
    assert block is not None
    assert "useful context" in block
    assert "viking://x" in block


@pytest.mark.asyncio
async def test_off_mode_does_not_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KITTY_OPENVIKING_MODE", raising=False)

    async def fail(*_args, **_kwargs):
        raise AssertionError("should not query")

    monkeypatch.setattr(ovs, "retrieve", fail)
    assert await ovs.context_block("hello") is None


async def _async_value(value):
    return value
