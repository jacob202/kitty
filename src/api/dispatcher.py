"""Command dispatcher — mirrors cli.py logic without Rich markup."""

import difflib
import logging
import re
import subprocess
import sys
import tempfile
import threading
from datetime import datetime as _dt
from pathlib import Path
from urllib.parse import urlparse

from src.api.emitters import emit_theme_change
from src.core.capabilities import (
    capability_snapshot,
    command_names,
    visible_help_commands,
)
from src.tools.skill_commands import get_skill, list_skills


def _screencapture(suffix: str = ".png") -> Path | None:
    """Take a screenshot with screencapture, return path or None on failure."""
    tmp = Path(tempfile.mktemp(suffix=suffix))
    subprocess.run(["screencapture", "-x", str(tmp)], capture_output=True)
    return tmp if tmp.exists() else None


logger = logging.getLogger(__name__)

# Thread safety lock for memory operations — must be module-level
# to be shared across threads. A local lock in dispatch() would be
# recreated on every call, defeating thread safety entirely.
_MEMORY_LOCK = threading.Lock()

# Loaded skills state — token-conscious: max 3 skills, injected via context dict
_loaded_skills: dict[str, str] = {}  # skill_name -> skill_content
_MAX_LOADED_SKILLS = 3

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

_AVAILABLE_COMMANDS = command_names()


def _validate_image_path(path: str) -> str | None:
    """Validate and resolve image path, returning sanitized path or None."""
    if not path:
        return None
    try:
        p = Path(path).resolve()
        if p.exists() and p.is_file():
            return str(p)
    except (OSError, ValueError):
        pass
    return None


def dispatch(
    inp: str,
    domain: str | None = None,
    sup=None,
    orch=None,
    fallback_chat=None,
    fallback_stream: bool = False,
    mode: str | None = None,
    reasoning: bool = False,
    model_target: str | None = None,
):
    """Handle commands and natural language, returning response object if NL."""
    inp = inp.strip()

    if not inp.startswith("/") or inp == "!!":
        if orch:
            try:
                # Inject loaded skills into context so they persist across NL queries
                context = {}
                if _loaded_skills:
                    context["active_skills"] = "\n\n".join(_loaded_skills.values())
                response = orch.process(
                    inp,
                    domain=domain,
                    context=context or None,
                    mode=mode,
                    reasoning=reasoning,
                    model_target=model_target,
                )
                if not getattr(response, "content", "").strip() and fallback_chat:
                    logger.warning("Orchestrator returned blank content; using web fallback")
                    return fallback_chat(inp, domain=domain, stream=fallback_stream)
                logger.debug("Orchestrator response: %s", response.content[:200])
                # In web mode, we need to print to stdout so TokenCapture picks it up
                sys.stdout.write(response.content + "\n")
                sys.stdout.flush()
                if response.safety_warnings:
                    for w in response.safety_warnings:
                        logger.warning("Safety warning: %s", w)
                return response
            except Exception:
                logger.exception("Orchestrator failed during dispatch")
        if fallback_chat:
            return fallback_chat(inp, domain=domain, stream=fallback_stream)
        if sup:
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
            tmp = _screencapture()
            if tmp:
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
            tmp = _screencapture()
            if tmp:
                sup.ocr_image(str(tmp))
                tmp.unlink(missing_ok=True)
            else:
                sys.stdout.write("Screenshot failed — grant Screen Recording permission.\n")
        else:
            safe_path = _validate_image_path(img)
            if safe_path:
                sup.ocr_image(safe_path)
            else:
                sys.stdout.write(f"Invalid or inaccessible image path: {img}\n")

    elif cmd == "/scrape":
        parts = inp.split(maxsplit=1)
        url = parts[1].strip().strip("'\"") if len(parts) > 1 else ""
        if url:
            try:
                parsed = urlparse(url)
                if parsed.scheme not in ("http", "https"):
                    sys.stdout.write("Only http/https URLs are allowed.\n")
                    return
                # Block requests to private/reserved IP ranges
                host = parsed.hostname or ""
                if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.endswith(".local"):
                    sys.stdout.write("Local network URLs are not allowed.\n")
                    return
                if re.match(r"^10\.|^172\.(1[6-9]|2[0-9]|3[0-1])\.|^192\.168\.", host):
                    sys.stdout.write("Private IP ranges are not allowed.\n")
                    return
            except Exception:
                sys.stdout.write("Invalid URL provided.\n")
                return
            sup.scrape_webpage(url)
        else:
            sys.stdout.write("Please provide a URL: /scrape <url>\n")

    elif cmd == "/repair":
        parts = inp.split(maxsplit=2)
        img = parts[1].strip("'\"") if len(parts) > 1 else ""
        context = parts[2] if len(parts) > 2 else ""
        if not img:
            tmp = _screencapture()
            if tmp:
                sup.repair_image(str(tmp), context)
                tmp.unlink(missing_ok=True)
            else:
                sys.stdout.write("Screenshot failed — grant Screen Recording permission.\n")
        else:
            safe_path = _validate_image_path(img)
            if safe_path:
                sup.repair_image(safe_path, context)
            else:
                sys.stdout.write(f"Invalid or inaccessible image path: {img}\n")

    elif cmd == "/image":
        parts = inp.split(maxsplit=2)
        img = parts[1].strip("'\"") if len(parts) > 1 else ""
        question = parts[2] if len(parts) > 2 else ""
        if not img:
            tmp = _screencapture()
            if tmp:
                sup.analyze_image(str(tmp), question)
                tmp.unlink(missing_ok=True)
        else:
            safe_path = _validate_image_path(img)
            if safe_path:
                sup.analyze_image(safe_path, question)
            else:
                sys.stdout.write(f"Invalid or inaccessible image path: {img}\n")

    elif cmd == "/capture":
        parts = inp.split(maxsplit=1)
        thought = parts[1] if len(parts) > 1 else ""
        if thought:
            ts = _dt.now().strftime("%Y-%m-%d %H:%M")
            key = f"capture_{_dt.now().strftime('%m%d_%H%M%S')}"
            with _MEMORY_LOCK:
                sup.memory.remember_fact(key, f"[{ts}] {thought}")
            sys.stdout.write(f"Captured: {thought}\n")

    elif cmd == "/remember":
        parts = inp.split(maxsplit=1)
        fact = parts[1] if len(parts) > 1 else ""
        if fact:
            key = "_".join(fact.lower().split()[:3]).rstrip(".,")
            with _MEMORY_LOCK:
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
        snapshot = capability_snapshot(
            enable_experimental_swarm=bool(getattr(sup, "config", {}).get("enable_experimental_swarm", False)),
            enable_internal_api=False,
        )
        sys.stdout.write(
            f"Specialists: {', '.join(s['name'] for s in sup.specialists)}\n"
        )
        sys.stdout.write(f"Tools: {', '.join(sup.tools)}\n")
        sys.stdout.write(f"Session cost: ${sup.session_cost:.4f}\n")
        mode = sup._active_mode
        mode_name = mode.get("name") if isinstance(mode, dict) else (mode or "none")
        sys.stdout.write(f"Work mode: {mode_name}\n")
        sys.stdout.write(
            "Capabilities: "
            f"{snapshot['commands']['visible_help_count']} visible, "
            f"{snapshot['commands']['beta_count']} beta, "
            f"{snapshot['commands']['internal_count']} internal\n"
        )
        mcp_summary = ", ".join(
            f"{name}={details['status']}"
            for name, details in snapshot["mcp"].items()
            if details["configured"]
        ) or "none"
        sys.stdout.write(f"Repo MCP: {mcp_summary}\n")
        swarm_state = "enabled" if snapshot["api"]["swarm"]["enabled"] else "hidden"
        sys.stdout.write(f"Experimental swarm API: {swarm_state}\n")

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

    elif cmd == "/skills":
        all_skills = list_skills()
        for name, info in all_skills.items():
            archived = " [archived]" if info.get("archived") else ""
            sys.stdout.write(f"  /skill {name:30s} {info['description']}{archived}\n")
        sys.stdout.write(f"\n{len(all_skills)} skills registered. Use /skill <name> to view details.\n")

    elif cmd == "/skill":
        parts = inp.split(maxsplit=1)
        skill_name = parts[1].strip() if len(parts) > 1 else ""
        if not skill_name:
            sys.stdout.write("Usage: /skill <name> — load a skill into context. Try /skills for the full list.\n")
        else:
            skill = get_skill(skill_name)
            if skill:
                if skill_name in _loaded_skills:
                    sys.stdout.write(f"Skill '{skill_name}' is already loaded.\n")
                elif len(_loaded_skills) >= _MAX_LOADED_SKILLS:
                    sys.stdout.write(
                        f"Cannot load '{skill_name}': max {_MAX_LOADED_SKILLS} skills loaded. "
                        f"Use /skill-unload <name> or /skill-clear first.\n"
                    )
                else:
                    _loaded_skills[skill_name] = skill["content"]
                    sys.stdout.write(
                        f"✅ Loaded skill: {skill['name']}\n"
                        f"   {skill['description']}\n"
                        f"   ({len(_loaded_skills)}/{_MAX_LOADED_SKILLS} slots used — "
                        f"will be injected into subsequent queries)\n"
                    )
            else:
                all_names = list(list_skills().keys())
                similar = difflib.get_close_matches(skill_name, all_names, n=3, cutoff=0.4)
                if similar:
                    sys.stdout.write(
                        f"Unknown skill: {skill_name}. Did you mean: {', '.join(similar)}?\n"
                    )
                else:
                    sys.stdout.write(f"Unknown skill: {skill_name}. Try /skills for the full list.\n")

    elif cmd == "/skill-unload":
        parts = inp.split(maxsplit=1)
        skill_name = parts[1].strip() if len(parts) > 1 else ""
        if not skill_name:
            sys.stdout.write("Usage: /skill-unload <name> — remove a loaded skill from context.\n")
        elif skill_name not in _loaded_skills:
            loaded = ", ".join(_loaded_skills) if _loaded_skills else "(none)"
            sys.stdout.write(f"Skill '{skill_name}' is not loaded. Currently loaded: {loaded}\n")
        else:
            del _loaded_skills[skill_name]
            sys.stdout.write(f"Unloaded skill: {skill_name}\n")

    elif cmd == "/skill-clear":
        count = len(_loaded_skills)
        _loaded_skills.clear()
        sys.stdout.write(f"Cleared {count} loaded skills.\n")

    elif cmd == "/skill-loaded":
        if not _loaded_skills:
            sys.stdout.write("No skills currently loaded. Use /skill <name> to load one.\n")
        else:
            sys.stdout.write(f"Loaded skills ({len(_loaded_skills)}/{_MAX_LOADED_SKILLS}):\n")
            for name in _loaded_skills:
                sys.stdout.write(f"  · {name}\n")

    elif cmd == "/help":
        lines = ["**Commands**"]
        for info in visible_help_commands():
            lines.append(f"- `{info.command}` — {info.description}")
        lines.append("- `!!` — re-run last query escalated to next model tier")
        lines.append("")
        lines.append(f"Registered skills: {len(list_skills())}")
        lines.append("Advanced commands are intentionally hidden from this list until they are production-safe.")
        sys.stdout.write("\n".join(lines) + "\n")

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
