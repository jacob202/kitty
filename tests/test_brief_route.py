"""
Tests for morning brief route.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.brief import brief_bp


class TestBriefRoute:
    def test_brief_blueprint_json_contract(self):
        from flask import Flask

        app = Flask(__name__)
        app.register_blueprint(brief_bp)

        with app.test_client() as client:
            resp = client.get("/api/brief")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert "brief" in data
            assert "data" in data
            brief_text = data["brief"]
            assert "Today:" in brief_text
            assert "Active focus:" in brief_text
            assert "Next concrete action:" in brief_text

    def test_create_app_registers_api_brief(self):
        from web import create_app

        app, _ = create_app()

        with app.test_client() as client:
            resp = client.get("/api/brief")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert "brief" in data
