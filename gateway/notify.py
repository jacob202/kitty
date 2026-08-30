"""Push notification — Pushover integration for phone alerts.

Public API:
  send(message, title, url) -> bool
  send_brief(summary) -> bool
  send_alert(message) -> bool
  is_configured() -> bool

Env vars: PUSHOVER_USER_KEY, PUSHOVER_API_TOKEN
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger("kitty.notify")

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


def _get_keys() -> tuple[str, str]:
    user = os.environ.get("PUSHOVER_USER_KEY", "").strip()
    token = os.environ.get("PUSHOVER_API_TOKEN", "").strip()
    return user, token


def send(
    message: str,
    title: str = "Kitty",
    url: Optional[str] = None,
    url_title: Optional[str] = None,
    priority: int = 0,
    sound: str = "pushover",
) -> bool:
    """Send a push notification via Pushover. Returns True on success."""
    user_key, api_token = _get_keys()
    if not user_key or not api_token:
        logger.warning("Pushover keys not configured — skipping notification")
        return False

    payload: dict = {
        "token": api_token,
        "user": user_key,
        "message": message[:1024],
        "title": title[:250],
        "priority": priority,
        "sound": sound,
    }
    if url:
        payload["url"] = url
        payload["url_title"] = url_title or "Open Kitty"

    try:
        resp = requests.post(PUSHOVER_URL, data=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("Pushover sent: %s", title)
            return True
        logger.error("Pushover failed (%d): %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.error("Pushover request failed: %s", e)
        return False


def send_brief(summary: str, open_url: Optional[str] = None) -> bool:
    """Convenience wrapper for morning brief delivery."""
    return send(
        message=summary,
        title="Kitty Morning Brief",
        url=open_url,
        url_title="Open Kitty",
    )


def send_alert(message: str, title: str = "Kitty Alert") -> bool:
    """High-priority notification that bypasses quiet hours."""
    return send(
        message=message,
        title=title,
        priority=2,
        sound="siren",
    )


def is_configured() -> bool:
    """Check if Pushover keys are set."""
    user, token = _get_keys()
    return bool(user and token)


# Backward compat aliases for existing callers
def send_pushover(message: str, title: str = "Kitty Brief", url: Optional[str] = None) -> bool:
    return send(message=message, title=title, url=url)


def format_brief_notification(brief: dict) -> tuple[str, str]:
    """Format a brief dict into (title, message) for Pushover."""
    today = brief.get("date", "Today")
    intention = brief.get("intention", "")
    headlines = brief.get("headlines", [])

    title = f"Kitty — {today}"
    lines = []
    if intention:
        lines.append(intention)
    if headlines:
        lines.append("")
        lines.append("News:")
        for h in headlines[:3]:
            lines.append(f"• {h.get('title', '')}")
    return title, "\n".join(lines)
