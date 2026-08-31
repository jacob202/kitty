from gateway import intelligence_projection


def test_projects_three_ranked_notices_without_triggering_magic_generation(monkeypatch):
    monkeypatch.setattr(intelligence_projection.deadline_store, 'list_needs_jacob', lambda: [{
        'id': 12, 'project_id': 7, 'due_date': '2026-09-01', 'obligation': 'Renew registration',
    }])
    monkeypatch.setattr(intelligence_projection.insight_loop, 'list_due', lambda: [{
        'id': 9, 'payload': {'text': 'Revisit the provider decision', 'category': 'decision'},
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
