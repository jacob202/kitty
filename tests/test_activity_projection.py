from unittest.mock import patch

from fastapi.testclient import TestClient

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
    assert body['items'][3]['destination'] == 'agents'
    assert all(source['state'] == 'available' for source in body['sources'].values())


def test_activity_projection_is_partial_when_one_authority_is_unavailable():
    with (
        patch('gateway.action_queue.list_actions', side_effect=RuntimeError('actions db unavailable')),
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
