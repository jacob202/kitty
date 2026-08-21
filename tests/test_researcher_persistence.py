from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from gateway.researcher import DeepResearcher, deep_dive


@pytest.mark.asyncio
async def test_deep_research_does_not_ingest_by_default() -> None:
    researcher = DeepResearcher()
    researcher._find_sources = AsyncMock(return_value=["https://example.com/source"])
    researcher._scrape_sources = AsyncMock(return_value="source evidence")
    researcher._synthesize_findings = Mock(return_value="research summary")
    researcher._ingest_findings = AsyncMock(return_value=True)

    result = await researcher.technical_deep_dive("topic")

    assert result == "research summary"
    researcher._ingest_findings.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_ingest_reports_success_only_after_successful_promotion() -> None:
    researcher = DeepResearcher()
    researcher._find_sources = AsyncMock(return_value=["https://example.com/source"])
    researcher._scrape_sources = AsyncMock(return_value="source evidence")
    researcher._synthesize_findings = Mock(return_value="research summary")
    researcher._ingest_findings = AsyncMock(return_value=True)

    result = await researcher.technical_deep_dive("topic", ingest=True)

    assert result == "research summary\n\nSaved to Kitty's knowledge base."
    researcher._ingest_findings.assert_awaited_once()


@pytest.mark.asyncio
async def test_explicit_ingest_failure_is_not_reported_as_success() -> None:
    researcher = DeepResearcher()
    researcher._find_sources = AsyncMock(return_value=["https://example.com/source"])
    researcher._scrape_sources = AsyncMock(return_value="source evidence")
    researcher._synthesize_findings = Mock(return_value="research summary")
    researcher._ingest_findings = AsyncMock(return_value=False)

    result = await researcher.technical_deep_dive("topic", ingest=True)

    assert "saving it to the knowledge base failed" in result
    assert "Saved to Kitty's knowledge base" not in result


@pytest.mark.asyncio
async def test_gateway_convenience_wrapper_is_non_persistent_by_default() -> None:
    with patch(
        "gateway.researcher.DeepResearcher.technical_deep_dive",
        new=AsyncMock(return_value="done"),
    ) as run:
        assert await deep_dive("topic") == "done"

    run.assert_awaited_once_with("topic", ingest=False)
