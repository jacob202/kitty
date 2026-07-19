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

    # Deploy — route awaits this, so it must be async.
    async def _mock_deploy(target_dir, platform, config):
        return {"status": "ok"}
    monkeypatch.setattr("gateway.deploy.deploy", _mock_deploy)

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

    # Builder
    monkeypatch.setattr(
        "gateway.builder.start",
        lambda goal, target_dir="", auto_approve=False: "build_001",
    )
    monkeypatch.setattr(
        "gateway.builder.status",
        lambda build_id: {"build_id": build_id, "status": "running"},
    )
    monkeypatch.setattr(
        "gateway.builder.approve_stage",
        lambda build_id, stage: True,
    )
    monkeypatch.setattr(
        "gateway.builder.list_builds",
        lambda limit=10: [],
    )

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
    def test_send_happy_path(self, client, monkeypatch):
        monkeypatch.setattr("gateway.imessage.is_available", lambda: True)
        r = client.post("/imessage/send", json={"recipient": "me", "message": "hi"})
        assert r.status_code == 200
        assert r.json()["sent"] is True

    def test_send_unavailable_returns_400(self, client):
        r = client.post("/imessage/send", json={"recipient": "me", "message": "hi"})
        assert r.status_code == 400
        assert "not available" in r.json()["detail"].lower()

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
    def test_happy_path(self, client):
        r = client.post("/deploy", json={"target_dir": "/tmp/test", "platform": "docker"})
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


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


class TestBuild:
    def test_start(self, client):
        r = client.post("/build/start", json={"goal": "fix tests"})
        assert r.status_code == 200
        body = r.json()
        assert body["build_id"] == "build_001"
        assert body["status"] == "started"

    def test_status(self, client):
        r = client.get("/build/test-build")
        assert r.status_code == 200
        assert r.json()["status"] == "running"

    def test_status_not_found(self, client, monkeypatch):
        monkeypatch.setattr(
            "gateway.builder.status",
            lambda build_id: {"status": "not_found"},
        )
        r = client.get("/build/ghost")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()

    def test_approve(self, client):
        r = client.post("/build/test-build/approve/review")
        assert r.status_code == 200
        body = r.json()
        assert body["approved"] is True

    def test_approve_fails(self, client, monkeypatch):
        monkeypatch.setattr(
            "gateway.builder.approve_stage",
            lambda build_id, stage: False,
        )
        r = client.post("/build/test-build/approve/review")
        assert r.status_code == 400
        assert "not awaiting" in r.json()["detail"].lower()

    def test_list(self, client):
        r = client.get("/builds")
        assert r.status_code == 200
        assert "builds" in r.json()


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
