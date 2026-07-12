"""HTTP-layer contract tests for gateway/routes/integrations.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# --- iMessage endpoints ---


def test_imessage_send_happy_path(client: TestClient) -> None:
    with patch("gateway.imessage.is_available", return_value=True), patch(
        "gateway.imessage.send", return_value=True
    ) as mock_send:
        resp = client.post("/imessage/send", json={"recipient": "Jacob", "message": "hi"})

    assert resp.status_code == 200
    assert resp.json() == {"sent": True}
    mock_send.assert_called_once_with("Jacob", "hi")


def test_imessage_send_unavailable_is_400(client: TestClient) -> None:
    with patch("gateway.imessage.is_available", return_value=False):
        resp = client.post("/imessage/send", json={"recipient": "Jacob", "message": "hi"})

    assert resp.status_code == 400


def test_imessage_send_empty_message_is_422(client: TestClient) -> None:
    resp = client.post("/imessage/send", json={"recipient": "Jacob", "message": ""})

    assert resp.status_code == 422


def test_imessage_recent_happy_path(client: TestClient) -> None:
    messages = [{"from": "Jacob", "text": "hey", "date": "2026-07-12"}]
    with patch("gateway.imessage.is_available", return_value=True), patch(
        "gateway.imessage.read_recent", return_value=messages
    ) as mock_recent:
        resp = client.get("/imessage/recent", params={"limit": 5})

    assert resp.status_code == 200
    assert resp.json() == {"available": True, "messages": messages}
    mock_recent.assert_called_once_with(5)


def test_imessage_recent_unavailable_returns_empty(client: TestClient) -> None:
    with patch("gateway.imessage.is_available", return_value=False):
        resp = client.get("/imessage/recent")

    assert resp.status_code == 200
    assert resp.json() == {"available": False, "messages": []}


# --- Telegram endpoints ---


def test_telegram_status_configured(client: TestClient) -> None:
    with patch("gateway.telegram_bot.is_configured", return_value=True):
        resp = client.get("/telegram/status")

    assert resp.status_code == 200
    assert resp.json() == {"configured": True}


def test_telegram_status_not_configured(client: TestClient) -> None:
    with patch("gateway.telegram_bot.is_configured", return_value=False):
        resp = client.get("/telegram/status")

    assert resp.status_code == 200
    assert resp.json() == {"configured": False}


# --- Plugin endpoints ---


def test_plugins_list_happy_path(client: TestClient) -> None:
    plugins = [{"name": "web", "enabled": True}]
    with patch("gateway.plugin_registry.list_plugins", return_value=plugins):
        resp = client.get("/plugins")

    assert resp.status_code == 200
    assert resp.json() == {"plugins": plugins}


def test_plugins_list_empty(client: TestClient) -> None:
    with patch("gateway.plugin_registry.list_plugins", return_value=[]):
        resp = client.get("/plugins")

    assert resp.status_code == 200
    assert resp.json() == {"plugins": []}


def test_plugin_enable_happy_path(client: TestClient) -> None:
    with patch("gateway.storage_router.enable_plugin", return_value=True) as mock_enable:
        resp = client.post("/plugin/web/enable")

    assert resp.status_code == 200
    assert resp.json() == {"plugin": "web", "enabled": True}
    mock_enable.assert_called_once_with("web")


def test_plugin_enable_not_found_is_404(client: TestClient) -> None:
    with patch("gateway.storage_router.enable_plugin", return_value=False):
        resp = client.post("/plugin/nope/enable")

    assert resp.status_code == 404


def test_plugin_disable_happy_path(client: TestClient) -> None:
    with patch("gateway.storage_router.disable_plugin", return_value=True) as mock_disable:
        resp = client.post("/plugin/web/disable")

    assert resp.status_code == 200
    assert resp.json() == {"plugin": "web", "enabled": False}
    mock_disable.assert_called_once_with("web")


def test_plugin_disable_not_found_is_404(client: TestClient) -> None:
    with patch("gateway.storage_router.disable_plugin", return_value=False):
        resp = client.post("/plugin/nope/disable")

    assert resp.status_code == 404


# --- MCP endpoints ---


def test_mcp_servers_happy_path(client: TestClient) -> None:
    servers = [{"name": "filesystem", "status": "up"}]
    with patch("gateway.mcp_tool_bridge.list_servers", return_value=servers):
        resp = client.get("/mcp/servers")

    assert resp.status_code == 200
    assert resp.json() == {"servers": servers}


def test_mcp_servers_empty(client: TestClient) -> None:
    with patch("gateway.mcp_tool_bridge.list_servers", return_value=[]):
        resp = client.get("/mcp/servers")

    assert resp.status_code == 200
    assert resp.json() == {"servers": []}


def test_mcp_tools_happy_path(client: TestClient) -> None:
    tools = [{"name": "read_file", "description": "reads a file"}]
    with patch("gateway.mcp_tool_bridge.get_tool_schema_for_llm", return_value=tools):
        resp = client.get("/mcp/tools")

    assert resp.status_code == 200
    assert resp.json() == {"tools": tools}


def test_mcp_tools_empty(client: TestClient) -> None:
    with patch("gateway.mcp_tool_bridge.get_tool_schema_for_llm", return_value=[]):
        resp = client.get("/mcp/tools")

    assert resp.status_code == 200
    assert resp.json() == {"tools": []}


# --- Sync endpoints ---


def test_sync_export_happy_path(client: TestClient) -> None:
    snapshot = {"memories": [{"text": "hi"}], "journal_entries": [], "todos": []}
    with patch("gateway.storage_sync.export_all", return_value=snapshot):
        resp = client.get("/sync/export")

    assert resp.status_code == 200
    assert resp.json() == snapshot


def test_sync_export_calls_export_all_with_no_args(client: TestClient) -> None:
    with patch("gateway.storage_sync.export_all", return_value={}) as mock_export:
        resp = client.get("/sync/export")

    assert resp.status_code == 200
    mock_export.assert_called_once_with()


def test_sync_import_happy_path(client: TestClient) -> None:
    payload = {"memories": [{"text": "hi"}]}
    with patch("gateway.storage_sync.import_all", return_value={"memories": 1}) as mock_import:
        resp = client.post("/sync/import", json=payload)

    assert resp.status_code == 200
    assert resp.json() == {"imported": {"memories": 1}}
    mock_import.assert_called_once_with(payload)


def test_sync_import_empty_body(client: TestClient) -> None:
    with patch("gateway.storage_sync.import_all", return_value={}) as mock_import:
        resp = client.post("/sync/import", json={})

    assert resp.status_code == 200
    assert resp.json() == {"imported": {}}
    mock_import.assert_called_once_with({})


# --- Deploy endpoint ---


def test_deploy_happy_path(client: TestClient) -> None:
    result = {"ok": True, "url": "https://example.com"}
    with patch("gateway.deploy.deploy", new=AsyncMock(return_value=result)) as mock_deploy:
        resp = client.post("/deploy", json={"target_dir": "/tmp/site", "platform": "github_pages"})

    assert resp.status_code == 200
    assert resp.json() == result
    mock_deploy.assert_awaited_once_with("/tmp/site", "github_pages", None)


def test_deploy_defaults_platform_to_docker(client: TestClient) -> None:
    with patch(
        "gateway.deploy.deploy", new=AsyncMock(return_value={"ok": True})
    ) as mock_deploy:
        resp = client.post("/deploy", json={"target_dir": "/tmp/site"})

    assert resp.status_code == 200
    mock_deploy.assert_awaited_once_with("/tmp/site", "docker", None)


def test_deploy_missing_target_dir_is_422(client: TestClient) -> None:
    resp = client.post("/deploy", json={"platform": "docker"})

    assert resp.status_code == 422


# --- Nudge endpoints ---


def test_nudge_list_happy_path(client: TestClient) -> None:
    nudges = [{"id": "n1", "text": "check the deploy"}]
    with patch("gateway.nudge.get_pending", return_value=nudges):
        resp = client.get("/nudges")

    assert resp.status_code == 200
    assert resp.json() == {"nudges": nudges}


def test_nudge_list_empty(client: TestClient) -> None:
    with patch("gateway.nudge.get_pending", return_value=[]):
        resp = client.get("/nudges")

    assert resp.status_code == 200
    assert resp.json() == {"nudges": []}


def test_nudge_dismiss_happy_path(client: TestClient) -> None:
    with patch("gateway.nudge.dismiss", return_value=True) as mock_dismiss:
        resp = client.post("/nudge/n1/dismiss")

    assert resp.status_code == 200
    assert resp.json() == {"dismissed": True}
    mock_dismiss.assert_called_once_with("n1")


def test_nudge_dismiss_reports_true_even_when_store_returns_false(client: TestClient) -> None:
    # The route doesn't branch on dismiss()'s return value — this pins that contract.
    with patch("gateway.nudge.dismiss", return_value=False):
        resp = client.post("/nudge/unknown/dismiss")

    assert resp.status_code == 200
    assert resp.json() == {"dismissed": True}


# --- Health & Patterns endpoints ---


def test_health_weekly_happy_path(client: TestClient) -> None:
    summary = {"steps_avg": 8500, "sleep_avg_hours": 7.2}
    with patch("gateway.health_parser.get_weekly_summary", return_value=summary):
        resp = client.get("/health/weekly")

    assert resp.status_code == 200
    assert resp.json() == summary


def test_health_weekly_empty_summary(client: TestClient) -> None:
    with patch("gateway.health_parser.get_weekly_summary", return_value={}):
        resp = client.get("/health/weekly")

    assert resp.status_code == 200
    assert resp.json() == {}


def test_patterns_weekly_happy_path(client: TestClient) -> None:
    summary = {"themes": ["deep work mornings"]}
    with patch("gateway.patterns.weekly", return_value=summary):
        resp = client.get("/patterns/weekly")

    assert resp.status_code == 200
    assert resp.json() == summary


def test_patterns_weekly_empty(client: TestClient) -> None:
    with patch("gateway.patterns.weekly", return_value={}):
        resp = client.get("/patterns/weekly")

    assert resp.status_code == 200
    assert resp.json() == {}


def test_patterns_annual_happy_path(client: TestClient) -> None:
    summary = {"year": 2026, "highlights": []}
    with patch("gateway.patterns.annual_review", return_value=summary):
        resp = client.get("/patterns/annual")

    assert resp.status_code == 200
    assert resp.json() == summary


def test_patterns_annual_empty(client: TestClient) -> None:
    with patch("gateway.patterns.annual_review", return_value={}):
        resp = client.get("/patterns/annual")

    assert resp.status_code == 200
    assert resp.json() == {}


# --- Weather endpoint ---


def test_weather_happy_path(client: TestClient) -> None:
    fake = {"temp_c": -18, "condition": "snow"}
    with patch("gateway.weather.get_weather", return_value=fake):
        resp = client.get("/weather")

    assert resp.status_code == 200
    assert resp.json() == fake


def test_weather_unavailable_falls_back_to_error_shape(client: TestClient) -> None:
    with patch("gateway.weather.get_weather", return_value=None):
        resp = client.get("/weather")

    assert resp.status_code == 200
    assert resp.json() == {"error": "weather unavailable"}


# --- Build endpoints ---


def test_build_start_happy_path(client: TestClient) -> None:
    with patch("gateway.builder.start", return_value="build-123") as mock_start:
        resp = client.post("/build/start", json={"goal": "add a health endpoint"})

    assert resp.status_code == 200
    assert resp.json() == {"build_id": "build-123", "status": "started"}
    mock_start.assert_called_once_with(goal="add a health endpoint", target_dir="", auto_approve=False)


def test_build_start_passes_optional_fields_through(client: TestClient) -> None:
    with patch("gateway.builder.start", return_value="build-9") as mock_start:
        resp = client.post(
            "/build/start",
            json={"goal": "ship it", "target_dir": "/repo", "auto_approve": True},
        )

    assert resp.status_code == 200
    mock_start.assert_called_once_with(goal="ship it", target_dir="/repo", auto_approve=True)


def test_build_start_empty_goal_is_422(client: TestClient) -> None:
    resp = client.post("/build/start", json={"goal": ""})

    assert resp.status_code == 422


def test_build_status_happy_path(client: TestClient) -> None:
    fake_status = {"id": "build-1", "status": "running", "current_stage": "implement"}
    with patch("gateway.builder.status", return_value=fake_status):
        resp = client.get("/build/build-1")

    assert resp.status_code == 200
    assert resp.json() == fake_status


def test_build_status_not_found_is_404(client: TestClient) -> None:
    with patch("gateway.builder.status", return_value={"id": "nope", "status": "not_found"}):
        resp = client.get("/build/nope")

    assert resp.status_code == 404


def test_build_approve_happy_path(client: TestClient) -> None:
    with patch("gateway.builder.approve_stage", return_value=True) as mock_approve:
        resp = client.post("/build/build-1/approve/implement")

    assert resp.status_code == 200
    assert resp.json() == {"build_id": "build-1", "stage": "implement", "approved": True}
    mock_approve.assert_called_once_with("build-1", "implement")


def test_build_approve_not_awaiting_approval_is_400(client: TestClient) -> None:
    with patch("gateway.builder.approve_stage", return_value=False):
        resp = client.post("/build/build-1/approve/commit")

    assert resp.status_code == 400


def test_build_list_default_limit(client: TestClient) -> None:
    with patch("gateway.builder.list_builds", return_value=[]) as mock_list:
        resp = client.get("/builds")

    assert resp.status_code == 200
    assert resp.json() == {"builds": []}
    mock_list.assert_called_once_with(limit=10)


def test_build_list_custom_limit(client: TestClient) -> None:
    builds = [{"id": "build-1", "status": "done"}]
    with patch("gateway.builder.list_builds", return_value=builds) as mock_list:
        resp = client.get("/builds", params={"limit": 3})

    assert resp.status_code == 200
    assert resp.json() == {"builds": builds}
    mock_list.assert_called_once_with(limit=3)


# --- Verifier endpoint ---


def test_verify_run_happy_path(client: TestClient) -> None:
    fake_result = {"ok": True, "passed": 12, "failed": 0}
    with patch(
        "gateway.verifier.verify", new=AsyncMock(return_value=fake_result)
    ) as mock_verify:
        resp = client.post("/verify", json={"target_dir": "/repo", "test_path": "tests/"})

    assert resp.status_code == 200
    assert resp.json() == fake_result
    mock_verify.assert_awaited_once_with("/repo", "tests/")


def test_verify_run_defaults_test_path_to_none(client: TestClient) -> None:
    with patch(
        "gateway.verifier.verify", new=AsyncMock(return_value={"ok": True})
    ) as mock_verify:
        resp = client.post("/verify", json={"target_dir": "/repo"})

    assert resp.status_code == 200
    mock_verify.assert_awaited_once_with("/repo", None)


def test_verify_run_missing_target_dir_is_422(client: TestClient) -> None:
    resp = client.post("/verify", json={})

    assert resp.status_code == 422


# --- Eval endpoints ---


def test_eval_run_happy_path(client: TestClient) -> None:
    fake_result = {"ok": True, "duration_s": 4.2}
    with patch("gateway.eval_runner.run_smoke", new=AsyncMock(return_value=fake_result)):
        resp = client.post("/eval/run")

    assert resp.status_code == 200
    assert resp.json() == fake_result


def test_eval_run_ignores_unexpected_body(client: TestClient) -> None:
    with patch("gateway.eval_runner.run_smoke", new=AsyncMock(return_value={"ok": True})):
        resp = client.post("/eval/run", json={"unexpected": "field"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_eval_compare_happy_path(client: TestClient) -> None:
    fake_result = {"before": {}, "after": {}, "delta": {}}
    with patch(
        "gateway.eval_runner.run_and_compare", new=AsyncMock(return_value=fake_result)
    ) as mock_compare:
        resp = client.get("/eval/compare")

    assert resp.status_code == 200
    assert resp.json() == fake_result
    mock_compare.assert_awaited_once_with()


def test_eval_compare_surfaces_empty_result(client: TestClient) -> None:
    with patch("gateway.eval_runner.run_and_compare", new=AsyncMock(return_value={})):
        resp = client.get("/eval/compare")

    assert resp.status_code == 200
    assert resp.json() == {}
