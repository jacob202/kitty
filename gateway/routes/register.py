"""Mount all gateway route modules on the FastAPI app."""

from __future__ import annotations

from fastapi import FastAPI

from gateway.routes import (
    experts,
    actions,
    ask,
    brief,
    calendar,
    capture,
    chats,
    completions,
    cron,
    deadlines,
    desktop,
    dream,
    extended,
    inbox,
    insights,
    integrations,
    journal,
    kitty_tools,
    knowledge,
    loops,
    magic,
    memories,
    monitors,
    projects,
    prompts,
    search,
    state,
    status,
    telos,
    voice,
)


def register_routes(app: FastAPI) -> None:
    for module in (
        experts,
        actions,
        ask,
        brief,
        calendar,
        capture,
        chats,
        completions,
        cron,
        deadlines,
        desktop,
        dream,
        inbox,
        insights,
        integrations,
        journal,
        kitty_tools,
        knowledge,
        loops,
        memories,
        monitors,
        projects,
        prompts,
        search,
        state,
        status,
        telos,
        voice,
    extended,
    magic,
):
        app.include_router(module.router)
