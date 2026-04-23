"""Command dispatcher — mirrors cli.py logic without Rich markup."""

import difflib
import logging
import subprocess
import sys
import tempfile
import threading
from datetime import datetime as _dt
from pathlib import Path

from src.api.emitters import emit_theme_change

logger = logging.getLogger(__name__)

_MODE_CTX = {
    "sansui": "Currently working on Sansui AU-7900 integrated amplifier repair.",
    "ridgeline": "Currently diagnosing 2007 Honda Ridgeline RTL. Primary issue: Bank 2 lean.",
    "heathkit": "Currently working on Heathkit tube amplifier restoration.",
    "hardware": "Hardware analysis and repair mode.",
    "investigative": "Investigative research and analysis mode.",
    "self": "Self-improvement and reflection mode.",
}

_THEME_MAP = {
    "hardware": "hardware",
    "investigative": "investigative",
    "self": "self-improvement",
    "sansui": "hardware",
    "ridgeline": "hardware",
    "heathkit": "hardware",
}

_AVAILABLE_COMMANDS = [
    "/brief", "/stuck", "/bench", "/prep", "/capture", "/review",
    "/screen", "/repair", "/image", "/deepsearch", "/help", "/status",
]


def dispatch(inp: str, domain: str | None = None, sup=None, orch=None):
    """Handle commands and natural language, returning response object if NL."""
    _memory_lock = threading.Lock()
    inp = inp.strip()

    if not inp.startswith("/") or inp == "!!":
        if orch:
            try:
                response = orch.process(inp, domain=domain)
                logger.debug("Orchestrator response: %s", response.content[:200])
                if response.safety_warnings:
                    for w in response.safety_warnings:
                        logger.warning("Safety warning: %s", w)
                return response
            except Exception:
                pass
        sup.run(inp)
        return None

    cmd = inp.split()[0].lower()

    if cmd == "/brief":
        sup.morning_brief()

    elif cmd == "/stuck":
        parts = inp.split(maxsplit=1)
        emit_theme_change("self-improvement")
        sup.stuck_recovery(parts[1] if len(parts) > 1 else "")

    elif cmd == "/bench":
        parts = inp.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""
        if not arg or arg.lower() in ("off", "clear"):
            sup.clear_mode()
            emit_theme_change("hardware")
            sys.stdout.write("Work mode cleared.\n")
        else:
            ctx = _MODE_CTX.get(arg.lower(), f"Working on: {arg}")
            sup.set_mode(arg, ctx)
            theme = _THEME_MAP.get(arg.lower(), "hardware")
            emit_theme_change(theme)
            sys.stdout.write(f"Work mode set: {arg}\n")

    elif cmd == "/prep":
        sup.prescriber_prep()

    elif cmd == "/optic":
        parts = inp.split(maxsplit=1)
        question = parts[1] if len(parts) > 1 else ""
        q_lower = question.lower()
        if any(w in q_lower for w in ["read", "text", "ocr", "transcribe", "words"]):
            tmp = Path(tempfile.mktemp(suffix=".png"))
            subprocess.run(["screencapture", "-x", str(tmp)], capture_output=True)
            if tmp.exists():
                sup.ocr_image(str(tmp))
                tmp.unlink(missing_ok=True)
            else:
                sys.stdout.write("Screenshot failed.\n")
        else:
            sup.screen_capture(question)

    elif cmd == "/screen":
        parts = inp.split(maxsplit=1)
        question = parts[1] if len(parts) > 1 else ""
        sup.screen_capture(question)

    elif cmd == "/ocr":
        parts = inp.split(maxsplit=1)
        img = parts[1].strip("'\"") if len(parts) > 1 else ""
        if not img:
            tmp = Path(tempfile.mktemp(suffix=".png"))
            subprocess.run(["screencapture", "-x", str(tmp)], capture_output=True)
            if tmp.exists():
                sup.ocr_image(str(tmp))
                tmp.unlink(missing_ok=True)
            else:
                sys.stdout.write("Screenshot failed — grant Screen Recording permission.\n")
        else:
            sup.ocr_image(img)

    elif cmd == "/scrape":
        parts = inp.split(maxsplit=1)
        url = parts[1].strip() if len(parts) > 1 else ""
        if url:
            sup.scrape_webpage(url)
        else:
            sys.stdout.write("Please provide a URL: /scrape <url>\n")

    elif cmd == "/repair":
        parts = inp.split(maxsplit=2)
        img = parts[1].strip("'\"") if len(parts) > 1 else ""
        context = parts[2] if len(parts) > 2 else ""
        if not img:
            tmp = Path(tempfile.mktemp(suffix=".png"))
            subprocess.run(["screencapture", "-x", str(tmp)], capture_output=True)
            if tmp.exists():
                sup.repair_image(str(tmp), context)
                tmp.unlink(missing_ok=True)
            else:
                sys.stdout.write("Screenshot failed — grant Screen Recording permission.\n")
        else:
            sup.repair_image(img, context)

    elif cmd == "/image":
        parts = inp.split(maxsplit=2)
        img = parts[1].strip("'\"") if len(parts) > 1 else ""
        question = parts[2] if len(parts) > 2 else ""
        if not img:
            tmp = Path(tempfile.mktemp(suffix=".png"))
            subprocess.run(["screencapture", "-x", str(tmp)], capture_output=True)
            if tmp.exists():
                sup.analyze_image(str(tmp), question)
                tmp.unlink(missing_ok=True)
        else:
            sup.analyze_image(img, question)

    elif cmd == "/capture":
        parts = inp.split(maxsplit=1)
        thought = parts[1] if len(parts) > 1 else ""
        if thought:
            ts = _dt.now().strftime("%Y-%m-%d %H:%M")
            key = f"capture_{_dt.now().strftime('%m%d_%H%M%S')}"
            with _memory_lock:
                sup.memory.remember_fact(key, f"[{ts}] {thought}")
            sys.stdout.write(f"Captured: {thought}\n")

    elif cmd == "/remember":
        parts = inp.split(maxsplit=1)
        fact = parts[1] if len(parts) > 1 else ""
        if fact:
            key = "_".join(fact.lower().split()[:3]).rstrip(".,")
            with _memory_lock:
                sup.memory.remember_fact(key, fact)
            sys.stdout.write(f"Remembered: {fact}\n")

    elif cmd == "/review":
        facts = sup.memory.get_facts()
        caps = {k: v for k, v in facts.items() if k.startswith("capture_")}
        other = {k: v for k, v in facts.items() if not k.startswith("capture_")}
        if caps:
            sys.stdout.write("Your captures:\n")
            for v in caps.values():
                sys.stdout.write(f"  · {v}\n")
        if other:
            sys.stdout.write("\nSaved facts:\n")
            for k, v in other.items():
                sys.stdout.write(f"  · {v}\n")
        obd = sup.memory.data.get("obd_health", "")
        if obd:
            sys.stdout.write(f"\nOBD health: {obd}\n")
        if not caps and not other and not obd:
            sys.stdout.write("Nothing saved yet. Type /capture to save a thought.\n")

    elif cmd == "/cal":
        parts = inp.split(maxsplit=1)
        arg = (parts[1] if len(parts) > 1 else "").strip()
        try:
            days = int(arg) if arg and arg.isdigit() else 7
        except ValueError:
            days = 7
        result = sup.tools["calendar_list"].list_events(days)
        sys.stdout.write(result + "\n")

    elif cmd == "/deepsearch":
        parts = inp.split(maxsplit=1)
        if len(parts) > 1:
            emit_theme_change("investigative")
            sup.deep_search(parts[1].strip())

    elif cmd == "/status":
        sys.stdout.write(
            f"Specialists: {', '.join(s['name'] for s in sup.specialists)}\n"
        )
        sys.stdout.write(f"Tools: {', '.join(sup.tools)}\n")
        sys.stdout.write(f"Session cost: ${sup.session_cost:.4f}\n")
        mode = sup._active_mode
        sys.stdout.write(f"Work mode: {mode['name'] if mode else 'none'}\n")

    elif cmd == "/clear":
        sup.history = []
        sup.save_session()
        sys.stdout.write("Conversation cleared.\n")

    elif cmd == "/watch":
        parts = inp.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else "on"
        if arg == "off":
            sys.stdout.write(sup.screen_watch_stop() + "\n")
        else:
            try:
                interval = int(arg)
            except ValueError:
                interval = 30
            sys.stdout.write(sup.screen_watch_start(interval=interval) + "\n")

    elif cmd == "/council":
        parts = inp.split(maxsplit=1)
        context = parts[1].strip() if len(parts) > 1 else ""
        if context:
            sup.assemble_council(context)
        else:
            sys.stdout.write("Please provide a topic for the Council: /council <topic>\n")

    elif cmd == "/help":
        sys.stdout.write(
            "**Commands**\n"
            "- `/brief` — morning brief, where you left off\n"
            "- `/stuck [task]` — ADHD rescue: one next physical step\n"
            "- `/bench [mode|off]` — set work mode (sansui, ridgeline, heathkit, or custom)\n"
            "- `/council <topic>` — dynamic expert panel for deep-dive debates\n"
            "- `/capture <thought>` — quick brain dump\n"
            "- `/review` — show captures, saved facts, OBD health\n"
            "- `/remember <fact>` — save a persistent fact\n"
            "- `/forget <key>` — remove a saved fact\n"
            "- `/memories` — list all saved facts\n"
            "- `/ingest [path]` — ingest PDF/EPUB into library\n"
            "- `/library` — list indexed documents\n"
            "- `/deepsearch [--depth N] <query>` — web search + optional crawl + synthesis\n"
            "- `/screen [question]` — screenshot + vision analysis\n"
            "- `/repair <photo> [context]` — repair photo analysis\n"
            "- `/image <photo> [question]` — vision question\n"
            "- `/clip` — load clipboard as context\n"
            "- `/paste` — multi-line input mode\n"
            "- `/export` — save session to ~/Documents/Kitty/exports/\n"
            "- `/status` — show models, tools, cost\n"
            "- `/history` — conversation turns this session\n"
            "- `/clear` — clear conversation history\n"
            "- `/cal [days]` — list upcoming calendar events\n"
            "- `/watch [on|off|30]` — continuous screen watcher\n"
            "- `/debug` — toggle routing debug info\n"
            "- `!!` — re-run last query escalated to next model tier\n"
        )

    else:
        try:
            if inp.startswith("/") and len(inp) > 1:
                similar = difflib.get_close_matches(
                    inp.split()[0], _AVAILABLE_COMMANDS, n=3, cutoff=0.6
                )
                if similar:
                    sys.stdout.write(
                        f"Unknown command: {inp.split()[0]}. Did you mean: {', '.join(similar)}?\n"
                    )
                else:
                    sys.stdout.write(
                        f"Unknown command: {inp.split()[0]}. Type /help for available commands.\n"
                    )
                return

            sup.run(inp)

        except Exception as e:
            logger.error("Dispatch error: %s", e)
            sys.stdout.write("Error processing request. Try: Use /help for commands, or rephrase your request.\n")
