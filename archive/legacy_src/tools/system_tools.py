"""
System tools: shell execution, file ops, macOS app control, server/HTTP access.
Destructive operations (rm, overwrite, kill, close app) pause and ask the user.
"""
import re
import subprocess
from pathlib import Path

import requests

HOME = str(Path.home())

# Commands / patterns that require user confirmation before running
_DESTRUCTIVE = [
    r'\brm\b', r'\brmdir\b', r'\brmrf\b',
    r'\bkill\b', r'\bpkill\b', r'\bkillall\b',
    r'\btruncate\b', r'\bformat\b', r'\bpurge\b',
    r'(?<![>])>\s*\S',          # single-redirect overwrite  (but not >>)
    r'\bsudo\b',
    r'\bdd\b.*of=',
    r'\bmkfs\b',
]

def _is_destructive(cmd: str) -> bool:
    return any(re.search(p, cmd, re.IGNORECASE) for p in _DESTRUCTIVE)


# ── Shell ──────────────────────────────────────────────────────────────────────
class ShellTool:
    """Run shell commands. Confirmation required for destructive ops."""

    def execute(self, command: str, confirm_func=None) -> str:
        if _is_destructive(command):
            if confirm_func and not confirm_func(f"Destructive command:\n  {command}"):
                return "Cancelled by user."
        try:
            r = subprocess.run(
                command, shell=True, capture_output=True,
                text=True, cwd=HOME, timeout=30,
            )
            out = r.stdout.strip()
            err = r.stderr.strip()
            if r.returncode != 0:
                return f"[exit {r.returncode}] {err or out}"
            return out or "(completed, no output)"
        except subprocess.TimeoutExpired:
            return "Timed out (30 s)."
        except Exception as e:
            return f"Error: {e}"


# ── File ───────────────────────────────────────────────────────────────────────
class FileTool:
    """Read, write, list files under the home directory."""

    def read(self, path: str, max_lines: int = 150) -> str:
        p = Path(path).expanduser()
        if not p.exists():
            return f"Not found: {path}"
        try:
            lines = p.read_text(errors="replace").splitlines()
            preview = "\n".join(lines[:max_lines])
            if len(lines) > max_lines:
                preview += f"\n… ({len(lines) - max_lines} more lines)"
            return preview
        except Exception as e:
            return f"Read error: {e}"

    def write(self, path: str, content: str, confirm_func=None) -> str:
        p = Path(path).expanduser()
        if p.exists() and confirm_func:
            if not confirm_func(f"Overwrite existing file: {path}"):
                return "Cancelled by user."
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"Written: {path} ({len(content):,} chars)"
        except Exception as e:
            return f"Write error: {e}"

    def list(self, path: str = "~/Desktop", pattern: str = "*") -> str:
        # Bare ~ is too noisy — default to Desktop which is what users actually mean
        if path in ("~", str(Path.home()), "home", "/home"):
            path = "~/Desktop"
        p = Path(path).expanduser()
        if not p.exists():
            # Try various path normalizations (model often gives Linux paths)
            candidates = [
                Path("~" + path).expanduser() if path.startswith("/") else None,
                Path(f"~/{path}").expanduser(),
                # Handle /home/user/Folder → ~/Folder
                Path("~/" + "/".join(Path(path).parts[3:])).expanduser() if len(Path(path).parts) > 3 else None,
            ]
            resolved = next((c for c in candidates if c and c.exists()), None)
            if resolved:
                p = resolved
            else:
                return f"Not found: {path}"
        items = sorted(p.glob(pattern))[:60]
        rows  = [f"{'DIR  ' if i.is_dir() else 'FILE '}{i.name}" for i in items]
        return "\n".join(rows) or "(empty)"


# ── App ────────────────────────────────────────────────────────────────────────
class AppTool:
    """Open, close, list, and control macOS apps via AppleScript."""

    def open(self, app: str) -> str:
        r = subprocess.run(["open", "-a", app], capture_output=True, text=True)
        return f"Opened: {app}" if r.returncode == 0 else f"Error: {r.stderr.strip()}"

    def close(self, app: str, confirm_func=None) -> str:
        if confirm_func and not confirm_func(f"Close app '{app}'"):
            return "Cancelled by user."
        r = subprocess.run(
            ["osascript", "-e", f'tell application "{app}" to quit'],
            capture_output=True, text=True,
        )
        return f"Closed: {app}" if r.returncode == 0 else f"Error: {r.stderr.strip()}"

    def list_running(self) -> str:
        r = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of every process where background only is false'],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            return ", ".join(sorted(a.strip() for a in r.stdout.strip().split(",")))
        return "Could not list running apps."

    def applescript(self, script: str) -> str:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        return r.stdout.strip() or r.stderr.strip() or "(done)"



# ── Obsidian ───────────────────────────────────────────────────────────────────
class ObsidianTool:
    """Read, write, and search notes in an Obsidian vault (direct filesystem)."""

    def __init__(self, vault_path: str = ""):
        self.vault = Path(vault_path).expanduser() if vault_path else None

    def _check(self) -> str | None:
        if not self.vault or not self.vault.exists():
            return "Obsidian vault path not configured. Set obsidian_vault_path in config/config.json."
        return None

    def create_note(self, path: str, content: str) -> str:
        err = self._check()
        if err: return err
        note = self.vault / (path if path.endswith(".md") else path + ".md")
        try:
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text(content)
            return f"Note created: {path}"
        except Exception as e:
            return f"Error: {e}"

    def append_note(self, path: str, content: str) -> str:
        err = self._check()
        if err: return err
        note = self.vault / (path if path.endswith(".md") else path + ".md")
        try:
            existing = note.read_text() if note.exists() else ""
            separator = "\n" if existing.endswith("\n") else "\n\n"
            note.write_text(existing + separator + content)
            return f"Appended to: {path}"
        except Exception as e:
            return f"Error: {e}"

    def read_note(self, path: str) -> str:
        err = self._check()
        if err: return err
        note = self.vault / (path if path.endswith(".md") else path + ".md")
        if not note.exists():
            return f"Note not found: {path}"
        try:
            return note.read_text()
        except Exception as e:
            return f"Error: {e}"

    def search_notes(self, query: str) -> str:
        err = self._check()
        if err: return err
        try:
            r = subprocess.run(
                ["grep", "-rl", "--include=*.md", query, str(self.vault)],
                capture_output=True, text=True, timeout=10,
            )
            if not r.stdout.strip():
                return f"No notes found matching: {query}"
            paths = r.stdout.strip().split("\n")[:15]
            return "\n".join(str(Path(p).relative_to(self.vault)) for p in paths)
        except Exception as e:
            return f"Search error: {e}"

    def list_notes(self, folder: str = "") -> str:
        err = self._check()
        if err: return err
        base = (self.vault / folder) if folder else self.vault
        if not base.exists():
            return f"Folder not found: {folder}"
        notes = sorted(base.rglob("*.md"))[:40]
        return "\n".join(str(n.relative_to(self.vault)) for n in notes) or "(empty)"


# ── Calendar ──────────────────────────────────────────────────────────────────
class CalendarTool:
    """List and create macOS Calendar events via AppleScript."""

    def list_events(self, days_ahead: int = 7) -> str:
        script = f"""
set output to ""
set today to current date
set today's time to 0
set endDate to today + ({days_ahead} * days)
tell application "Calendar"
    repeat with aCal in every calendar
        set calName to name of aCal
        repeat with anEvent in (every event of aCal whose start date >= today and start date <= endDate)
            set evTitle to summary of anEvent
            set evStart to start date of anEvent as string
            set output to output & calName & ": " & evTitle & " - " & evStart & linefeed
        end repeat
    end repeat
end tell
return output
"""
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
        result = r.stdout.strip()
        if not result and r.returncode != 0:
            return f"Calendar error: {r.stderr.strip()}"
        return result or "(no upcoming events)"

    def create_event(self, title: str, start: str, duration_minutes: int = 60,
                     calendar: str = "", notes: str = "") -> str:
        """Create event. start format: 'YYYY-MM-DD HH:MM'"""
        from datetime import datetime as _dt
        try:
            dt = _dt.strptime(start, "%Y-%m-%d %H:%M")
        except ValueError:
            return "Invalid start format. Use: YYYY-MM-DD HH:MM"
        cal_clause = f'calendar "{calendar}"' if calendar else "default calendar"
        notes_line = f'\n            set description of newEvent to "{notes}"' if notes else ""
        as_date    = dt.strftime("%A, %B %d, %Y at %I:%M:%S %p")
        script = f"""
set startDate to date "{as_date}"
set endDate to startDate + ({duration_minutes} * minutes)
tell application "Calendar"
    tell {cal_clause}
        set newEvent to make new event with properties {{summary: "{title}", start date: startDate, end date: endDate}}{notes_line}
        reload calendars
    end tell
end tell
return "Created: {title}"
"""
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return f"Calendar error: {r.stderr.strip()}"
        return r.stdout.strip() or f"Event created: {title}"


# ── Reminders ─────────────────────────────────────────────────────────────────
class RemindersTool:
    """Create macOS Reminders via AppleScript — these actually fire as notifications."""

    def create(self, title: str, remind_at: str = "", notes: str = "") -> str:
        """Create a reminder. remind_at format: 'YYYY-MM-DD HH:MM' or 'HH:MM' for today."""
        from datetime import date as _date
        from datetime import datetime as _dt
        date_part = ""
        if remind_at:
            try:
                if len(remind_at) <= 5:  # HH:MM only
                    remind_at = f"{_date.today().isoformat()} {remind_at}"
                dt       = _dt.strptime(remind_at, "%Y-%m-%d %H:%M")
                as_date  = dt.strftime("%A, %B %d, %Y at %I:%M:%S %p")
                date_part = f'\n    set remind me date of newReminder to date "{as_date}"'
            except ValueError:
                pass
        notes_part = f'\n    set body of newReminder to "{notes}"' if notes else ""
        script = f"""
tell application "Reminders"
    set newReminder to make new reminder with properties {{name: "{title}"}}
    {date_part}{notes_part}
end tell
return "Reminder created."
"""
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return f"Reminder error: {r.stderr.strip()}"
        return r.stdout.strip() or f"✓ Reminder set: {title}" + (f" at {remind_at}" if remind_at else "")


# ── Messages ──────────────────────────────────────────────────────────────────
class MessagesTool:
    """Send iMessages and read recent messages via AppleScript / SQLite."""

    def send(self, to: str, text: str, confirm_func=None) -> str:
        if confirm_func and not confirm_func(f"Send iMessage to {to}:\n  {text}"):
            return "Cancelled by user."
        script = f"""
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "{to}" of targetService
    send "{text}" to targetBuddy
end tell
return "Sent."
"""
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return f"Messages error: {r.stderr.strip()}"
        return r.stdout.strip() or "Message sent."

    def recent(self, count: int = 10) -> str:
        db = Path.home() / "Library/Messages/chat.db"
        if not db.exists():
            return "Messages database not found."
        try:
            import sqlite3
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            cur = con.execute(f"""
                SELECT datetime(m.date/1000000000 + 978307200,'unixepoch','localtime'),
                       h.id, m.text
                FROM message m
                JOIN handle h ON m.handle_id = h.ROWID
                WHERE m.text IS NOT NULL
                ORDER BY m.date DESC LIMIT {int(count)}
            """)
            rows = cur.fetchall()
            con.close()
            return "\n".join(f"{r[0]} | {r[1]}: {r[2]}" for r in rows) or "(no messages)"
        except Exception as e:
            return f"Error reading Messages DB: {e}"


# ── Server / HTTP ──────────────────────────────────────────────────────────────
class ServerTool:
    KNOWN = {
        "ollama":      "http://localhost:11434",
        "n8n":         "http://localhost:5678",
        "draw_things": "http://127.0.0.1:7859",
    }

    def status(self, service: str = None) -> str:
        targets = {service: self.KNOWN.get(service, service)} if service else self.KNOWN
        lines   = []
        for name, url in targets.items():
            try:
                r = requests.get(url, timeout=3)
                lines.append(f"  [up]   {name}  {url}  HTTP {r.status_code}")
            except Exception:
                lines.append(f"  [down] {name}  {url}")
        return "\n".join(lines)

    def request(self, url: str, method: str = "GET", body: dict = None, headers: dict = None) -> str:
        try:
            resp = requests.request(method.upper(), url, json=body, headers=headers or {}, timeout=15)
            ct   = resp.headers.get("content-type", "")
            if "html" in ct or resp.text.strip().startswith("<!"):
                # Strip HTML — extract visible text only
                import re as _re
                text = _re.sub(r'<script[^>]*>.*?</script>', '', resp.text, flags=_re.DOTALL | _re.IGNORECASE)
                text = _re.sub(r'<style[^>]*>.*?</style>',  '', text,      flags=_re.DOTALL | _re.IGNORECASE)
                text = _re.sub(r'<[^>]+>', ' ', text)
                text = _re.sub(r'\s{3,}', '\n', text).strip()
                return f"HTTP {resp.status_code}\n{text[:1500]}"
            if "json" in ct:
                import json as _json
                try:
                    return f"HTTP {resp.status_code}\n{_json.dumps(resp.json(), indent=2)[:2000]}"
                except Exception:
                    pass
            return f"HTTP {resp.status_code}\n{resp.text[:2000]}"
        except Exception as e:
            return f"Request error: {e}"
