"""iMessage bridge — send/read via AppleScript on macOS.

Public API:
  send(phone_or_email, message) -> bool
  read_recent(limit) -> list[dict]
  is_available() -> bool
"""
from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger("kitty.imessage")


def _run_applescript(script: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        logger.warning("iMessage AppleScript failed: %s", result.stderr.strip())
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "osascript not available"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        logger.error("iMessage AppleScript error: %s", e)
        return False, str(e)


def _escape_applescript_string(text: str) -> str:
    """Escape backslash and double-quote for a plain AppleScript string literal."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _applescript_string_literal(message: str) -> str:
    """Build an AppleScript expression for ``message`` with real linefeeds.

    AppleScript string literals have no `\\n` escape — a literal backslash-n
    two-character sequence renders as-is instead of a newline. Multi-line
    text is built by joining per-line string literals with `& return &`.
    """
    lines = message.split("\n")
    quoted = [f'"{_escape_applescript_string(line)}"' for line in lines]
    return " & return & ".join(quoted)


def send(recipient: str, message: str) -> bool:
    """Send an iMessage. Recipient can be phone number or email.

    Targets the participant of the iMessage account directly rather than
    `buddy "<id>"`, which fails silently on modern Messages.app (exit 0, no
    message sent) — verified on Jacob's Air 2026-07-04. Requires Messages to
    be signed in and a conversation with the recipient to already exist.
    """
    message_expr = _applescript_string_literal(message)
    recipient_escaped = _escape_applescript_string(recipient)
    script = f'''
    tell application "Messages"
        set targetAccount to 1st account whose service type = iMessage
        send {message_expr} to participant "{recipient_escaped}" of targetAccount
    end tell
    '''
    ok, _ = _run_applescript(script)
    if ok:
        logger.info("iMessage sent to %s", recipient)
    return ok


def read_recent(limit: int = 10) -> list[dict]:
    """Read recent iMessages from the last active conversation."""
    script = (
        'tell application "Messages"\n'
        '    set output to {}\n'
        '    try\n'
        '        set targetChat to item 1 of (get every chat)\n'
        '        set recentMsgs to (messages of targetChat) as list\n'
        f'        set msgLimit to {limit}\n'
        '        if (count of recentMsgs) < msgLimit then set msgLimit to count of recentMsgs\n'
        '        repeat with i from 1 to msgLimit\n'
        '            set msg to item -i of recentMsgs\n'
        '            set msgSender to (get handle of msg) as string\n'
        '            set msgText to (get content of msg) as string\n'
        '            set msgTime to (date sent of msg) as «class isot»\n'
        '            set end of output to msgSender & "|||" & msgText & "|||" & msgTime\n'
        '        end repeat\n'
        '    end try\n'
        '    set AppleScript\'s text item delimiters to linefeed\n'
        '    return output as string\n'
        'end tell'
    )
    ok, out = _run_applescript(script)
    if not ok or not out:
        return []

    messages = []
    for line in out.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("|||", 2)
        if len(parts) == 3:
            messages.append({
                "sender": parts[0].strip(),
                "text": parts[1].strip(),
                "time": parts[2].strip(),
            })
    return messages


def is_available() -> bool:
    """Check if iMessage integration is available."""
    try:
        subprocess.run(
            ["osascript", "-e", 'tell application "Messages" to get name'],
            capture_output=True, timeout=5,
        )
        return True
    except Exception:
        return False


def get_recent_text(limit: int = 5) -> str:
    """Return a formatted snippet of recent iMessages for context injection."""
    if not is_available():
        return ""
    msgs = read_recent(limit)
    if not msgs:
        return ""
    lines = ["[Recent iMessages]"]
    for m in msgs:
        sender = m.get("sender", "?")
        text = m.get("text", "")[:100]
        lines.append(f"  {sender}: {text}")
    return "\n".join(lines)
