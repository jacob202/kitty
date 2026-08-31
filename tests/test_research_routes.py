from fastapi import BackgroundTasks

from gateway.routes import research as research_route


def test_start_research_returns_durable_run_and_schedules_worker(monkeypatch):
    monkeypatch.setattr(research_route.research_runs, 'begin_run', lambda **kw: {'id': 'rrun_1', 'topic': kw['topic'], 'project_id': kw.get('project_id'), 'status': 'running', 'stage': 'queued'})
    tasks = BackgroundTasks()

    result = research_route.start_research(research_route.StartResearchRequest(topic='battery chemistry', project_id=7), tasks)

    assert result['run']['id'] == 'rrun_1'
    assert result['run']['stage'] == 'queued'
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].func is research_route.research_execution.run_persisted_research_background


def test_get_research_run_404s_when_missing(monkeypatch):
    monkeypatch.setattr(research_route.research_runs, 'get_run', lambda run_id: None)
    try:
        research_route.get_research_run('missing')
    except Exception as exc:
        assert getattr(exc, 'status_code', None) == 404
    else:
        raise AssertionError('expected 404')
