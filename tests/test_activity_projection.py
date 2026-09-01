from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from gateway import activity_projection
from gateway.app import app


def test_activity_projection_normalizes_existing_authorities():
    with (
        patch('gateway.action_queue.list_actions', return_value=[{
            'id': 7, 'title': 'Approve calendar event', 'preview': 'Tomorrow at 10',
            'status': 'proposed', 'created_at': 40.0,
        }]),
        patch('gateway.automation_runs.list_runs', return_value=[{
            'id': 'arun_1', 'automation_id': 'morning', 'action': 'brief.send',
            'status': 'running', 'started_at': 30.0, 'error': None,
        }]),
        patch('gateway.agent_runner.list_agents', return_value=[{
            'session_id': 12, 'goal': 'Compare the two implementations',
            'status': 'completed', 'created_at': 10.0, 'updated_at': 20.0,
        }]),
        patch('gateway.builder_status.build_control_plane_summary', return_value={
            'initiatives': [{
                'initiative_id': 'kitty-polish', 'title': 'Kitty polish',
                'state': 'paused', 'pause_reason': 'needs product decision',
                'updated_at': 35.0, 'packet_count': 4,
            }],
            'queue': {},
        }),
    ):
        response = TestClient(app).get('/activity?limit=20')

    assert response.status_code == 200
    body = response.json()
    assert body['counts'] == {'total': 4, 'waiting': 2, 'running': 1, 'failed': 0, 'completed': 1}
    assert [item['source'] for item in body['items']] == ['action', 'builder', 'automation', 'agent']
    assert body['items'][0]['state'] == 'waiting'
    assert body['items'][0]['destination'] == 'home'
    assert body['items'][1]['destination'] == 'work'
    assert body['items'][2]['destination'] == 'automations'
    assert body['items'][3]['destination'] == 'agent-sessions'
    assert all(source['state'] == 'available' for source in body['sources'].values())


def test_activity_projection_is_partial_when_one_authority_is_unavailable():
    with (
        patch('gateway.action_queue.list_actions', side_effect=OSError('actions db unavailable')),
        patch('gateway.automation_runs.list_runs', return_value=[]),
        patch('gateway.agent_runner.list_agents', return_value=[]),
        patch('gateway.builder_status.build_control_plane_summary', return_value={'initiatives': [], 'queue': {}}),
    ):
        response = TestClient(app).get('/activity')

    assert response.status_code == 200
    body = response.json()
    assert body['items'] == []
    assert body['sources']['actions']['state'] == 'unavailable'
    assert 'actions db unavailable' in body['sources']['actions']['reason']
    assert body['sources']['builder']['state'] == 'available'


def test_activity_projection_preserves_attention_truth_and_real_builder_timestamps():
    recent_actions = [
        {'id': 100 + i, 'title': f'recent {i}', 'preview': None, 'status': 'rejected', 'created_at': float(100 + i)}
        for i in range(30)
    ]
    old_unknown = {
        'id': 1, 'title': 'Calendar outcome needs review', 'preview': 'Created event?',
        'status': 'unknown', 'result': 'gateway restarted mid-execution; outcome unknown', 'created_at': 1.0,
    }
    old_approved = {
        'id': 2, 'title': 'Approved but not started', 'preview': 'Ready to run',
        'status': 'approved', 'result': None, 'created_at': 2.0,
    }

    def list_actions(status=None, limit=30):
        if status == 'unknown':
            return [old_unknown]
        if status == 'approved':
            return [old_approved]
        if status in {'proposed', 'failed', 'outcome_unknown'}:
            return []
        return recent_actions

    recent_runs = [
        {'id': f'new-{i}', 'automation_id': 'daily', 'action': 'brief.send', 'status': 'completed', 'started_at': float(200 + i), 'completed_at': float(200 + i), 'error': None}
        for i in range(30)
    ]
    old_failure = {'id': 'old-fail', 'automation_id': 'daily', 'action': 'brief.send', 'status': 'failed', 'started_at': 3.0, 'completed_at': 4.0, 'error': 'provider unavailable'}

    def list_runs(*, statuses=None, limit=30, **_kwargs):
        if statuses:
            return [old_failure] if 'failed' in statuses else []
        return recent_runs

    with (
        patch('gateway.action_queue.list_actions', side_effect=list_actions),
        patch('gateway.automation_runs.list_runs', side_effect=list_runs),
        patch('gateway.agent_runner.list_agents', return_value=[{
            'session_id': 9, 'goal': 'Stopped on request', 'status': 'cancelled',
            'created_at': 5.0, 'updated_at': 6.0,
        }]),
        patch('gateway.builder_status.build_control_plane_summary', return_value={
            'initiatives': [{
                'initiative_id': 'old-build', 'title': 'Old build', 'state': 'paused',
                'pause_reason': 'superseded', 'superseded_by': 'new-build',
                'updated_at': '2026-08-31 18:00:00', 'packet_count': 4,
            }], 'queue': {},
        }),
    ):
        body = activity_projection.build_activity_projection(limit=4)

    by_id = {item['id']: item for item in body['items']}
    assert by_id['action:1']['state'] == 'failed'
    assert 'outcome unknown' in by_id['action:1']['detail']
    assert by_id['action:2']['state'] == 'waiting'
    assert by_id['automation:old-fail']['state'] == 'failed'
    assert body['counts']['failed'] >= 2
    assert body['counts']['waiting'] >= 1
    assert body['counts']['completed'] >= 31


def test_activity_projection_cancelled_agents_and_superseded_builder_are_not_attention():
    with (
        patch('gateway.action_queue.list_actions', return_value=[]),
        patch('gateway.automation_runs.list_runs', return_value=[]),
        patch('gateway.agent_runner.list_agents', return_value=[{
            'session_id': 12, 'goal': 'Stopped by user', 'status': 'cancelled',
            'created_at': 10.0, 'updated_at': 11.0,
        }]),
        patch('gateway.builder_status.build_control_plane_summary', return_value={
            'initiatives': [{
                'initiative_id': 'legacy', 'title': 'Legacy initiative', 'state': 'paused',
                'pause_reason': 'superseded', 'superseded_by': 'current',
                'updated_at': '2026-08-31 18:00:00', 'packet_count': 1,
            }], 'queue': {},
        }),
    ):
        body = activity_projection.build_activity_projection(limit=20)

    states = {item['id']: item['state'] for item in body['items']}
    assert states['agent:12'] == 'completed'
    assert states['builder:legacy'] == 'completed'
    assert body['counts']['waiting'] == 0
    assert body['counts']['failed'] == 0


def test_activity_projection_fetches_unresolved_agents_outside_recent_history():
    recent = [
        {'session_id': 100 + i, 'goal': f'recent {i}', 'status': 'completed', 'created_at': 100 + i, 'updated_at': 100 + i}
        for i in range(30)
    ]
    old_failed = {'session_id': 7, 'goal': 'Old failed agent', 'status': 'failed', 'created_at': 1.0, 'updated_at': 2.0}

    def list_agents(limit=30, *, statuses=None):
        return [old_failed] if statuses else recent

    with (
        patch('gateway.action_queue.list_actions', return_value=[]),
        patch('gateway.automation_runs.list_runs', return_value=[]),
        patch('gateway.agent_runner.list_agents', side_effect=list_agents),
        patch('gateway.builder_status.build_control_plane_summary', return_value={'initiatives': [], 'queue': {}}),
    ):
        body = activity_projection.build_activity_projection(limit=4)

    assert body['items'][0]['id'] == 'agent:7'
    assert body['items'][0]['state'] == 'failed'
    assert body['items'][0]['destination'] == 'agent-sessions'
    assert body['counts']['failed'] == 1


def test_activity_projection_does_not_hide_programming_errors_as_partial_success():
    with (
        patch('gateway.action_queue.list_actions', side_effect=ValueError('bad action shape')),
        patch('gateway.automation_runs.list_runs', return_value=[]),
        patch('gateway.agent_runner.list_agents', return_value=[]),
        patch('gateway.builder_status.build_control_plane_summary', return_value={'initiatives': [], 'queue': {}}),
    ):
        with pytest.raises(ValueError, match='bad action shape'):
            activity_projection.build_activity_projection()


def test_builder_active_with_only_queued_packets_is_waiting_not_running():
    counts = {
        'total': 1, 'queued': 1, 'claimed': 0, 'running': 0, 'blocked': 0,
        'pr_opened': 0, 'awaiting_review': 0, 'done': 0, 'failed': 0,
        'cancelled': 0, 'exhausted': 0,
    }
    with patch('gateway.builder_status.build_control_plane_summary', return_value={
        'initiatives': [{
            'initiative_id': 'queued-build', 'title': 'Queued build', 'state': 'active',
            'pause_reason': None, 'superseded_by': None, 'updated_at': 7.0,
            'packet_count': 1, 'counts': counts,
        }],
        'queue': {'queued': 1, 'running': 0},
    }):
        item = activity_projection._builder_items()[0]

    assert item['state'] == 'waiting'


def test_builder_active_with_claimed_or_running_packet_is_in_motion():
    counts = {
        'total': 1, 'queued': 0, 'claimed': 1, 'running': 0, 'blocked': 0,
        'pr_opened': 0, 'awaiting_review': 0, 'done': 0, 'failed': 0,
        'cancelled': 0, 'exhausted': 0,
    }
    with patch('gateway.builder_status.build_control_plane_summary', return_value={
        'initiatives': [{
            'initiative_id': 'claimed-build', 'title': 'Claimed build', 'state': 'active',
            'pause_reason': None, 'superseded_by': None, 'updated_at': 8.0,
            'packet_count': 1, 'counts': counts,
        }],
        'queue': {'queued': 0, 'claimed': 1},
    }):
        item = activity_projection._builder_items()[0]

    assert item['state'] == 'running'


def test_active_builder_with_only_queued_packets_is_waiting_not_running():
    with (
        patch('gateway.action_queue.list_actions', return_value=[]),
        patch('gateway.automation_runs.list_runs', return_value=[]),
        patch('gateway.agent_runner.list_agents', return_value=[]),
        patch('gateway.builder_status.build_control_plane_summary', return_value={
            'initiatives': [{
                'initiative_id': 'queued-build', 'title': 'Queued build', 'state': 'active',
                'pause_reason': None, 'superseded_by': None, 'updated_at': 10.0,
                'packet_count': 1,
                'counts': {
                    'total': 1, 'queued': 1, 'claimed': 0, 'running': 0, 'blocked': 0,
                    'pr_opened': 0, 'awaiting_review': 0, 'done': 0, 'failed': 0,
                    'cancelled': 0, 'exhausted': 0,
                },
            }],
            'queue': {'total': 1, 'queued': 1, 'claimed': 0, 'running': 0},
        }),
    ):
        body = activity_projection.build_activity_projection(limit=20)

    item = next(item for item in body['items'] if item['id'] == 'builder:queued-build')
    assert item['state'] == 'waiting'
    assert item['raw_state'] == 'queued'
    assert 'queued' in (item['detail'] or '').lower()
