"""Regression tests for gateway.context_enrichment fail-loud behavior.

The brief-content sync helpers must surface source outages as explicit
"unavailable" markers in the morning brief instead of silently returning
an empty section that hides the failure from the user.
"""

from __future__ import annotations

from gateway import context_enrichment as ce


def test_todos_text_sync_surfaces_failure(monkeypatch) -> None:
    def boom() -> str:
        raise RuntimeError("todo store down")

    import gateway.todo_store as ts

    monkeypatch.setattr(ts, "get_todos_text", boom)
    assert ce._TODOS_UNAVAILABLE in ce.todos_text_sync()


def test_todos_text_sync_happy_path(monkeypatch) -> None:
    import gateway.todo_store as ts

    monkeypatch.setattr(ts, "get_todos_text", lambda: "- buy milk")
    assert ce.todos_text_sync() == "- buy milk"


def test_weather_text_sync_surfaces_failure(monkeypatch) -> None:
    def boom() -> str:
        raise RuntimeError("weather api down")

    import gateway.weather as w

    monkeypatch.setattr(w, "get_weather_text", boom)
    assert ce._WEATHER_UNAVAILABLE in ce.weather_text_sync()


def test_calendar_text_sync_surfaces_failure(monkeypatch) -> None:
    def boom() -> list[dict]:
        raise RuntimeError("calendar down")

    import gateway.calendar_integration as ci

    monkeypatch.setattr(ci, "get_today", boom)
    monkeypatch.setattr(ci, "is_available", lambda: True)
    assert ce._CALENDAR_UNAVAILABLE in ce.calendar_today_text_sync()
