"""Persist onboarding state in the shared app_settings table.

So any browser, PWA, or phone sees the same onboarding state across devices.
"""

from __future__ import annotations

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE


ONBOARDING_COMPLETE_KEY = "onboarding_complete"
PREFERRED_NAME_KEY = "preferred_name"
THEME_KEY = "theme"


def get_onboarding_state() -> dict[str, str | bool | None]:
    """Read onboarding settings from app_settings."""
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        rows = conn.execute(
            "SELECT key, value FROM app_settings WHERE key IN (?, ?, ?)",
            (ONBOARDING_COMPLETE_KEY, PREFERRED_NAME_KEY, THEME_KEY),
        ).fetchall()
    mapping = {row["key"]: row["value"] for row in rows}
    return {
        "onboarded": mapping.get(ONBOARDING_COMPLETE_KEY) == "true",
        "preferredName": mapping.get(PREFERRED_NAME_KEY) or "",
        "theme": mapping.get(THEME_KEY) or "",
    }


def set_onboarding_state(
    *,
    onboarded: bool | None = None,
    preferred_name: str | None = None,
    theme: str | None = None,
) -> dict[str, str | bool]:
    """Persist onboarding settings. Returns the current state after write."""
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        if onboarded is not None:
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (ONBOARDING_COMPLETE_KEY, "true" if onboarded else "false"),
            )
        if preferred_name is not None:
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (PREFERRED_NAME_KEY, preferred_name.strip()),
            )
        if theme is not None:
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (THEME_KEY, theme),
            )
        conn.commit()
    return {"ok": True, "onboarded": onboarded if onboarded is not None else False}
