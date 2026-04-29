"""
Tests for commands route.
"""
import sys, os, pytest, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.api.commands import commands_bp


class TestCommandsRoute:
    def test_blueprint_exists(self):
        assert commands_bp is not None
        assert commands_bp.name == 'commands'

    def test_stuck_command(self):
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(commands_bp)

        with app.test_client() as client:
            resp = client.post('/api/command',
                                 data=json.dumps({'command': '/stuck'}),
                                 content_type='application/json')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert 'response' in data
            assert 'action' in data
            assert 'next_action' in data['action']

    def test_done_command(self):
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(commands_bp)

        with app.test_client() as client:
            resp = client.post('/api/command',
                                 data=json.dumps({'command': 'done test task'}),
                                 content_type='application/json')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert 'response' in data

    def test_unknown_command(self):
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(commands_bp)

        with app.test_client() as client:
            resp = client.post('/api/command',
                                 data=json.dumps({'command': 'unknown'}),
                                 content_type='application/json')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert 'Unknown command' in data['response']

    def test_create_app_registers_api_command(self):
        from web import create_app

        app, _ = create_app()

        with app.test_client() as client:
            resp = client.post('/api/command',
                               data=json.dumps({'command': '/stuck'}),
                               content_type='application/json')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data['command'] == '/stuck'
