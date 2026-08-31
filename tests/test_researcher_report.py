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
