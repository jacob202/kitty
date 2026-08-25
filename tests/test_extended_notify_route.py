"""Tests for the /notify/test route — COR-004 (RC-02).

GET requests must be side-effect-free. `/notify/test` used to be a GET that
sent a real Pushover push notification when configured, so any prefetcher,
link scanner, or browser mid-air request against it could trigger a real
send. It is now POST-only.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes import extended as extended_route


def _client():
    app = FastAPI()
    app.include_router(extended_route.router)
    return TestClient(app)


class TestNotifyTest:
    def test_get_is_no_longer_allowed(self):
        r = _client().get("/notify/test")
        assert r.status_code == 405

    def test_post_not_configured(self, monkeypatch):
        monkeypatch.setattr("gateway.notify.is_configured", lambda: False)
        r = _client().post("/notify/test")
        assert r.status_code == 200
        assert r.json()["configured"] is False

    def test_post_configured_sends(self, monkeypatch):
        monkeypatch.setattr("gateway.notify.is_configured", lambda: True)
        monkeypatch.setattr("gateway.notify.send", lambda message, title="Kitty", url=None: True)
        r = _client().post("/notify/test")
        assert r.status_code == 200
        body = r.json()
        assert body["configured"] is True
        assert body["sent"] is True
