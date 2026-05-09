import os
import requests
import logging
from typing import Optional

logger = logging.getLogger("kitty.notify")

def send_pushover(message: str, title: str = "Kitty Brief", url: Optional[str] = None) -> bool:
    """
    Sends a push notification to Jacob's phone via the Pushover API.
    Requires PUSHOVER_USER_KEY and PUSHOVER_API_TOKEN in .env.
    """
    user_key = os.environ.get("PUSHOVER_USER_KEY")
    api_token = os.environ.get("PUSHOVER_API_TOKEN")
    
    if not user_key or not api_token:
        logger.warning("Pushover credentials missing from .env. Notification skipped.")
        return False
        
    data = {
        "token": api_token,
        "user": user_key,
        "message": message,
        "title": title
    }
    
    if url:
        data["url"] = url
        data["url_title"] = "Open Kitty"
        
    try:
        resp = requests.post("https://api.pushover.net/1/messages.json", data=data, timeout=10)
        resp.raise_for_status()
        logger.info("Pushover notification sent successfully.")
        return True
    except Exception as e:
        logger.error("Failed to send Pushover notification: %s", e)
        return False


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
