"""
Tests for morning brief route.
"""
import sys, os, pytest, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.api.brief import brief_bp


class TestBriefRoute:
    def test_blueprint_exists(self):
        assert brief_bp is not None
        assert brief_bp.name == 'brief'

    def test_get_brief_response(self):
        # Simulate a request context
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(brief_bp)

        with app.test_client() as client:
            resp = client.get('/api/brief')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert 'brief' in data
            assert 'data' in data

    def test_brief_content(self):
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(brief_bp)

        with app.test_client() as client:
            resp = client.get('/api/brief')
            data = json.loads(resp.data)
            brief_text = data['brief']
            assert 'Today:' in brief_text
            assert 'Active focus:' in brief_text
            assert 'Next concrete action:' in brief_text

    def test_create_app_registers_api_brief(self):
        from web import create_app

        app, _ = create_app()

        with app.test_client() as client:
            resp = client.get('/api/brief')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert 'brief' in data
