"""Calendar integration — read/write macOS Calendar via AppleScript.

Public API:
  get_today() -> list[dict]      Today's events
  get_upcoming(days) -> list[dict]  Events in next N days
  create(title, start, end, notes) -> bool
"""
from __future__ import annotations

import logging
import subprocess
from typing import Optional

logger = logging.getLogger("kitty.calendar")


def _run_applescript(script: str) -> tuple[bool, str]:
    """Run an AppleScript and return (success, output)."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        logger.warning("AppleScript failed: %s", result.stderr.strip())
        return False, result.stderr.strip()
    except FileNotFoundError:
        logger.warning("osascript not available — not on macOS?")
        return False, "osascript not available"
    except subprocess.TimeoutExpired:
        logger.warning("AppleScript timed out")
        return False, "timeout"
    except Exception as e:
        logger.error("AppleScript error: %s", e)
        return False, str(e)


def _parse_event_lines(output: str) -> list[dict]:
    """Parse AppleScript output: each event is 3 lines: title, start, end."""
    events = []
    lines = [l.strip() for l in output.split("\n") if l.strip()]
    for i in range(0, len(lines), 3):
        if i + 2 < len(lines):
            events.append({
                "title": lines[i],
                "start": lines[i + 1],
                "end": lines[i + 2],
            })
    return events


def get_today() -> list[dict]:
    """Get today's calendar events."""
    script = """
    tell application "Calendar"
        set todayStart to (current date) - (time of (current date))
        set todayEnd to todayStart + (24 * hours)
        set eventList to {}
        tell calendar "Calendar"
            set calEvents to (every event whose start date >= todayStart and start date < todayEnd)
            repeat with ev in calEvents
                set end of eventList to summary of ev
                set end of eventList to start date of ev as string
                set end of eventList to end date of ev as string
            end repeat
        end tell
        set AppleScript's text item delimiters to linefeed
        return eventList as string
    end tell
    """
    ok, out = _run_applescript(script)
    if not ok:
        return []
    return _parse_event_lines(out)


def get_upcoming(days: int = 7) -> list[dict]:
    """Get events for the next N days."""
    script = f"""
    tell application "Calendar"
        set dayStart to (current date) - (time of (current date))
        set dayEnd to dayStart + ({days} * days)
        set eventList to {{}}
        tell calendar "Calendar"
            set calEvents to (every event whose start date >= dayStart and start date < dayEnd)
            repeat with ev in calEvents
                set end of eventList to summary of ev
                set end of eventList to start date of ev as string
                set end of eventList to end date of ev as string
            end repeat
        end tell
        set AppleScript's text item delimiters to linefeed
        return eventList as string
    end tell
    """
    ok, out = _run_applescript(script)
    if not ok:
        return []
    return _parse_event_lines(out)


def create(
    title: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    notes: str = "",
    calendar_name: str = "Calendar",
) -> bool:
    """Create a new calendar event. Times in ISO format or natural language."""
    start = start_time or "now"
    end = end_time or "in 1 hour"
    notes_escaped = notes.replace('"', '\\"').replace("\n", "\\n")

    script = f'''
    tell application "Calendar"
        tell calendar "{calendar_name}"
            set newEvent to make new event with properties {{summary:"{title}", start date:(date "{start}"), end date:(date "{end}"), description:"{notes_escaped}"}}
        end tell
    end tell
    '''
    ok, _ = _run_applescript(script)
    if ok:
        logger.info("Calendar event created: %s", title)
    return ok


def get_upcoming_text(days: int = 7) -> str:
    """Return a formatted text summary of upcoming events for context injection."""
    events = get_upcoming(days)
    if not events:
        return ""

    lines = ["## Upcoming Calendar Events"]
    for ev in events[:10]:
        title = ev.get("title", "")
        start = ev.get("start", "")
        lines.append(f"- {start}: {title}")
    return "\n".join(lines)


def is_available() -> bool:
    """Check if Calendar integration is available (macOS only)."""
    try:
        subprocess.run(["osascript", "-e", 'tell application "Calendar" to get name'], 
                       capture_output=True, timeout=5)
        return True
    except Exception:
        return False
