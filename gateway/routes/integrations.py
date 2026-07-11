"""Integrations: messaging, plugins, MCP, sync, ops tooling."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(tags=["integrations"])

# --- iMessage endpoints ---


class iMessageSendRequest(BaseModel):
    recipient: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=2000)


@router.post("/imessage/send")
async def imessage_send(payload: iMessageSendRequest):
    from gateway.imessage import is_available, send

    if not is_available():
        raise HTTPException(status_code=400, detail="iMessage not available (macOS only)")
    success = send(payload.recipient, payload.message)
    return {"sent": success}


@router.get("/imessage/recent")
async def imessage_recent(limit: int = 10):
    from gateway.imessage import is_available, read_recent

    if not is_available():
        return {"available": False, "messages": []}
    return {"available": True, "messages": read_recent(limit)}


# --- Telegram endpoints ---


@router.get("/telegram/status")
async def telegram_status():
    from gateway.telegram_bot import is_configured

    return {"configured": is_configured()}


# --- Plugin endpoints ---


@router.get("/plugins")
async def plugins_list():
    from gateway.plugin_registry import list_plugins

    return {"plugins": list_plugins()}


@router.post("/plugin/{name}/enable")
async def plugin_enable(name: str):
    from gateway.storage_router import enable_plugin

    ok = enable_plugin(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {name}")
    return {"plugin": name, "enabled": True}


@router.post("/plugin/{name}/disable")
async def plugin_disable(name: str):
    from gateway.storage_router import disable_plugin

    ok = disable_plugin(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {name}")
    return {"plugin": name, "enabled": False}


# --- MCP endpoints ---


@router.get("/mcp/servers")
async def mcp_servers():
    from gateway.mcp_tool_bridge import list_servers

    return {"servers": list_servers()}


@router.get("/mcp/tools")
async def mcp_tools():
    from gateway.mcp_tool_bridge import get_tool_schema_for_llm

    return {"tools": get_tool_schema_for_llm()}


# --- Sync endpoints ---


@router.get("/sync/export")
async def sync_export():
    from gateway.storage_sync import export_all

    return export_all()


@router.post("/sync/import")
async def sync_import(request: Request):
    from gateway.storage_sync import import_all

    body = await request.json()
    counts = import_all(body)
    return {"imported": counts}


# --- Search endpoint consolidated into routes/search.py ---


# --- Deploy endpoint ---


class DeployRequest(BaseModel):
    target_dir: str = Field(min_length=1, max_length=1000)
    platform: str = "docker"
    config: Optional[dict] = None


@router.post("/deploy")
async def deploy_project(payload: DeployRequest):
    from gateway.deploy import deploy

    return await deploy(payload.target_dir, payload.platform, payload.config)


# --- Nudge endpoints ---


@router.get("/nudges")
async def nudge_list():
    from gateway.nudge import get_pending

    return {"nudges": get_pending()}


@router.post("/nudge/{nudge_id}/dismiss")
async def nudge_dismiss(nudge_id: str):
    from gateway.nudge import dismiss

    dismiss(nudge_id)
    return {"dismissed": True}


# --- Health & Patterns endpoints ---


@router.get("/health/weekly")
async def health_weekly():
    from gateway.health_parser import get_weekly_summary

    return get_weekly_summary()


@router.get("/patterns/weekly")
async def patterns_weekly():
    from gateway.patterns import weekly

    return weekly()


@router.get("/patterns/annual")
async def patterns_annual():
    from gateway.patterns import annual_review

    return annual_review()


# --- Cron endpoints consolidated into routes/cron.py ---


@router.get("/weather")
async def weather():
    """Current weather for Regina."""
    from gateway.weather import get_weather

    return get_weather() or {"error": "weather unavailable"}


# --- Build endpoints ---


class BuildStartRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=3000)
    target_dir: str = ""
    auto_approve: bool = False


@router.post("/build/start")
async def build_start(payload: BuildStartRequest):
    from gateway.builder import start

    build_id = start(
        goal=payload.goal,
        target_dir=payload.target_dir,
        auto_approve=payload.auto_approve,
    )
    return {"build_id": build_id, "status": "started"}


@router.get("/build/{build_id}")
async def build_status(build_id: str):
    from gateway.builder import status

    s = status(build_id)
    if s.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Build not found")
    return s


@router.post("/build/{build_id}/approve/{stage}")
async def build_approve(build_id: str, stage: str):
    from gateway.builder import approve_stage

    approved = approve_stage(build_id, stage)
    if not approved:
        raise HTTPException(status_code=400, detail="Stage not awaiting approval")
    return {"build_id": build_id, "stage": stage, "approved": True}


@router.get("/builds")
async def build_list(limit: int = 10):
    from gateway.builder import list_builds

    return {"builds": list_builds(limit=limit)}


# --- Verifier endpoints ---


class VerifyRequest(BaseModel):
    target_dir: str = Field(min_length=1, max_length=1000)
    test_path: Optional[str] = None


@router.post("/verify")
async def verify_run(payload: VerifyRequest):
    from gateway.verifier import verify

    result = await verify(payload.target_dir, payload.test_path)
    return result


# --- Eval endpoints ---


@router.post("/eval/run")
async def eval_run():
    from gateway.eval_runner import run_smoke

    return await run_smoke()


@router.get("/eval/compare")
async def eval_compare():
    from gateway.eval_runner import run_and_compare

    return await run_and_compare()


# --- Web monitor endpoints consolidated into routes/monitors.py ---
