from unittest.mock import AsyncMock

import pytest

from gateway import research_execution


@pytest.mark.asyncio
async def test_persisted_research_saves_markdown_artifact(monkeypatch, tmp_path):
    stages = []
    monkeypatch.setattr(research_execution.research_runs, 'update_stage', lambda run_id, **kw: stages.append(kw['stage']) or {'id': run_id})
    monkeypatch.setattr(research_execution.research_runs, 'get_run', lambda run_id: {'id': run_id, 'topic': 'battery chemistry', 'project_id': 7})
    completed = {}
    monkeypatch.setattr(research_execution.research_runs, 'complete_run', lambda run_id, **kw: completed.update(kw) or {'id': run_id, 'status': 'completed', **kw})
    monkeypatch.setattr(research_execution.research_runs, 'fail_run', lambda *a, **k: (_ for _ in ()).throw(AssertionError('must not fail')))
    researcher = AsyncMock()
    async def report(topic, progress=None):
        if progress:
            progress('searching')
            progress('reading', ['https://example.com/a'])
            progress('synthesizing', ['https://example.com/a'])
        return {
            'summary': 'LFP is thermally stable.',
            'sources': ['https://example.com/a'],
            'findings': 'Evidence body',
        }
    researcher.technical_deep_dive_report.side_effect = report
    monkeypatch.setattr(research_execution, 'DeepResearcher', lambda: researcher)
    monkeypatch.setattr(research_execution, 'RESEARCH_OUTPUT_DIR', tmp_path)
    registered = {}
    monkeypatch.setattr(research_execution.artifact_store, 'register_file', lambda path, **kw: registered.update(path=path, **kw) or {'id': 'artifact_r1'})

    await research_execution.run_persisted_research('rrun_1')

    assert stages == ['searching', 'reading', 'synthesizing', 'saving']
    assert registered['kind'] == 'research_report'
    assert registered['media_type'] == 'text/markdown'
    assert registered['project_id'] == 7
    text = registered['path'].read_text()
    assert '# Research: battery chemistry' in text
    assert 'https://example.com/a' in text
    assert 'Evidence body' in text
    assert completed['artifact_id'] == 'artifact_r1'
    assert completed['sources'] == ['https://example.com/a']


@pytest.mark.asyncio
async def test_failure_is_persisted_logged_and_propagated(monkeypatch, caplog):
    monkeypatch.setattr(research_execution.research_runs, 'get_run', lambda run_id: {'id': run_id, 'topic': 'x', 'project_id': None, 'status': 'running'})
    failed = {}
    monkeypatch.setattr(research_execution.research_runs, 'fail_run', lambda run_id, **kw: failed.update(kw) or {'id': run_id})
    researcher = AsyncMock()
    researcher.technical_deep_dive_report.side_effect = RuntimeError('provider offline')
    monkeypatch.setattr(research_execution, 'DeepResearcher', lambda: researcher)
    with pytest.raises(RuntimeError, match='provider offline'):
        await research_execution.run_persisted_research('rrun_fail')
    assert 'provider offline' in failed['error']
    assert any('Research run rrun_fail failed' in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_artifact_and_completion_share_one_transaction(monkeypatch, tmp_path):
    db_file = tmp_path / 'kitty.db'
    monkeypatch.setattr(research_execution.research_runs, 'DB_FILE', db_file)
    monkeypatch.setattr(research_execution.artifact_store, 'ARTIFACTS_DB_FILE', db_file)
    monkeypatch.setattr(research_execution, 'RESEARCH_OUTPUT_DIR', tmp_path / 'reports')
    run = research_execution.research_runs.begin_run(topic='atomic research')
    researcher = AsyncMock()
    researcher.technical_deep_dive_report.return_value = {'summary': 'done', 'sources': [], 'findings': 'evidence'}
    monkeypatch.setattr(research_execution, 'DeepResearcher', lambda: researcher)
    original_complete = research_execution.research_runs.complete_run
    def broken_complete(*args, **kwargs):
        raise RuntimeError('completion write failed')
    monkeypatch.setattr(research_execution.research_runs, 'complete_run', broken_complete)
    with pytest.raises(RuntimeError, match='completion write failed'):
        await research_execution.run_persisted_research(run['id'])
    monkeypatch.setattr(research_execution.research_runs, 'complete_run', original_complete)
    from gateway import db as kitty_db
    with kitty_db.connect(db_file) as conn:
        artifacts = conn.execute("SELECT COUNT(*) FROM artifacts WHERE source_ref = ?", (f"research_run:{run['id']}",)).fetchone()[0]
    assert artifacts == 0
