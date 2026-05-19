"""Mount all gateway route modules on the FastAPI app."""

from __future__ import annotations

from fastapi import FastAPI

from gateway.routes import brief, calendar, chat, extended, integrations


def register_routes(app: FastAPI) -> None:
    for module in (brief, calendar, chat, integrations, extended):
        app.include_router(module.router)
