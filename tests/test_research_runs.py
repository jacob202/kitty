from gateway import research_runs


def _patch_db(monkeypatch, tmp_path):
    db_file = tmp_path / 'kitty.db'
    monkeypatch.setattr(research_runs, 'DB_FILE', db_file)
    return db_file


def test_run_lifecycle_is_durable_and_structured(monkeypatch, tmp_path):
    _patch_db(monkeypatch, tmp_path)
    run = research_runs.begin_run(topic='battery chemistry', project_id=7, created_at=100.0)

    assert run['status'] == 'running'
    assert run['stage'] == 'queued'
    assert run['project_id'] == 7

    searching = research_runs.update_stage(run['id'], stage='searching', updated_at=101.0)
    assert searching['stage'] == 'searching'

    reading = research_runs.update_stage(
        run['id'], stage='reading', sources=['https://example.com/a'], updated_at=102.0,
    )
    assert reading['sources'] == ['https://example.com/a']

    done = research_runs.complete_run(
        run['id'], summary='Lithium iron phosphate is stable.', artifact_id='artifact_r1',
        sources=['https://example.com/a'], completed_at=110.0,
    )
    assert done['status'] == 'completed'
    assert done['stage'] == 'completed'
    assert done['artifact_id'] == 'artifact_r1'
    assert done['summary'].startswith('Lithium iron')
    assert research_runs.get_run(run['id'])['status'] == 'completed'


def test_previous_process_running_run_reconciles_to_interrupted(monkeypatch, tmp_path):
    _patch_db(monkeypatch, tmp_path)
    run = research_runs.begin_run(topic='stale run', created_at=10.0)
    monkeypatch.setattr(research_runs, 'PROCESS_STARTED_AT', 20.0)

    changed = research_runs.reconcile_interrupted(now=30.0)

    assert changed == 1
    current = research_runs.get_run(run['id'])
    assert current['status'] == 'interrupted'
    assert current['stage'] == 'interrupted'
    assert 'gateway restarted' in current['error']
