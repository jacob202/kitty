"""Tests for gateway.monitors — the monitors substrate.

The route layer was slimmed in Phase 3 to a thin wrapper. These
tests pin the substrate: the module delegates to ``web_monitor``
and never returns an in-memory mock.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from gateway import monitors


@pytest.fixture
def isolated_watch_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from gateway import web_monitor

    db = tmp_path / "web_monitors.db"
    monkeypatch.setattr(web_monitor, "MONITOR_DB", db)
    return db


class TestListMonitors:
    def test_empty_initially(self, isolated_watch_db: Path) -> None:
        assert monitors.list_monitors() == []

    def test_returns_watches_after_add(self, isolated_watch_db: Path) -> None:
        from gateway import web_monitor

        with patch.object(web_monitor, "_ensure_polling"):
            web_monitor.add_watch("https://example.com", label="example")
        rows = monitors.list_monitors()
        assert any(r["url"] == "https://example.com" for r in rows)

    def test_surfaces_store_failure(self, isolated_watch_db: Path) -> None:
        from gateway import web_monitor

        with (
            patch.object(
                web_monitor,
                "list_watches",
                side_effect=OSError("monitor database is locked"),
            ),
            pytest.raises(
                monitors.MonitorError,
                match="monitor list failed.*database is locked",
            ) as raised,
        ):
            monitors.list_monitors()

        assert raised.value.details["operation"] == "list"
        assert raised.value.details["exception_type"] == "OSError"

    def test_rejects_malformed_store_response(self, isolated_watch_db: Path) -> None:
        from gateway import web_monitor

        with (
            patch.object(web_monitor, "list_watches", return_value=None),
            pytest.raises(
                monitors.MonitorError,
                match="returned NoneType, expected list",
            ),
        ):
            monitors.list_monitors()


class TestCreateMonitor:
    def test_returns_watch_dict(self, isolated_watch_db: Path) -> None:
        from gateway import web_monitor

        with patch.object(web_monitor, "_ensure_polling"):
            watch = monitors.create_monitor("https://example.com/x", interval_minutes=120)
        assert watch["url"] == "https://example.com/x"
        assert watch["interval"] == 120
        assert watch["enabled"] is True
        assert isinstance(watch["watch_id"], str)
        assert len(watch["watch_id"]) == 8

    def test_validates_url(self, isolated_watch_db: Path) -> None:
        with pytest.raises(ValueError, match="url"):
            monitors.create_monitor("", interval_minutes=60)
        with pytest.raises(ValueError, match="url"):
            monitors.create_monitor(123, interval_minutes=60)  # type: ignore[arg-type]

    def test_validates_interval(self, isolated_watch_db: Path) -> None:
        with pytest.raises(ValueError, match="interval_minutes"):
            monitors.create_monitor("https://example.com", interval_minutes=0)
        with pytest.raises(ValueError, match="interval_minutes"):
            monitors.create_monitor("https://example.com", interval_minutes=-1)

    def test_surfaces_store_failure(self, isolated_watch_db: Path) -> None:
        from gateway import web_monitor

        with (
            patch.object(
                web_monitor,
                "add_watch",
                side_effect=OSError("monitor database is read-only"),
            ),
            pytest.raises(
                monitors.MonitorError,
                match="monitor create failed.*database is read-only",
            ),
        ):
            monitors.create_monitor("https://example.com")

    def test_rejects_invalid_watch_id(self, isolated_watch_db: Path) -> None:
        from gateway import web_monitor

        with (
            patch.object(web_monitor, "add_watch", return_value="   "),
            pytest.raises(
                monitors.MonitorError,
                match="invalid watch id",
            ),
        ):
            monitors.create_monitor("https://example.com")


class TestDeleteMonitor:
    def test_returns_true_for_existing(self, isolated_watch_db: Path) -> None:
        from gateway import web_monitor

        with patch.object(web_monitor, "_ensure_polling"):
            wid = web_monitor.add_watch("https://example.com/del")
        assert monitors.delete_monitor(wid) is True

    def test_returns_false_for_unknown(self, isolated_watch_db: Path) -> None:
        assert monitors.delete_monitor("nope") is False

    def test_validates_id(self, isolated_watch_db: Path) -> None:
        with pytest.raises(ValueError, match="monitor_id"):
            monitors.delete_monitor("")
        with pytest.raises(ValueError, match="monitor_id"):
            monitors.delete_monitor(42)  # type: ignore[arg-type]

    def test_surfaces_store_failure(self, isolated_watch_db: Path) -> None:
        from gateway import web_monitor

        with (
            patch.object(
                web_monitor,
                "remove_watch",
                side_effect=OSError("monitor database is locked"),
            ),
            pytest.raises(
                monitors.MonitorError,
                match="monitor delete failed.*database is locked",
            ) as raised,
        ):
            monitors.delete_monitor("watch-123")

        assert raised.value.details["monitor_id"] == "watch-123"

    def test_rejects_non_boolean_store_response(self, isolated_watch_db: Path) -> None:
        from gateway import web_monitor

        with (
            patch.object(web_monitor, "remove_watch", return_value=None),
            pytest.raises(
                monitors.MonitorError,
                match="returned NoneType, expected bool",
            ),
        ):
            monitors.delete_monitor("watch-123")


class TestCheckMonitor:
    @pytest.mark.asyncio
    async def test_returns_check_result(self, isolated_watch_db: Path) -> None:
        from gateway import web_monitor

        with patch.object(web_monitor, "_ensure_polling"):
            wid = web_monitor.add_watch("https://example.com/check")
        with patch.object(
            web_monitor, "check_now", return_value={"watch_id": wid, "changed": False}
        ) as mock_check:
            result = await monitors.check_monitor(wid)
        assert result["watch_id"] == wid
        mock_check.assert_awaited_once_with(wid)

    @pytest.mark.asyncio
    async def test_validates_id(self, isolated_watch_db: Path) -> None:
        with pytest.raises(ValueError, match="monitor_id"):
            await monitors.check_monitor("")

    @pytest.mark.asyncio
    async def test_converts_not_found_envelope_to_typed_404(
        self,
        isolated_watch_db: Path,
    ) -> None:
        from gateway import web_monitor

        with (
            patch.object(
                web_monitor,
                "check_now",
                return_value={"error": "Watch not found"},
            ),
            pytest.raises(monitors.MonitorNotFoundError, match="was not found"),
        ):
            await monitors.check_monitor("missing-watch")

    @pytest.mark.asyncio
    async def test_converts_http_error_envelope_to_typed_502(
        self,
        isolated_watch_db: Path,
    ) -> None:
        from gateway import web_monitor

        with (
            patch.object(
                web_monitor,
                "check_now",
                return_value={"status": "error", "code": 503, "changed": False},
            ),
            pytest.raises(
                monitors.MonitorCheckError,
                match="upstream returned HTTP 503",
            ) as raised,
        ):
            await monitors.check_monitor("watch-123")

        assert raised.value.status_code == 502
        assert raised.value.details["upstream_status"] == 503

    @pytest.mark.asyncio
    async def test_classifies_untyped_error_envelope_as_degraded_backend(
        self,
        isolated_watch_db: Path,
    ) -> None:
        from gateway import web_monitor

        with (
            patch.object(
                web_monitor,
                "check_now",
                return_value={
                    "status": "error",
                    "error": "database is locked",
                    "changed": False,
                },
            ),
            pytest.raises(
                monitors.MonitorError,
                match="backend returned an unclassified error",
            ) as raised,
        ):
            await monitors.check_monitor("watch-123")

        assert raised.value.status_code == 503
        assert raised.value.details == {
            "operation": "check",
            "monitor_id": "watch-123",
        }

    @pytest.mark.asyncio
    async def test_classifies_database_exception_as_storage_failure(
        self,
        isolated_watch_db: Path,
    ) -> None:
        from gateway import web_monitor

        with (
            patch.object(
                web_monitor,
                "check_now",
                side_effect=sqlite3.OperationalError("database is locked"),
            ),
            pytest.raises(
                monitors.MonitorError,
                match="monitor check failed.*database is locked",
            ) as raised,
        ):
            await monitors.check_monitor("watch-123")

        assert raised.value.status_code == 503
        assert raised.value.details["monitor_id"] == "watch-123"

    @pytest.mark.asyncio
    async def test_does_not_mislabel_programming_error_as_degraded_storage(
        self,
        isolated_watch_db: Path,
    ) -> None:
        from gateway import web_monitor

        defect = RuntimeError("unexpected monitor defect")
        with (
            patch.object(web_monitor, "check_now", side_effect=defect),
            pytest.raises(
                RuntimeError,
                match="unexpected monitor defect",
            ) as raised,
        ):
            await monitors.check_monitor("watch-123")

        assert raised.value is defect

    @pytest.mark.asyncio
    async def test_rejects_empty_success_envelope(
        self,
        isolated_watch_db: Path,
    ) -> None:
        from gateway import web_monitor

        with (
            patch.object(web_monitor, "check_now", return_value={}),
            pytest.raises(
                monitors.MonitorCheckError,
                match="invalid or mismatched watch_id",
            ),
        ):
            await monitors.check_monitor("watch-123")

    @pytest.mark.asyncio
    async def test_rejects_non_boolean_changed_value(
        self,
        isolated_watch_db: Path,
    ) -> None:
        from gateway import web_monitor

        with (
            patch.object(
                web_monitor,
                "check_now",
                return_value={"watch_id": "watch-123", "changed": "no"},
            ),
            pytest.raises(
                monitors.MonitorCheckError,
                match="non-boolean 'changed'",
            ),
        ):
            await monitors.check_monitor("watch-123")


def _app_client() -> TestClient:
    from gateway.app import app

    return TestClient(app, raise_server_exceptions=False)


def test_monitors_route_returns_structured_503_on_list_failure() -> None:
    with patch.object(
        monitors,
        "list_monitors",
        side_effect=monitors.MonitorError("monitor database is locked"),
    ):
        response = _app_client().get("/monitors")

    assert response.status_code == 503
    assert response.json() == {
        "error": "storage.unavailable",
        "message": "monitor database is locked",
    }


def test_monitor_create_route_reports_missing_url_as_validation_error() -> None:
    response = _app_client().post("/monitor/create", json={"interval": 60})

    assert response.status_code == 400
    assert response.json() == {
        "error": "validation_error",
        "message": "monitor create request is missing required field 'url'",
        "details": {"field": "url"},
    }


def test_monitor_delete_route_returns_404_instead_of_false_success() -> None:
    with patch.object(monitors, "delete_monitor", return_value=False):
        response = _app_client().delete("/monitor/missing-watch")

    assert response.status_code == 404
    assert response.json() == {
        "error": "storage.not_found",
        "message": "monitor 'missing-watch' was not found",
        "details": {"monitor_id": "missing-watch"},
    }


def test_monitor_check_route_returns_structured_502() -> None:
    error = monitors.MonitorCheckError(
        "monitor check failed for 'watch-123': upstream returned HTTP 503",
        details={"monitor_id": "watch-123", "upstream_status": 503},
    )
    with patch.object(monitors, "check_monitor", side_effect=error):
        response = _app_client().get("/monitor/watch-123/check")

    assert response.status_code == 502
    assert response.json() == {
        "error": "monitor.check_failed",
        "message": "monitor check failed for 'watch-123': upstream returned HTTP 503",
        "details": {"monitor_id": "watch-123", "upstream_status": 503},
    }


def test_monitor_check_route_classifies_store_failure_as_503() -> None:
    error = monitors.MonitorError(
        "monitor check failed: OperationalError: database is locked",
        details={"operation": "check", "monitor_id": "watch-123"},
    )
    with patch.object(monitors, "check_monitor", side_effect=error):
        response = _app_client().get("/monitor/watch-123/check")

    assert response.status_code == 503
    assert response.json() == {
        "error": "storage.unavailable",
        "message": "monitor check failed: OperationalError: database is locked",
        "details": {"operation": "check", "monitor_id": "watch-123"},
    }


def test_monitor_check_route_classifies_untyped_error_envelope_as_503() -> None:
    from gateway import web_monitor

    with patch.object(
        web_monitor,
        "check_now",
        return_value={
            "status": "error",
            "error": "database is locked",
            "changed": False,
        },
    ):
        response = _app_client().get("/monitor/watch-123/check")

    assert response.status_code == 503
    assert response.json() == {
        "error": "storage.unavailable",
        "message": "monitor check failed for 'watch-123': backend returned an unclassified error",
        "details": {"operation": "check", "monitor_id": "watch-123"},
    }
