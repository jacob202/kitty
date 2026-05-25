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
    integrations,
    journal,
    kitty_tools,
    memories,
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
        journal,
        memories,
        voice,
        kitty_tools,
        integrations,
        extended,
    ):
        app.include_router(module.router)
