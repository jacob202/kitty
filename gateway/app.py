"""Kitty Gateway — thin FastAPI brain between the kitty-chat UI and LiteLLM."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from gateway.auth import BearerAuthMiddleware
from gateway.config import is_test_env
from gateway.constants import MAX_BODY_BYTES
from gateway.errors import KittyError
from gateway.paths import validate_dirs, validate_env
from gateway.routes.register import register_routes
from gateway.voice_middleware import VoiceGateMiddleware

logger = logging.getLogger("kitty.gateway")
logging.basicConfig(level=logging.INFO)


def _reconcile_image_jobs_on_startup() -> None:
    """Close image jobs whose generating gateway coroutine no longer exists."""
    from gateway.image_jobs import reconcile_stale

    reconciled = reconcile_stale()
    if reconciled:
        logger.warning("reconciled %d orphaned image job(s) at startup", reconciled)


async def _recover_unknown_bfl_jobs_on_startup() -> None:
    """Reconcile durable BFL receipts without blocking Gateway startup."""
    try:
        from gateway.image_runner import recover_unknown_bfl_jobs

        recovered = await recover_unknown_bfl_jobs()
    except Exception:
        logger.exception("BFL image recovery pass failed; unknown jobs remain recoverable")
        return
    if recovered:
        logger.warning("recovered %d unknown BFL image job(s) at startup", recovered)


def _reconcile_image_batches_on_startup() -> None:
    """Fail interrupted image renders while preserving queued batch work."""
    from gateway.image_batches import reconcile_inflight

    reconciled = reconcile_inflight()
    if reconciled:
        logger.warning("reconciled %d interrupted image batch item(s) at startup", reconciled)


def _reconcile_agent_workspace_turns_on_startup() -> None:
    """Make room work truthful after the in-process executor has restarted."""
    from gateway.agent_workspace import interrupt_running_turns

    reconciled = interrupt_running_turns()
    if reconciled:
        logger.warning("interrupted %d orphaned shared-agent room turn(s) at startup", reconciled)



def _reconcile_autonomy_sessions_on_startup() -> None:
    """Make spawned-agent work truthful after the in-process executor has restarted."""
    from gateway.autonomy_state import interrupt_active_sessions

    reconciled = interrupt_active_sessions()
    if reconciled:
        logger.warning("interrupted %d orphaned autonomy session(s) at startup", reconciled)


def _reconcile_actions_on_startup() -> None:
    """Make ActionQueue rows truthful after a crash mid-execution (REL-002)."""
    from gateway.action_queue import reconcile_stale_executing

    reconciled = reconcile_stale_executing()
    if reconciled:
        logger.warning(
            "marked %d ActionQueue row(s) unknown after a restart mid-execution",
            reconciled,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_dirs()
    validate_env()
    _reconcile_image_jobs_on_startup()
    _reconcile_image_batches_on_startup()
    _reconcile_agent_workspace_turns_on_startup()
    _reconcile_autonomy_sessions_on_startup()
    _reconcile_actions_on_startup()
    from gateway.automation_supervisor import RecoveryPolicy, supervisor
    from gateway.image_recipes import seed_default_recipes

    seed_default_recipes()
    background_services_enabled = not is_test_env()
    if background_services_enabled:
        try:
            from gateway.telegram_bot import is_configured as tg_configured
            from gateway.telegram_bot import start_polling
            from gateway.telegram_bot import stop as tg_stop

            if tg_configured():
                supervisor.track_recoverable(
                    "telegram",
                    start_polling,
                    policy=RecoveryPolicy(
                        max_attempts=3,
                        backoff_seconds=2.0,
                        backoff_factor=5.0,
                        backoff_max=60.0,
                        cooldown_seconds=300.0,
                    ),
                    stop=tg_stop,
                )
            else:
                supervisor.mark("telegram", "unavailable", reason="integration not configured")
        except Exception as exc:
            supervisor.mark("telegram", "degraded", reason=f"{type(exc).__name__}: {exc}")
            logger.exception("telegram bot startup failed — integration disabled")

        # Startup BFL recovery is a one-shot reconciliation pass, not a
        # persistent background service. Keep it asynchronous without putting
        # normal task completion into the supervisor's unavailable state.
        image_recovery_task = asyncio.create_task(
            _recover_unknown_bfl_jobs_on_startup()
        )
        app.state.image_recovery_task = image_recovery_task

        from gateway.image_batches import worker_loop as image_batch_worker_loop
        from gateway.routes.image_studio_jobs import execute_studio_batch_request

        supervisor.track_recoverable(
            "image-batch-worker",
            lambda: image_batch_worker_loop(execute_studio_batch_request),
            policy=RecoveryPolicy(
                max_attempts=3,
                backoff_seconds=2.0,
                backoff_factor=5.0,
                backoff_max=60.0,
                cooldown_seconds=300.0,
            ),
        )
        try:
            import gateway.cron as cron
            from gateway import automation_actions
            from gateway.cron import register_action
            from gateway.cron import start as cron_start
            from gateway.web_monitor import deliver_notification

            automation_actions.register_action(
                "web_monitor.notify",
                deliver_notification,
                policy=automation_actions.ActionPolicy(capability="notify.send", tier="T1"),
            )

            async def _action_deliver_brief():
                from gateway.brief_scheduler import generate_and_deliver_brief

                await asyncio.to_thread(generate_and_deliver_brief)

            async def _action_refresh_brief():
                from gateway.brief import generate_brief

                await asyncio.to_thread(generate_brief)

            async def _action_check_nudges():
                from gateway.nudge import check

                check()

            async def _action_check_monitors():
                from gateway.web_monitor import check_due

                await check_due()

            async def _action_memory_consolidate():
                from gateway.memory_consolidation import nightly_dream

                await asyncio.to_thread(nightly_dream)

            async def _action_compact_traces():
                from gateway.memory_consolidation import prune_trace_log

                await asyncio.to_thread(prune_trace_log)

            async def _action_triage_inbox():
                from gateway import triage

                await asyncio.to_thread(triage.run_pass)

            async def _action_scan_icloud_inbox():
                from gateway.inbox_watcher import scan_once

                await asyncio.to_thread(scan_once)

            async def _action_poll_mail():
                from gateway.connectors.mail import poll_now

                await asyncio.to_thread(poll_now)

            async def _action_warm_prefetch():
                from gateway.prefetcher import warm

                await warm()

            register_action("brief.deliver", _action_deliver_brief, tier="T1")
            register_action("brief.refresh", _action_refresh_brief)
            register_action("nudges.check", _action_check_nudges)
            register_action("monitors.check", _action_check_monitors)
            register_action("memory.consolidate", _action_memory_consolidate)
            register_action("traces.compact", _action_compact_traces)
            register_action("inbox.triage", _action_triage_inbox)
            register_action("inbox.scan", _action_scan_icloud_inbox)

            def _action_poll_github():
                from gateway.connectors import github

                return github.poll_now()

            async def _action_poll_experts():
                from gateway.expert_proactive import poll_experts

                await asyncio.to_thread(poll_experts)

            register_action("mail.poll", _action_poll_mail)
            register_action("github.poll", _action_poll_github)
            register_action("experts.poll", _action_poll_experts)
            register_action("prefetch.warm", _action_warm_prefetch)

            from gateway.life_cron import evening_reflection_action, morning_proactive_action

            async def _action_life_evening_reflection():
                await evening_reflection_action()

            async def _action_life_morning_proactive():
                await morning_proactive_action()

            async def _action_insights_return_due():
                from gateway.insight_loop import return_due

                await return_due()

            register_action("life.evening_reflection", _action_life_evening_reflection, tier="T1")
            register_action("life.morning_proactive", _action_life_morning_proactive, tier="T1")
            register_action("insights.return_due", _action_insights_return_due)
            from gateway.brief_scheduler import load_brief_time, load_brief_timezone

            cron.ensure_schedule(
                "morning brief",
                "brief.deliver",
                "daily",
                load_brief_time(),
                {"timezone": load_brief_timezone().key},
            )
            cron.schedule("brief cache refresh", "brief.refresh", "interval", "15")
            cron.schedule("insights return due", "insights.return_due", "interval", "15")
            cron.schedule("web monitor due checks", "monitors.check", "interval", "5")
            cron.schedule("iCloud inbox scan", "inbox.scan", "interval", "0.5")
            cron.schedule("trace log compaction", "traces.compact", "daily", "03:30")
            def _cron_factory():
                task = cron_start()
                if task is None:
                    raise RuntimeError("cron runner failed to start (automation run evidence unavailable)")
                return task

            supervisor.track_recoverable(
                "cron",
                _cron_factory,
                policy=RecoveryPolicy(
                    max_attempts=3,
                    backoff_seconds=2.0,
                    backoff_factor=5.0,
                    backoff_max=60.0,
                    cooldown_seconds=300.0,
                ),
                stop=cron.stop,
                stale_after=90.0,
            )
        except Exception as exc:
            supervisor.mark("cron", "degraded", reason=f"{type(exc).__name__}: {exc}")
            logger.exception("cron system registration failed — scheduled jobs disabled")

        try:
            from gateway.capability_report import (
                probe_capabilities,
                render_capability_report,
            )

            startup_report = await probe_capabilities()
            app.state.startup_capability_report = startup_report
            logger.info(render_capability_report(startup_report))
        except Exception as exc:
            logger.exception("startup capability report failed: %s", exc)
    yield
    if background_services_enabled:
        await supervisor.stop_all()
        pending_image_recovery = getattr(app.state, "image_recovery_task", None)
        if pending_image_recovery is not None and not pending_image_recovery.done():
            pending_image_recovery.cancel()
            try:
                await pending_image_recovery
            except asyncio.CancelledError:
                pass
    try:
        from gateway.http_client import _http_client

        if _http_client and not _http_client.is_closed:
            await _http_client.aclose()
    except Exception:
        logger.warning("Failed to close HTTP client during shutdown")


app = FastAPI(title="Kitty Gateway", lifespan=lifespan)

app.add_middleware(VoiceGateMiddleware)
app.add_middleware(BearerAuthMiddleware)
_cors_origins = ["http://localhost:3000", "http://localhost:4000", "http://localhost:4001"]

# Explicit CORS allow-lists. Wildcard methods/headers with credentials is the
# canonical RCE primitive the moment allow_origins widens to any external host
# (browsers will then let any page on a wildcarded origin call the gateway as
# the user). Keep narrow; expand only with a reviewer ticket.
# See docs/AUDIT_FULL_ENGINEERING_2026-07-20.md §1.4.
_CORS_ALLOWED_METHODS: list[str] = [
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
]
_CORS_ALLOWED_HEADERS: list[str] = [
    "Authorization",
    "Content-Type",
    "X-Requested-With",
    "Accept",
    "Origin",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=_CORS_ALLOWED_METHODS,
    allow_headers=_CORS_ALLOWED_HEADERS,
)


@app.middleware("http")
async def body_size_guard(request: Request, call_next):
    """Reject requests with content-length exceeding MAX_BODY_BYTES."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError:
            return Response(status_code=400, content="Invalid Content-Length header")
        if declared_length < 0:
            return Response(status_code=400, content="Invalid Content-Length header")
        if declared_length > MAX_BODY_BYTES:
            return Response(status_code=413, content="Request body too large")
    return await call_next(request)


@app.exception_handler(KittyError)
async def kitty_error_handler(request: Request, exc: KittyError):
    """Translate ``KittyError`` subclasses to a consistent JSON error shape.

    Falls through to FastAPI's default 500 for genuinely unexpected
    exceptions — this handler only fires for errors the gateway
    describes on purpose. The body shape is:

    ``{"error": "<machine code>", "message": "...", "details": {...}}``
    """
    if exc.status_code >= 500:
        logger.exception("kitty_error: %s %s", exc.code, exc.message)
    return Response(
        status_code=exc.status_code,
        media_type="application/json",
        content=json.dumps(exc.to_dict()),
    )


@app.get("/health")
async def health():
    # litellm_reachable lives here because /api/models masks LiteLLM failures
    # behind a fallback model list — this is the one honest signal the UI
    # health strip can read. Short timeout so a dead proxy can't make the
    # gateway itself look slow.
    from gateway.http_client import get_http_client
    from gateway.paths import LITELLM_BASE

    litellm_reachable = False
    try:
        client = await get_http_client()
        resp = await client.get(f"{LITELLM_BASE}/health/readiness", timeout=1.5)
        litellm_reachable = resp.status_code == 200
    except Exception:  # noqa: BLE001 — any failure means "not reachable", which is the answer
        logger.warning("Health check: LiteLLM unreachable")
        litellm_reachable = False
    return {
        "status": "ok",
        "service": "kitty-gateway",
        "litellm_reachable": litellm_reachable,
    }


@app.get("/mood")
async def get_mood():
    """Return Kitty's current mood and session stats for the UI."""
    from gateway.buddy import get_state

    return get_state()


@app.get("/stream")
async def sse_stream(request: Request, session_id: str | None = None):
    """Server-Sent Events endpoint for pushing state changes to the UI."""
    import uuid

    from fastapi.responses import StreamingResponse

    from gateway.sse import broadcaster

    client_id = session_id or str(uuid.uuid4())

    async def event_generator():
        async for message in broadcaster.subscribe(client_id):
            if await request.is_disconnected():
                break
            yield message

    return StreamingResponse(event_generator(), media_type="text/event-stream")


register_routes(app)
