import json
from pathlib import Path

from src.api.dispatcher import dispatch


class _DummySupervisor:
    def __init__(self):
        self.config = {}
        self.specialists = []
        self.tools = []
        self.session_cost = 0.0
        self._active_mode = None


def test_help_hides_dead_and_internal_commands(capsys):
    dispatch("/help", sup=_DummySupervisor())

    output = capsys.readouterr().out

    assert "/brief" in output
    assert "/deepsearch" in output
    assert "/remember <fact>" in output
    assert "/memories" not in output
    assert "/ingest [path]" not in output
    assert "/process-pdf" not in output


def test_create_app_hides_swarm_routes_by_default(monkeypatch):
    import web as web_module

    class DummyOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("src.space_kitty.core_orchestrator.CoreOrchestrator", DummyOrchestrator)

    app, _ = web_module.create_app()
    client = app.test_client()

    response = client.get("/api/swarm/roster")

    assert response.status_code == 404


def test_capabilities_api_reports_repo_mcp_and_swarm_status(monkeypatch):
    import web as web_module

    class DummyOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("src.space_kitty.core_orchestrator.CoreOrchestrator", DummyOrchestrator)

    app, _ = web_module.create_app()
    client = app.test_client()

    response = client.get("/api/capabilities")

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["commands"]["visible_help_count"] > 0
    assert payload["api"]["swarm"]["enabled"] is False
    assert payload["api"]["swarm"]["tier"] == "disabled"
    assert payload["api"]["scorecard"]["enabled"] is False
    assert payload["api"]["api_health"]["enabled"] is False
    assert payload["mcp"]["filesystem"]["tier"] == "core"
    assert payload["mcp"]["memory"]["status"] == "keep"
    assert payload["mcp"]["sequential-thinking"]["status"] == "investigate"


def test_internal_routes_are_hidden_by_default(monkeypatch):
    import web as web_module

    class DummyOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("src.space_kitty.core_orchestrator.CoreOrchestrator", DummyOrchestrator)

    app, _ = web_module.create_app()
    client = app.test_client()

    for path, method in (
        ("/api/settings/update", "post"),
        ("/api/eval/scorecard", "get"),
        ("/api/health", "get"),
        ("/api/diagnostics", "get"),
        ("/api/resilience/status", "get"),
        ("/api/settings/profiles", "get"),
        ("/api/settings/profiles/active", "get"),
    ):
        response = getattr(client, method)(path, json={"primary": "test/model"} if method == "post" else None)
        assert response.status_code == 404, (path, response.status_code, response.get_data(as_text=True))


def test_internal_routes_can_be_enabled_for_dev_mode(monkeypatch, tmp_path):
    import src.api.system_routes as system_routes
    import web as web_module

    class DummyOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("src.space_kitty.core_orchestrator.CoreOrchestrator", DummyOrchestrator)
    monkeypatch.setattr(system_routes, "Path", lambda value: tmp_path / Path(value))
    monkeypatch.setenv("KITTY_ENABLE_INTERNAL_API", "1")
    monkeypatch.setattr(system_routes, "_get_cached_health", lambda: {"status": "healthy", "timestamp": 123})

    app, _ = web_module.create_app()
    client = app.test_client()

    response = client.get("/api/eval/scorecard")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["status"] == "unavailable"
    assert "scorecard" in payload["error"].lower()

    health_response = client.get("/api/health")
    assert health_response.status_code == 200
    assert health_response.get_json()["status"] == "healthy"
