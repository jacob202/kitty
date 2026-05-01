"""
Tests for critical untested routes: POST /brief, POST /chat, GET /api/news,
POST /api/chatbox/start, SSE /stream.
"""
import sys, os, pytest, json
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from web import create_app

@pytest.fixture
def client():
    app, _ = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

class TestCriticalRoutes:
    def test_post_brief(self, client):
        resp = client.post('/brief')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['ok'] is True

    def test_post_chat(self, client):
        resp = client.post('/chat', 
                           data=json.dumps({'message': 'hello'}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['ok'] is True

    def test_chatbox_start(self, client):
        resp = client.post('/api/chatbox/start',
                           data=json.dumps({'topic': 'test'}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert "chatbox unavailable" in data['message']

    def test_get_api_news(self, client):
        resp = client.get("/api/news")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, dict)

    def test_get_api_news_summary(self, client):
        resp = client.get("/api/news/summary")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "domains" in data
        assert "total" in data

    def test_stream_smoke(self, client):
        # Smoke test for SSE endpoint
        resp = client.get('/stream?query=hello')
        assert resp.status_code == 200
        assert resp.mimetype == 'text/event-stream'
