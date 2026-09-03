from unittest.mock import AsyncMock, Mock

import pytest

from gateway.researcher import DeepResearcher


@pytest.mark.asyncio
async def test_structured_report_exposes_sources_and_progress_without_ingesting():
    researcher = DeepResearcher()
    researcher._find_sources = AsyncMock(return_value=['https://example.com/a', 'https://example.com/b'])
    researcher._scrape_sources = AsyncMock(return_value='### SOURCE: https://example.com/a\nevidence')
    researcher._synthesize_findings = Mock(return_value='research summary')
    researcher._ingest_findings = AsyncMock(return_value=True)
    events = []
    def progress(stage, sources=None):
        events.append((stage, sources))

    report = await researcher.technical_deep_dive_report('topic', progress=progress)

    assert report['summary'] == 'research summary'
    assert report['sources'] == ['https://example.com/a', 'https://example.com/b']
    assert 'evidence' in report['findings']
    assert events == [
        ('searching', None),
        ('reading', ['https://example.com/a', 'https://example.com/b']),
        ('synthesizing', ['https://example.com/a', 'https://example.com/b']),
    ]
    researcher._ingest_findings.assert_not_awaited()

@pytest.mark.asyncio
async def test_missing_tavily_key_is_backend_failure(monkeypatch):
    researcher = DeepResearcher()
    researcher.tavily_key = None
    with pytest.raises(Exception, match='Tavily|TAVILY'):
        await researcher.technical_deep_dive_report('topic')


@pytest.mark.asyncio
async def test_tavily_request_failure_is_not_zero_results(monkeypatch):
    researcher = DeepResearcher()
    researcher.tavily_key = 'key'
    client = AsyncMock()
    client.post.side_effect = RuntimeError('search timeout')
    researcher._get_client = AsyncMock(return_value=client)
    with pytest.raises(Exception, match='search timeout'):
        await researcher.technical_deep_dive_report('topic')


def test_synthesis_failure_propagates(monkeypatch):
    researcher = DeepResearcher()
    monkeypatch.setattr('gateway.llm_client.chat', Mock(side_effect=RuntimeError('provider unavailable')))
    with pytest.raises(Exception, match='provider unavailable'):
        researcher._synthesize_findings('topic', 'evidence')
