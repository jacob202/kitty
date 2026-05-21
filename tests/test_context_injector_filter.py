"""Tests for the Kitty Context Injector OWUI filter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.openwebui_filters.kitty_context_injector import Filter


def make_body(messages: list[dict]) -> dict:
    return {"messages": messages}


def make_fake_resp(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


# --- inlet tests ---


@pytest.mark.asyncio
async def test_inlet_no_messages_returns_body_unchanged():
    f = Filter()
    body = {}
    result = await f.inlet(body)
    assert result is body


@pytest.mark.asyncio
async def test_inlet_no_user_message_returns_body_unchanged():
    f = Filter()
    body = make_body([{"role": "system", "content": "You are Kitty."}])
    result = await f.inlet(body)
    assert result is body


@pytest.mark.asyncio
async def test_inlet_no_results_returns_body_unchanged():
    f = Filter()
    body = make_body([
        {"role": "system", "content": "You are Kitty."},
        {"role": "user", "content": "What is a MOSFET?"},
    ])
    fake_resp = make_fake_resp(200, {
        "knowledge": [], "memories": [], "journal": [], "todos": [], "query": "MOSFET",
    })

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_resp)):
        result = await f.inlet(body)

    assert result is body


@pytest.mark.asyncio
async def test_inlet_injects_context_after_user_message():
    f = Filter()
    body = make_body([
        {"role": "system", "content": "You are Kitty."},
        {"role": "user", "content": "What is a MOSFET?"},
    ])
    fake_resp = make_fake_resp(200, {
        "knowledge": [
            {"kind": "knowledge", "source": "electronics.pdf", "title": "MOSFET Basics",
             "text": "A MOSFET is a voltage-controlled transistor.", "score": 0.95, "metadata": {}},
        ],
        "memories": [], "journal": [], "todos": [], "query": "MOSFET",
    })

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_resp)):
        result = await f.inlet(body)

    messages = result["messages"]
    assert len(messages) == 3
    # order: system, user, injected context
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[2]["role"] == "system"
    assert "MOSFET Basics" in messages[2]["content"]
    assert "voltage-controlled" in messages[2]["content"]
    assert "Sources consulted" in messages[2]["content"]


@pytest.mark.asyncio
async def test_inlet_injects_multiple_sections():
    f = Filter()
    body = make_body([
        {"role": "system", "content": "You are Kitty."},
        {"role": "user", "content": "How did I sleep last night?"},
    ])
    fake_resp = make_fake_resp(200, {
        "knowledge": [
            {"kind": "knowledge", "source": "sleep_guide.pdf", "title": "Sleep Hygiene",
             "text": "Consistent sleep schedules improve rest.", "score": 0.85, "metadata": {}},
        ],
        "memories": [
            {"kind": "memory", "source": "memory", "title": "Jacob's sleep",
             "text": "Jacob slept 7 hours last night.", "score": 0.9, "metadata": {}},
        ],
        "journal": [], "todos": [], "query": "sleep last night",
    })

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_resp)):
        result = await f.inlet(body)

    context = result["messages"][2]["content"]
    assert "Sleep Hygiene" in context
    assert "Jacob's sleep" in context
    assert "Knowledge" in context
    assert "Memories" in context


@pytest.mark.asyncio
async def test_inlet_inserts_after_last_user_message():
    f = Filter()
    body = make_body([
        {"role": "system", "content": "You are Kitty."},
        {"role": "user", "content": "First question."},
        {"role": "assistant", "content": "First answer."},
        {"role": "user", "content": "Second question."},
    ])
    fake_resp = make_fake_resp(200, {
        "knowledge": [
            {"kind": "knowledge", "source": "doc.pdf", "title": "Doc",
             "text": "Content.", "score": 0.9, "metadata": {}},
        ],
        "memories": [], "journal": [], "todos": [], "query": "Second question.",
    })

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_resp)):
        result = await f.inlet(body)

    messages = result["messages"]
    assert len(messages) == 5
    assert messages[3]["role"] == "user"
    assert messages[3]["content"] == "Second question."
    assert messages[4]["role"] == "system"


@pytest.mark.asyncio
async def test_inlet_handles_gateway_unavailable():
    f = Filter()
    body = make_body([
        {"role": "user", "content": "What is a MOSFET?"},
    ])

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=ConnectionError("refused"))):
        result = await f.inlet(body)

    assert result is body


@pytest.mark.asyncio
async def test_inlet_truncates_long_source_text():
    f = Filter()
    long_text = "A" * 1000
    body = make_body([
        {"role": "system", "content": "You are Kitty."},
        {"role": "user", "content": "Tell me something long."},
    ])
    fake_resp = make_fake_resp(200, {
        "knowledge": [
            {"kind": "knowledge", "source": "long.pdf", "title": "Long Document",
             "text": long_text, "score": 0.9, "metadata": {}},
        ],
        "memories": [], "journal": [], "todos": [], "query": "long",
    })

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_resp)):
        result = await f.inlet(body)

    context = result["messages"][2]["content"]
    assert len(context) < 2000
    assert "..." in context


@pytest.mark.asyncio
async def test_inlet_stores_sources_on_self():
    f = Filter()
    body = make_body([
        {"role": "user", "content": "Tell me about audio circuits."},
    ])
    fake_resp = make_fake_resp(200, {
        "knowledge": [
            {"kind": "knowledge", "source": "audio.pdf", "title": "Audio Circuits",
             "text": "Op-amps are fundamental.", "score": 0.9, "metadata": {}},
        ],
        "memories": [], "journal": [], "todos": [], "query": "audio circuits",
    })

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_resp)):
        await f.inlet(body)

    assert len(f._sources) == 1
    assert f._sources[0]["source"] == "audio.pdf"


# --- outlet tests ---


@pytest.mark.asyncio
async def test_outlet_noop_when_no_sources():
    f = Filter()
    f._sources = []
    body = {"choices": [{"message": {"content": "Just a regular reply."}}]}
    result = await f.outlet(body)
    assert result is body


@pytest.mark.asyncio
async def test_outlet_noop_when_no_match():
    f = Filter()
    f._sources = [{"title": "MOSFET Basics", "source": "electronics.pdf"}]
    body = {"choices": [{"message": {"content": "That's a great question."}}]}
    result = await f.outlet(body)
    assert result is body


@pytest.mark.asyncio
async def test_outlet_appends_citation_when_content_matches():
    f = Filter()
    f._sources = [{"title": "MOSFET Basics", "source": "electronics.pdf"}]
    body = {"choices": [{"message": {"content": "A MOSFET works like this: MOSFET Basics explains it well."}}]}
    result = await f.outlet(body)

    content = result["choices"][0]["message"]["content"]
    assert "_Sources referenced:_" in content
    assert "MOSFET Basics" in content
    assert "electronics.pdf" in content


@pytest.mark.asyncio
async def test_outlet_noop_without_choices():
    f = Filter()
    f._sources = [{"title": "MOSFET Basics", "source": "electronics.pdf"}]
    body = {}
    result = await f.outlet(body)
    assert result is body
