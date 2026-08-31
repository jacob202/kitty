"""RED tests for QoL-01 Kitty Health projection (gateway/health_surface.py).

The projection is a read-only composition of existing primitives; every test
injects fake domain sources so nothing touches the network or the live
automation supervisor.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gateway.health_surface import HealthDomain, build_health_surface


def _src(
    name: str,
    status: str,
    *,
    reason: str = "",
    detail: dict | None = None,
):
    async def _collect() -> HealthDomain:
        return HealthDomain(
            name=name,
            status=status,
            reason=reason,
            detail=detail or {},
        )

    return _collect


def _healthy_sources() -> dict:
    return {
        "gateway": _src("gateway", "available", reason="ok"),
        "database": _src("database", "available", reason="ok"),
        "memory": _src("memory", "available", reason="ok"),
        "automation_supervisor": _src("automation_supervisor", "available", reason="ok"),
        "cron": _src("cron", "available", reason="ok"),
        "telegram": _src("telegram", "available", reason="ok"),
        "image_lab": _src("image_lab", "available", reason="ok"),
        "image_providers": _src("image_providers", "available", reason="ok"),
        "image_queue": _src("image_queue", "available", reason="ok"),
        "ollama": _src("ollama", "available", reason="ok"),
        "pending_grants": _src(
            "pending_grants", "available", reason="ok", detail={"count": 2}
        ),
    }


@pytest.mark.asyncio
async def test_all_healthy_overall_healthy():
    result = await build_health_surface(_healthy_sources())
    assert result["overall"] == "healthy"
    assert result["degraded"] == []
    assert set(result["still_functional"]) == set(_healthy_sources())
    assert all(d["status"] == "available" for d in result["domains"])
    assert isinstance(result["generated_at"], str)
    assert result["generated_at"]


@pytest.mark.asyncio
async def test_one_degraded_domain_surfaces_overall_and_detail():
    sources = _healthy_sources()
    sources["cron"] = _src("cron", "degraded", reason="ValueError: watcher crashed")
    result = await build_health_surface(sources)
    assert result["overall"] == "degraded"
    assert "cron" in result["degraded"]
    cron = next(d for d in result["domains"] if d["name"] == "cron")
    assert cron["status"] == "degraded"
    assert "watcher crashed" in cron["reason"]


@pytest.mark.asyncio
async def test_unavailable_dependency_is_truthful():
    sources = _healthy_sources()
    sources["telegram"] = _src("telegram", "unavailable", reason="integration not configured")
    result = await build_health_surface(sources)
    assert result["overall"] == "degraded"
    assert "telegram" in result["degraded"]
    assert result["still_functional"] == [
        name for name in _healthy_sources() if name != "telegram"
    ]


@pytest.mark.asyncio
async def test_stale_service_reported_stale():
    sources = _healthy_sources()
    sources["cron"] = _src("cron", "stale", reason="service heartbeat is stale")
    result = await build_health_surface(sources)
    cron = next(d for d in result["domains"] if d["name"] == "cron")
    assert cron["status"] == "stale"
    assert "stale" in cron["reason"]
    assert "cron" in result["degraded"]
    assert result["overall"] == "degraded"


@pytest.mark.asyncio
async def test_gateway_unreachable_makes_overall_unavailable():
    sources = _healthy_sources()
    sources["gateway"] = _src("gateway", "unavailable", reason="unreachable: gateway down")
    result = await build_health_surface(sources)
    assert result["overall"] == "unavailable"
    assert "gateway" in result["degraded"]


@pytest.mark.asyncio
async def test_source_failure_fails_loud_never_silently_green():
    async def boom():
        raise RuntimeError("snapshot failed")

    sources = _healthy_sources()
    sources["automation_supervisor"] = boom
    with pytest.raises(RuntimeError, match="snapshot failed"):
        await build_health_surface(sources)


@pytest.mark.asyncio
async def test_image_lab_health_ignores_completed_startup_recovery(monkeypatch):
    import gateway.automation_supervisor as supervision
    import gateway.health_surface as health_surface

    statuses = {
        "image-recovery": {"status": "unavailable", "reason": "task exited"},
        "image-batch-worker": {"status": "available", "reason": "task running"},
    }
    monkeypatch.setattr(
        supervision.supervisor,
        "get_status",
        lambda name: statuses[name],
    )

    domain = await health_surface._image_lab_source()

    assert domain.status == "available"
    assert domain.detail == {"image-batch-worker": "available"}


@pytest.mark.asyncio
async def test_image_provider_down_image_lab_still_functional():
    sources = _healthy_sources()
    sources["image_providers"] = _src(
        "image_providers", "unavailable", reason="FAL_API_KEY is not set"
    )
    result = await build_health_surface(sources)
    assert result["overall"] == "degraded"
    assert "image_providers" in result["degraded"]
    assert "image_lab" in result["still_functional"]


@pytest.mark.asyncio
async def test_ollama_down_memory_still_functional():
    sources = _healthy_sources()
    sources["ollama"] = _src("ollama", "unavailable", reason="embedding model unavailable")
    result = await build_health_surface(sources)
    assert result["overall"] == "degraded"
    assert "ollama" in result["degraded"]
    assert "memory" in result["still_functional"]


@pytest.mark.asyncio
async def test_pending_grants_count_surfaced():
    result = await build_health_surface(_healthy_sources())
    assert result["pending_grants"] == 2


def test_health_surface_route_returns_projection(monkeypatch):
    import gateway.routes.status as status_routes
    from gateway.app import app

    async def fake_build(_sources=None):
        return {
            "generated_at": "2026-08-23T12:00:00Z",
            "overall": "healthy",
            "domains": [],
            "degraded": [],
            "still_functional": ["gateway"],
            "pending_grants": 0,
        }

    monkeypatch.setattr(status_routes, "build_health_surface", fake_build)
    client = TestClient(app, raise_server_exceptions=True)
    r = client.get("/health/surface")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] == "healthy"
    assert "generated_at" in body
    assert "domains" in body
    assert "degraded" in body
    assert "still_functional" in body
    assert "pending_grants" in body


@pytest.mark.asyncio
async def test_mcp_tool_health_degrades_on_open_circuit_without_claiming_remote_probe(monkeypatch):
    import gateway.health_surface as health_surface
    import gateway.mcp_tool_bridge as mcp

    monkeypatch.setattr(
        mcp,
        "tool_health_snapshot",
        lambda: {
            "state": "degraded",
            "configured_servers": 2,
            "open_circuits": [
                {
                    "server": "search",
                    "tool": "query",
                    "consecutive_failures": 3,
                    "retry_after_seconds": 20.0,
                    "probe_due": False,
                    "last_error": "timeout",
                }
            ],
            "remote_health_probed": False,
        },
    )

    domain = await health_surface._mcp_tools_source()

    assert domain.status == "degraded"
    assert "1 tool circuit" in domain.reason
    assert domain.detail["remote_health_probed"] is False
    assert domain.detail["open_circuits"][0]["tool"] == "query"


@pytest.mark.asyncio
async def test_mcp_tool_health_with_no_servers_is_available_but_not_live_probed(monkeypatch):
    import gateway.health_surface as health_surface
    import gateway.mcp_tool_bridge as mcp

    monkeypatch.setattr(
        mcp,
        "tool_health_snapshot",
        lambda: {
            "state": "available",
            "configured_servers": 0,
            "open_circuits": [],
            "remote_health_probed": False,
        },
    )

    domain = await health_surface._mcp_tools_source()

    assert domain.status == "available"
    assert "no MCP servers configured" in domain.reason
    assert domain.detail["remote_health_probed"] is False


@pytest.mark.asyncio
async def test_mcp_tool_configuration_error_is_degraded_even_without_open_circuit(monkeypatch):
    import gateway.health_surface as health_surface
    import gateway.mcp_tool_bridge as mcp

    monkeypatch.setattr(
        mcp,
        "tool_health_snapshot",
        lambda: {
            "state": "degraded",
            "configured_servers": 1,
            "configuration_errors": ["demo: timeout_seconds must be positive"],
            "open_circuits": [],
            "remote_health_probed": False,
        },
    )

    domain = await health_surface._mcp_tools_source()

    assert domain.status == "degraded"
    assert "1 MCP configuration error" in domain.reason
    assert domain.detail["remote_health_probed"] is False


@pytest.mark.asyncio
async def test_image_provider_health_includes_openai_image_lane(monkeypatch):
    import gateway.health_surface as health_surface
    import gateway.image_runner as image_runner

    for name in (
        "airforce_images_available", "fal_images_available", "openrouter_images_available",
        "flux_images_available", "flux2_images_available",
    ):
        monkeypatch.setattr(image_runner, name, lambda: (False, "off"))
    monkeypatch.setattr(image_runner, "openai_images_available", lambda: (True, ""))

    domain = await health_surface._image_providers_source()

    assert domain.status == "available"
    assert domain.detail["openai"] == {"ok": True, "reason": ""}
    assert "1/6 provider(s) ready" in domain.reason
