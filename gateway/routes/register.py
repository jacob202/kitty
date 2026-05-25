"""Mount all gateway route modules on the FastAPI app."""

from __future__ import annotations

from fastapi import FastAPI

from gateway.routes import (
    ask,
    brief,
    calendar,
    chats,
    completions,
    cron,
    dream,
    extended,
    insights,
    integrations,
    journal,
    kitty_tools,
    loops,
    memories,
    monitors,
    prompts,
    search,
    voice,
)


def register_routes(app: FastAPI) -> None:
    for module in (
        ask,
        brief,
        calendar,
        chats,
        completions,
        cron,
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
        voice,
        extended,
    ):
        app.include_router(module.router)
