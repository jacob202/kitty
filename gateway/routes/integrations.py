"""Integrations: messaging, plugins, MCP, sync, ops tooling."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

class IntegrationsImessageSendResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsImessageRecentResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsTelegramStatusResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsPluginsResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsPluginNameEnableResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsPluginNameDisableResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsMcpServersResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsMcpToolsResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsSyncExportResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsSyncImportResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsDeployResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsNudgesResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsNudgeNudgeIdDismissResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsHealthWeeklyResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsPatternsWeeklyResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsPatternsAnnualResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsWeatherResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsBuildStartResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsBuildBuildIdResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsBuildBuildIdApproveStageResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsBuildsResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsVerifyResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsEvalRunResponse(BaseModel):
    model_config = {"extra": "allow"}


class IntegrationsEvalCompareResponse(BaseModel):
    model_config = {"extra": "allow"}



router = APIRouter(tags=["integrations"])

# --- iMessage endpoints ---


class iMessageSendRequest(BaseModel):
    recipient: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=2000)


@router.post("/imessage/send", response_model=IntegrationsImessageSendResponse)
async def imessage_send(payload: iMessageSendRequest):
    from gateway.imessage import is_available, send

    if not is_available():
        raise HTTPException(status_code=400, detail="iMessage not available (macOS only)")
    success = send(payload.recipient, payload.message)
    return {"sent": success}


@router.get("/imessage/recent", response_model=IntegrationsImessageRecentResponse)
async def imessage_recent(limit: int = 10):
    from gateway.imessage import is_available, read_recent

    if not is_available():
        return {"available": False, "messages": []}
    return {"available": True, "messages": read_recent(limit)}


# --- Telegram endpoints ---


@router.get("/telegram/status", response_model=IntegrationsTelegramStatusResponse)
async def telegram_status():
    from gateway.telegram_bot import is_configured

    return {"configured": is_configured()}


# --- Plugin endpoints ---


@router.get("/plugins", response_model=IntegrationsPluginsResponse)
async def plugins_list():
    from gateway.plugin_registry import list_plugins

    return {"plugins": list_plugins()}


@router.post("/plugin/{name}/enable", response_model=IntegrationsPluginNameEnableResponse)
async def plugin_enable(name: str):
    from gateway.storage_router import enable_plugin

    ok = enable_plugin(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {name}")
    return {"plugin": name, "enabled": True}


@router.post("/plugin/{name}/disable", response_model=IntegrationsPluginNameDisableResponse)
async def plugin_disable(name: str):
    from gateway.storage_router import disable_plugin

    ok = disable_plugin(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {name}")
    return {"plugin": name, "enabled": False}


# --- MCP endpoints ---


@router.get("/mcp/servers", response_model=IntegrationsMcpServersResponse)
async def mcp_servers():
    from gateway.mcp_tool_bridge import list_servers

    return {"servers": list_servers()}


@router.get("/mcp/tools", response_model=IntegrationsMcpToolsResponse)
async def mcp_tools():
    from gateway.mcp_tool_bridge import get_tool_schema_for_llm

    return {"tools": get_tool_schema_for_llm()}


# --- Sync endpoints ---


@router.get("/sync/export", response_model=IntegrationsSyncExportResponse)
async def sync_export():
    from gateway.storage_sync import export_all

    return export_all()


@router.post("/sync/import", response_model=IntegrationsSyncImportResponse)
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


@router.post("/deploy", response_model=IntegrationsDeployResponse)
async def deploy_project(payload: DeployRequest):
    from gateway.deploy import deploy

    return await deploy(payload.target_dir, payload.platform, payload.config)


# --- Nudge endpoints ---


@router.get("/nudges", response_model=IntegrationsNudgesResponse)
async def nudge_list():
    from gateway.nudge import get_pending

    return {"nudges": get_pending()}


@router.post("/nudge/{nudge_id}/dismiss", response_model=IntegrationsNudgeNudgeIdDismissResponse)
async def nudge_dismiss(nudge_id: str):
    from gateway.nudge import dismiss

    dismiss(nudge_id)
    return {"dismissed": True}


# --- Health & Patterns endpoints ---


@router.get("/health/weekly", response_model=IntegrationsHealthWeeklyResponse)
async def health_weekly():
    from gateway.health_parser import get_weekly_summary

    return get_weekly_summary()


@router.get("/patterns/weekly", response_model=IntegrationsPatternsWeeklyResponse)
async def patterns_weekly():
    from gateway.patterns import weekly

    return weekly()


@router.get("/patterns/annual", response_model=IntegrationsPatternsAnnualResponse)
async def patterns_annual():
    from gateway.patterns import annual_review

    return annual_review()


# --- Cron endpoints consolidated into routes/cron.py ---


@router.get("/weather", response_model=IntegrationsWeatherResponse)
async def weather():
    """Current weather for Regina."""
    from gateway.weather import get_weather

    return get_weather() or {"error": "weather unavailable"}


# --- Build endpoints ---


class BuildStartRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=3000)
    target_dir: str = ""
    auto_approve: bool = False


@router.post("/build/start", response_model=IntegrationsBuildStartResponse)
async def build_start(payload: BuildStartRequest):
    from gateway.builder import start

    build_id = start(
        goal=payload.goal,
        target_dir=payload.target_dir,
        auto_approve=payload.auto_approve,
    )
    return {"build_id": build_id, "status": "started"}


@router.get("/build/{build_id}", response_model=IntegrationsBuildBuildIdResponse)
async def build_status(build_id: str):
    from gateway.builder import status

    s = status(build_id)
    if s.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Build not found")
    return s


@router.post("/build/{build_id}/approve/{stage}", response_model=IntegrationsBuildBuildIdApproveStageResponse)
async def build_approve(build_id: str, stage: str):
    from gateway.builder import approve_stage

    approved = approve_stage(build_id, stage)
    if not approved:
        raise HTTPException(status_code=400, detail="Stage not awaiting approval")
    return {"build_id": build_id, "stage": stage, "approved": True}


@router.get("/builds", response_model=IntegrationsBuildsResponse)
async def build_list(limit: int = 10):
    from gateway.builder import list_builds

    return {"builds": list_builds(limit=limit)}


# --- Verifier endpoints ---


class VerifyRequest(BaseModel):
    target_dir: str = Field(min_length=1, max_length=1000)
    test_path: Optional[str] = None


@router.post("/verify", response_model=IntegrationsVerifyResponse)
async def verify_run(payload: VerifyRequest):
    from gateway.verifier import verify

    result = await verify(payload.target_dir, payload.test_path)
    return result


# --- Eval endpoints ---


@router.post("/eval/run", response_model=IntegrationsEvalRunResponse)
async def eval_run():
    from gateway.eval_runner import run_smoke

    return await run_smoke()


@router.get("/eval/compare", response_model=IntegrationsEvalCompareResponse)
async def eval_compare():
    from gateway.eval_runner import run_and_compare

    return await run_and_compare()


# --- Web monitor endpoints consolidated into routes/monitors.py ---
