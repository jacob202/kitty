"""Tests for the /integrations routes — messaging, plugins, MCP, sync, ops."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes import integrations as integrations_route


@pytest.fixture
def client(monkeypatch):
    # iMessage — default to unavailable so tests don't need macOS.
    monkeypatch.setattr("gateway.imessage.is_available", lambda: False)
    monkeypatch.setattr("gateway.imessage.send", lambda r, m: True)
    monkeypatch.setattr("gateway.imessage.read_recent", lambda limit=10: [])

    # Telegram
    monkeypatch.setattr("gateway.telegram_bot.is_configured", lambda: True)

    # Plugins
    monkeypatch.setattr("gateway.plugin_registry.list_plugins", lambda: [])
    monkeypatch.setattr(
        "gateway.storage_router.enable_plugin",
        lambda name: name == "test-plugin",
    )
    monkeypatch.setattr(
        "gateway.storage_router.disable_plugin",
        lambda name: name == "test-plugin",
    )

    # MCP
    monkeypatch.setattr("gateway.mcp_tool_bridge.list_servers", lambda: [])
    monkeypatch.setattr("gateway.mcp_tool_bridge.get_tool_schema_for_llm", lambda: [])

    # Sync
    monkeypatch.setattr(
        "gateway.storage_sync.export_all",
        lambda: {"memories": [], "todos": []},
    )
    monkeypatch.setattr(
        "gateway.storage_sync.import_all",
        lambda body: {"memories": 0, "todos": 0},
    )

    # Nudge
    monkeypatch.setattr("gateway.nudge.get_pending", lambda: [])
    monkeypatch.setattr("gateway.nudge.dismiss", lambda nudge_id: None)

    # Health & patterns
    monkeypatch.setattr(
        "gateway.health_parser.get_weekly_summary",
        lambda: {"total": 5, "trend": "up"},
    )
    monkeypatch.setattr("gateway.patterns.weekly", lambda: {"week": 29, "entries": []})
    monkeypatch.setattr("gateway.patterns.annual_review", lambda: {"year": 2026, "highlights": []})

    # Weather
    monkeypatch.setattr("gateway.weather.get_weather", lambda: {"temp": 22, "condition": "clear"})

    # Verifier — route awaits this, so it must be async.
    async def _mock_verify(target_dir, test_path=None):
        return {"passed": True}
    monkeypatch.setattr("gateway.verifier.verify", _mock_verify)

    # Eval — both are awaited.
    async def _mock_run_smoke():
        return {"passed": True, "results": []}
    async def _mock_run_and_compare():
        return {"changes": [], "regressions": []}
    monkeypatch.setattr("gateway.eval_runner.run_smoke", _mock_run_smoke)
    monkeypatch.setattr("gateway.eval_runner.run_and_compare", _mock_run_and_compare)

    app = FastAPI()
    app.include_router(integrations_route.router)
    return TestClient(app)


class TestIMessage:
    def test_send_route_is_removed(self, client, monkeypatch):
        """AUTH-003 (RC-02): POST /imessage/send called gateway.imessage.send()
        directly, bypassing the action queue entirely — no tier check, no
        grant evaluation, no audit trail, and nothing in the tier file (a
        signed-off policy set) authorizes an "imessage.send" kind. Proved
        unreachable before deleting: no frontend caller, no tool_server
        registration, no other backend reference (gateway.push calls
        gateway.imessage.send directly, not this HTTP route)."""
        monkeypatch.setattr("gateway.imessage.is_available", lambda: True)
        r = client.post("/imessage/send", json={"recipient": "me", "message": "hi"})
        assert r.status_code == 404

    def test_recent_unavailable_returns_available_false(self, client):
        r = client.get("/imessage/recent")
        assert r.status_code == 200
        body = r.json()
        assert body["available"] is False
        assert body["messages"] == []


class TestTelegram:
    def test_status(self, client):
        r = client.get("/telegram/status")
        assert r.status_code == 200
        assert r.json()["configured"] is True


class TestPlugins:
    def test_list(self, client):
        r = client.get("/plugins")
        assert r.status_code == 200
        assert "plugins" in r.json()

    def test_enable_known(self, client):
        r = client.post("/plugin/test-plugin/enable")
        assert r.status_code == 200
        assert r.json()["enabled"] is True

    def test_enable_unknown_returns_404(self, client):
        r = client.post("/plugin/ghost/enable")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()

    def test_disable_known(self, client):
        r = client.post("/plugin/test-plugin/disable")
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    def test_disable_unknown_returns_404(self, client):
        r = client.post("/plugin/ghost/disable")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()


class TestMCP:
    def test_servers(self, client):
        r = client.get("/mcp/servers")
        assert r.status_code == 200
        assert "servers" in r.json()

    def test_tools(self, client):
        r = client.get("/mcp/tools")
        assert r.status_code == 200
        assert "tools" in r.json()


class TestSync:
    def test_export(self, client):
        r = client.get("/sync/export")
        assert r.status_code == 200
        body = r.json()
        assert "memories" in body
        assert "todos" in body

    def test_import(self, client):
        r = client.post("/sync/import", json={"memories": [], "todos": []})
        assert r.status_code == 200
        assert "imported" in r.json()


class TestDeploy:
    def test_deploy_route_is_removed(self, client):
        """AUTH-004 (RC-02): POST /deploy took an unvalidated target_dir path
        straight from the request body and passed it to gateway.deploy.deploy(),
        which writes a Dockerfile into that directory — an arbitrary-path
        filesystem write with no tier check, grant evaluation, or audit trail.
        Proved unreachable before deleting: no frontend caller, no tool_server
        registration, no other backend reference to gateway.deploy or this
        route."""
        r = client.post("/deploy", json={"target_dir": "/tmp/test", "platform": "docker"})
        assert r.status_code == 404


class TestNudge:
    def test_list(self, client):
        r = client.get("/nudges")
        assert r.status_code == 200
        assert "nudges" in r.json()

    def test_dismiss(self, client):
        r = client.post("/nudge/test-nudge/dismiss")
        assert r.status_code == 200
        assert r.json()["dismissed"] is True


class TestHealthPatterns:
    def test_health_weekly(self, client):
        r = client.get("/health/weekly")
        assert r.status_code == 200
        assert r.json()["total"] == 5

    def test_patterns_weekly(self, client):
        r = client.get("/patterns/weekly")
        assert r.status_code == 200
        assert "week" in r.json()

    def test_patterns_annual(self, client):
        r = client.get("/patterns/annual")
        assert r.status_code == 200
        assert "year" in r.json()


class TestWeather:
    def test_happy_path(self, client):
        r = client.get("/weather")
        assert r.status_code == 200
        body = r.json()
        assert body["temp"] == 22
        assert body["condition"] == "clear"



class TestVerify:
    def test_happy_path(self, client):
        r = client.post("/verify", json={"target_dir": "/tmp/test"})
        assert r.status_code == 200
        assert r.json()["passed"] is True


class TestEval:
    def test_run(self, client):
        r = client.post("/eval/run")
        assert r.status_code == 200
        assert r.json()["passed"] is True

    def test_compare(self, client):
        r = client.get("/eval/compare")
        assert r.status_code == 200
        assert "changes" in r.json()
