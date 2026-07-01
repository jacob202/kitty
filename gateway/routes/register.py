from __future__ import annotations

from fastapi import FastAPI

from gateway.routes import ask, brief, calendar, chats, completions, cron, desktop
from gateway.routes import dream, extended, insights, integrations, journal, kitty_tools
from gateway.routes import loops, memories, monitors, prompts, search, state, telos, voice


def register_routes(app: FastAPI) -> None:
    for module in (
        ask,
        brief,
        calendar,
        chats,
        completions,
        cron,
        desktop,
        dream,
        insights,
        integrations,
        journal,
        kitty_tools,
        loops,
        memories,
        monitors,
        prompts,
        search,
        state,
        telos,
        voice,
        extended,
    ):
        app.include_router(module.router)
