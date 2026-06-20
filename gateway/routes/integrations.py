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
    from gateway.imessage import send, is_available

    if not is_available():
        raise HTTPException(
            status_code=400, detail="iMessage not available (macOS only)"
        )
    success = send(payload.recipient, payload.message)
    return {"sent": success}


@router.get("/imessage/recent")
async def imessage_recent(limit: int = 10):
    from gateway.imessage import read_recent, is_available

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
    from gateway.sync import export_snapshot

    return export_snapshot()


@router.post("/sync/import")
async def sync_import(request: Request):
    from gateway.sync import import_snapshot

    body = await request.json()
    merged = import_snapshot(body)
    return {"merged": merged}


# --- Search endpoint ---


@router.get("/search")
async def search_all(q: str = "", limit: int = 5):
    from gateway.search import async_search

    return await async_search(q, limit=limit)


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


# --- Cron endpoints ---


class CronScheduleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=200)
    schedule_type: str = "daily"
    schedule_value: str = "07:00"
    metadata: Optional[dict] = None


@router.post("/cron/schedule")
async def cron_schedule(payload: CronScheduleRequest):
    from gateway.cron import schedule

    sid = schedule(
        name=payload.name,
        action=payload.action,
        schedule_type=payload.schedule_type,
        schedule_value=payload.schedule_value,
        metadata=payload.metadata,
    )
    return {"schedule_id": sid}


@router.get("/cron/schedules")
async def cron_list():
    from gateway.cron import list_schedules

    return {"schedules": list_schedules()}


@router.delete("/cron/{schedule_id}")
async def cron_delete(schedule_id: str):
    from gateway.cron import remove

    ok = remove(schedule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"deleted": True}


@router.post("/cron/{schedule_id}/toggle")
async def cron_toggle(schedule_id: str):
    from gateway.cron import toggle

    state = toggle(schedule_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"enabled": state}


@router.get("/cron/actions")
async def cron_actions():
    from gateway.cron import get_actions

    return {"actions": get_actions()}


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


# --- Web monitor endpoints ---


class WatchCreateRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    label: str = ""
    keywords: Optional[list[str]] = None
    interval_minutes: int = 30


@router.post("/monitor/create")
async def monitor_create(payload: WatchCreateRequest):
    from gateway.web_monitor import add_watch

    watch_id = add_watch(
        url=payload.url,
        label=payload.label,
        keywords=payload.keywords,
        interval_minutes=payload.interval_minutes,
    )
    return {"watch_id": watch_id}


@router.get("/monitors")
async def monitor_list():
    from gateway.web_monitor import list_watches

    return {"watches": list_watches()}


@router.post("/monitor/{watch_id}/check")
async def monitor_check(watch_id: str):
    from gateway.web_monitor import check_now

    result = await check_now(watch_id)
    return result


@router.delete("/monitor/{watch_id}")
async def monitor_delete(watch_id: str):
    from gateway.web_monitor import remove_watch

    removed = remove_watch(watch_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Watch not found")
    return {"deleted": True}
