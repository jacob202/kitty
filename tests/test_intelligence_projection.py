from gateway import intelligence_projection


def test_projects_three_ranked_notices_without_triggering_magic_generation(monkeypatch):
    monkeypatch.setattr(intelligence_projection.deadline_store, 'list_needs_jacob', lambda: [{
        'id': 12, 'project_id': 7, 'due_date': '2026-09-01', 'obligation': 'Renew registration',
    }])
    monkeypatch.setattr(intelligence_projection.insight_loop, 'list_due', lambda: [{
        'id': 9, 'payload': {'summary': 'Revisit the provider decision', 'category': 'decision'},
    }])
    monkeypatch.setattr(intelligence_projection.life_awareness, 'morning_proactive', lambda: {
        'proactive_suggestions': [
            {'kind': 'life_step', 'priority': 'high', 'text': 'Kitty: ship the next wave', 'why': 'Momentum', 'project_id': 7},
            {'kind': 'upcoming_event', 'priority': 'medium', 'text': 'Next: review at 3 PM'},
        ]
    })
    monkeypatch.setattr(intelligence_projection.magic_kitty, 'cached_connections', lambda: [{
        'insight_id': 'magic-1', 'kind': 'suggestion', 'title': 'Two projects overlap',
        'detail': 'Reuse the same artifact flow.', 'source': 'Kitty, Research', 'confidence': 0.91,
    }])

    projection = intelligence_projection.build_projection(limit=3)

    assert [item['source'] for item in projection['items']] == ['deadline', 'insight', 'magic']
    assert projection['items'][0]['destination'] == 'projects'
    assert projection['items'][0]['project_id'] == 7
    assert projection['items'][1]['prompt'].startswith('Help me act on this returned insight:')
    assert projection['counts']['total_candidates'] == 5
    assert projection['counts']['shown'] == 3


def test_source_failure_degrades_only_that_source(monkeypatch):
    monkeypatch.setattr(intelligence_projection.deadline_store, 'list_needs_jacob', lambda: [])
    monkeypatch.setattr(intelligence_projection.insight_loop, 'list_due', lambda: [])
    monkeypatch.setattr(intelligence_projection.life_awareness, 'morning_proactive', lambda: (_ for _ in ()).throw(RuntimeError('calendar unavailable')))
    monkeypatch.setattr(intelligence_projection.magic_kitty, 'cached_connections', lambda: [])

    projection = intelligence_projection.build_projection(limit=3)

    assert projection['items'] == []
    assert projection['sources']['life']['state'] == 'unavailable'
    assert 'calendar unavailable' in projection['sources']['life']['reason']
    assert projection['sources']['deadline']['state'] == 'available'


def test_due_insight_reads_persisted_summary_schema(monkeypatch):
    monkeypatch.setattr(intelligence_projection.deadline_store, 'list_needs_jacob', lambda: [])
    monkeypatch.setattr(intelligence_projection.insight_loop, 'list_due', lambda: [{
        'id': 9, 'payload': {'summary': 'Use the production summary', 'category': 'decision'},
    }])
    monkeypatch.setattr(intelligence_projection.magic_kitty, 'cached_connections', lambda: [])
    monkeypatch.setattr(intelligence_projection.life_awareness, 'invalidate_proactive_cache', lambda: None, raising=False)
    monkeypatch.setattr(intelligence_projection.life_awareness, 'morning_proactive', lambda: {'proactive_suggestions': []})
    projection = intelligence_projection.build_projection(limit=3)
    assert projection['items'][0]['title'] == 'Use the production summary'
    assert 'Use the production summary' in projection['items'][0]['prompt']


def test_deadline_ties_preserve_source_due_date_order(monkeypatch):
    monkeypatch.setattr(intelligence_projection.deadline_store, 'list_needs_jacob', lambda: [
        {'id': 99, 'due_date': '2026-09-01', 'obligation': 'Soonest'},
        {'id': 1, 'due_date': '2026-09-02', 'obligation': 'Later'},
        {'id': 2, 'due_date': '2026-09-03', 'obligation': 'Latest'},
    ])
    monkeypatch.setattr(intelligence_projection.insight_loop, 'list_due', lambda: [])
    monkeypatch.setattr(intelligence_projection.magic_kitty, 'cached_connections', lambda: [])
    monkeypatch.setattr(intelligence_projection.life_awareness, 'invalidate_proactive_cache', lambda: None, raising=False)
    monkeypatch.setattr(intelligence_projection.life_awareness, 'morning_proactive', lambda: {'proactive_suggestions': []})
    projection = intelligence_projection.build_projection(limit=3)
    assert [item['title'] for item in projection['items']] == ['Soonest', 'Later', 'Latest']


def test_life_projection_refreshes_proactive_cache_before_read(monkeypatch):
    calls = []
    monkeypatch.setattr(intelligence_projection.deadline_store, 'list_needs_jacob', lambda: [])
    monkeypatch.setattr(intelligence_projection.insight_loop, 'list_due', lambda: [])
    monkeypatch.setattr(intelligence_projection.magic_kitty, 'cached_connections', lambda: [])
    monkeypatch.setattr(intelligence_projection.life_awareness, 'invalidate_proactive_cache', lambda: calls.append('invalidate'), raising=False)
    monkeypatch.setattr(intelligence_projection.life_awareness, 'morning_proactive', lambda: calls.append('read') or {'proactive_suggestions': []})
    intelligence_projection.build_projection(limit=3)
    assert calls == ['invalidate', 'read']


def test_explicit_refresh_can_force_generated_connection_into_limited_projection(monkeypatch):
    monkeypatch.setattr(intelligence_projection.deadline_store, 'list_needs_jacob', lambda: [
        {'id': 1, 'due_date': '2026-09-01', 'obligation': 'A'},
        {'id': 2, 'due_date': '2026-09-02', 'obligation': 'B'},
        {'id': 3, 'due_date': '2026-09-03', 'obligation': 'C'},
    ])
    monkeypatch.setattr(intelligence_projection.insight_loop, 'list_due', lambda: [])
    monkeypatch.setattr(intelligence_projection.magic_kitty, 'cached_connections', lambda: [{
        'insight_id': 'magic-new', 'title': 'Generated connection', 'detail': 'Useful overlap', 'confidence': 0.9,
    }])
    monkeypatch.setattr(intelligence_projection.life_awareness, 'invalidate_proactive_cache', lambda: None, raising=False)
    monkeypatch.setattr(intelligence_projection.life_awareness, 'morning_proactive', lambda: {'proactive_suggestions': []})
    projection = intelligence_projection.build_projection(limit=3, ensure_source='magic')
    assert len(projection['items']) == 3
    assert any(item['source'] == 'magic' for item in projection['items'])
