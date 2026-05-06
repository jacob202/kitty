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
from src.core.command_engine import CommandResult, get_command_engine
from src.tools.skill_commands import get_skill, list_skills


def _screencapture(suffix: str = ".png") -> Path | None:
    tmp = Path(tempfile.mktemp(suffix=suffix))
    subprocess.run(["screencapture", "-x", str(tmp)], capture_output=True)
    return tmp if tmp.exists() else None


logger = logging.getLogger(__name__)

_MEMORY_LOCK = threading.Lock()

_loaded_skills: dict[str, str] = {}
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
    if not path:
        return None
    try:
        p = Path(path).resolve()
        if p.exists() and p.is_file():
            return str(p)
    except (OSError, ValueError):
        pass
    return None


def _ensure_commands_registered(sup):
    """Register all slash commands with the engine. Idempotent — skips if already registered."""
    engine = get_command_engine()
    if engine.visible_count() > 2:
        return

    def handle_help(args: str, **ctx):
        lines = ["**Commands**"]
        for info in visible_help_commands():
            lines.append(f"- `{info.command}` — {info.description}")
        lines.append("- `!!` — re-run last query escalated to next model tier")
        lines.append("")
        lines.append(f"Registered skills: {len(list_skills())}")
        lines.append("Advanced commands are intentionally hidden from this list until they are production-safe.")
        return CommandResult(success=True, message="\n".join(lines))

    def handle_brief(args: str, **ctx):
        sup = ctx["sup"]
        sup.morning_brief()
        return CommandResult(success=True)

    def handle_stuck(args: str, **ctx):
        sup = ctx["sup"]
        emit_theme_change("self-improvement")
        sup.stuck_recovery(args if args else "")
        return CommandResult(success=True)

    def handle_bench(args: str, **ctx):
        sup = ctx["sup"]
        arg = args.strip()
        if not arg or arg.lower() in ("off", "clear"):
            sup.clear_mode()
            emit_theme_change("hardware")
            return CommandResult(success=True, message="Work mode cleared.")
        ctx_desc = _MODE_CTX.get(arg.lower(), f"Working on: {arg}")
        sup.set_mode(arg, ctx_desc)
        theme = _THEME_MAP.get(arg.lower(), "hardware")
        emit_theme_change(theme)
        return CommandResult(success=True, message=f"Work mode set: {arg}")

    def handle_screen(args: str, **ctx):
        sup = ctx["sup"]
        question = args
        sup.screen_capture(question)
        return CommandResult(success=True)

    def handle_scrape(args: str, **ctx):
        sup = ctx["sup"]
        url = args.strip().strip("'\"")
        if not url:
            return CommandResult(success=False, error="Please provide a URL: /scrape <url>")
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return CommandResult(success=False, error="Only http/https URLs are allowed.")
            host = parsed.hostname or ""
            if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.endswith(".local"):
                return CommandResult(success=False, error="Local network URLs are not allowed.")
            if re.match(r"^10\.|^172\.(1[6-9]|2[0-9]|3[0-1])\.|^192\.168\.", host):
                return CommandResult(success=False, error="Private IP ranges are not allowed.")
        except Exception:
            return CommandResult(success=False, error="Invalid URL provided.")
        sup.scrape_webpage(url)
        return CommandResult(success=True)

    def handle_capture(args: str, **ctx):
        sup = ctx["sup"]
        thought = args
        if thought:
            ts = _dt.now().strftime("%Y-%m-%d %H:%M")
            key = f"capture_{_dt.now().strftime('%m%d_%H%M%S')}"
            with _MEMORY_LOCK:
                sup.memory.remember_fact(key, f"[{ts}] {thought}")
            return CommandResult(success=True, message=f"Captured: {thought}")
        return CommandResult(success=False)

    def handle_remember(args: str, **ctx):
        sup = ctx["sup"]
        fact = args
        if fact:
            key = "_".join(fact.lower().split()[:3]).rstrip(".,")
            with _MEMORY_LOCK:
                sup.memory.remember_fact(key, fact)
            return CommandResult(success=True, message=f"Remembered: {fact}")
        return CommandResult(success=False)

    def handle_review(args: str, **ctx):
        sup = ctx["sup"]
        facts = sup.memory.get_facts()
        caps = {k: v for k, v in facts.items() if k.startswith("capture_")}
        other = {k: v for k, v in facts.items() if not k.startswith("capture_")}
        lines = []
        if caps:
            lines.append("Your captures:")
            for v in caps.values():
                lines.append(f"  · {v}")
        if other:
            lines.append("\nSaved facts:")
            for k, v in other.items():
                lines.append(f"  · {v}")
        obd = sup.memory.data.get("obd_health", "")
        if obd:
            lines.append(f"\nOBD health: {obd}")
        if not caps and not other and not obd:
            return CommandResult(success=True, message="Nothing saved yet. Type /capture to save a thought.")
        return CommandResult(success=True, message="\n".join(lines))

    def handle_deepsearch(args: str, **ctx):
        sup = ctx["sup"]
        if args:
            emit_theme_change("investigative")
            sup.deep_search(args)
        return CommandResult(success=True)

    def handle_status(args: str, **ctx):
        sup = ctx["sup"]
        snapshot = capability_snapshot(
            enable_experimental_swarm=bool(getattr(sup, "config", {}).get("enable_experimental_swarm", False)),
            enable_internal_api=False,
        )
        lines = [
            f"Specialists: {', '.join(s['name'] for s in sup.specialists)}",
            f"Tools: {', '.join(sup.tools)}",
            f"Session cost: ${sup.session_cost:.4f}",
        ]
        mode = sup._active_mode
        mode_name = mode.get("name") if isinstance(mode, dict) else (mode or "none")
        lines.append(f"Work mode: {mode_name}")
        lines.append(
            f"Capabilities: "
            f"{snapshot['commands']['visible_help_count']} visible, "
            f"{snapshot['commands']['beta_count']} beta, "
            f"{snapshot['commands']['internal_count']} internal"
        )
        mcp_summary = ", ".join(
            f"{name}={details['status']}"
            for name, details in snapshot["mcp"].items()
            if details["configured"]
        ) or "none"
        lines.append(f"Repo MCP: {mcp_summary}")
        swarm_state = "enabled" if snapshot["api"]["swarm"]["enabled"] else "hidden"
        lines.append(f"Experimental swarm API: {swarm_state}")
        return CommandResult(success=True, message="\n".join(lines))

    def handle_clear(args: str, **ctx):
        sup = ctx["sup"]
        sup.history = []
        sup.save_session()
        return CommandResult(success=True, message="Conversation cleared.")

    def handle_council(args: str, **ctx):
        sup = ctx["sup"]
        if args:
            sup.assemble_council(args)
            return CommandResult(success=True)
        return CommandResult(success=False, error="Please provide a topic for the Council: /council <topic>")

    def handle_prep(args: str, **ctx):
        ctx["sup"].prescriber_prep()
        return CommandResult(success=True)

    def handle_optic(args: str, **ctx):
        sup = ctx["sup"]
        question = args
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
        return CommandResult(success=True)

    def handle_ocr(args: str, **ctx):
        sup = ctx["sup"]
        img = args.strip().strip("'\"")
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
        return CommandResult(success=True)

    def handle_repair(args: str, **ctx):
        sup = ctx["sup"]
        parts = args.split(maxsplit=1)
        img = parts[0].strip().strip("'\"") if parts else ""
        context = parts[1] if len(parts) > 1 else ""
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
        return CommandResult(success=True)

    def handle_image(args: str, **ctx):
        sup = ctx["sup"]
        parts = args.split(maxsplit=1)
        img = parts[0].strip().strip("'\"") if parts else ""
        question = parts[1] if len(parts) > 1 else ""
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
        return CommandResult(success=True)

    def handle_cal(args: str, **ctx):
        sup = ctx["sup"]
        arg = args.strip()
        try:
            days = int(arg) if arg and arg.isdigit() else 7
        except ValueError:
            days = 7
        result = sup.tools["calendar_list"].list_events(days)
        return CommandResult(success=True, message=result)

    def handle_watch(args: str, **ctx):
        sup = ctx["sup"]
        arg = args.strip() or "on"
        if arg == "off":
            return CommandResult(success=True, message=sup.screen_watch_stop())
        try:
            interval = int(arg)
        except ValueError:
            interval = 30
        return CommandResult(success=True, message=sup.screen_watch_start(interval=interval))

    def handle_skills(args: str, **ctx):
        lines = [
            "\n── Chained Skills ──",
            "orient     health → architecture → current state",
            "research   search → scrape → interaction → synthesis",
            "plan       ideate → design → grill → zoom-out",
            "build      find → test → implement → review → verify",
            "ship       demo → checklist → gate → go/no-go",
            "optimize   token audit → compression → report",
            "handoff    capture → accounting → update docs → commit",
            "",
            "── CLI Tools ──",
            "firecrawl       web search + scrape",
            "agent-browser   browser automation",
            "ast-grep        code search",
            "",
            f"Use /skill <name> to load one into context. {len(_loaded_skills)}/{_MAX_LOADED_SKILLS} loaded.",
        ]
        if _loaded_skills:
            lines.append("\n── Loaded ──")
            for name in _loaded_skills:
                lines.append(f"  · {name}")
        return CommandResult(success=True, message="\n".join(lines))

    def handle_skill(args: str, **ctx):
        skill_name = args.strip()
        if not skill_name:
            return CommandResult(success=False, error="Usage: /skill <name> — load a skill into context. Try /skills for the full list.")
        skill = get_skill(skill_name)
        if skill:
            if skill_name in _loaded_skills:
                return CommandResult(success=True, message=f"Skill '{skill_name}' is already loaded.")
            elif len(_loaded_skills) >= _MAX_LOADED_SKILLS:
                return CommandResult(success=False, error=f"Cannot load '{skill_name}': max {_MAX_LOADED_SKILLS} skills loaded. Use /skill-unload <name> or /skill-clear first.")
            else:
                _loaded_skills[skill_name] = skill["content"]
                return CommandResult(success=True, message=f"✅ Loaded skill: {skill['name']}\n   {skill['description']}\n   ({len(_loaded_skills)}/{_MAX_LOADED_SKILLS} slots used)")
        else:
            all_names = list(list_skills().keys())
            similar = difflib.get_close_matches(skill_name, all_names, n=3, cutoff=0.4)
            if similar:
                return CommandResult(success=False, error=f"Unknown skill: {skill_name}. Did you mean: {', '.join(similar)}?")
            return CommandResult(success=False, error=f"Unknown skill: {skill_name}. Try /skills for the full list.")

    def handle_skill_unload(args: str, **ctx):
        skill_name = args.strip()
        if not skill_name:
            return CommandResult(success=False, error="Usage: /skill-unload <name> — remove a loaded skill from context.")
        if skill_name not in _loaded_skills:
            loaded = ", ".join(_loaded_skills) if _loaded_skills else "(none)"
            return CommandResult(success=False, error=f"Skill '{skill_name}' is not loaded. Currently loaded: {loaded}")
        del _loaded_skills[skill_name]
        return CommandResult(success=True, message=f"Unloaded skill: {skill_name}")

    def handle_skill_clear(args: str, **ctx):
        count = len(_loaded_skills)
        _loaded_skills.clear()
        return CommandResult(success=True, message=f"Cleared {count} loaded skills.")

    def handle_skill_loaded(args: str, **ctx):
        if not _loaded_skills:
            return CommandResult(success=True, message="No skills currently loaded. Use /skill <name> to load one.")
        lines = [f"Loaded skills ({len(_loaded_skills)}/{_MAX_LOADED_SKILLS}):"]
        for name in _loaded_skills:
            lines.append(f"  · {name}")
        return CommandResult(success=True, message="\n".join(lines))

    engine.register("help", handle_help, description="Show available commands", category="core")
    engine.register("brief", handle_brief, description="Morning brief — where you left off", category="core")
    engine.register("stuck", handle_stuck, description="ADHD rescue: one concrete next step", category="core")
    engine.register("bench", handle_bench, description="Set work mode (sansui, ridgeline, heathkit, or custom)", category="core")
    engine.register("screen", handle_screen, description="Screenshot + vision analysis", category="tools")
    engine.register("scrape", handle_scrape, description="Scrape a webpage for content", category="tools")
    engine.register("capture", handle_capture, description="Quick brain dump (persisted)", category="memory")
    engine.register("remember", handle_remember, description="Save a persistent fact", category="memory")
    engine.register("review", handle_review, description="Show all captures + saved facts", category="memory")
    engine.register("deepsearch", handle_deepsearch, description="Web search + synthesis", category="tools")
    engine.register("status", handle_status, description="Model, tools, session cost", category="core")
    engine.register("clear", handle_clear, description="Clear conversation history", category="core")
    engine.register("council", handle_council, description="Dynamic expert panel debate", category="core")
    engine.register("prep", handle_prep, description="Prescriber prep session", category="core", visible=False)
    engine.register("optic", handle_optic, description="Screenshot + vision/OCR analysis", category="tools", visible=False)
    engine.register("ocr", handle_ocr, description="OCR from screenshot or image path", category="tools", visible=False)
    engine.register("repair", handle_repair, description="Hardware repair image analysis", category="tools", visible=False)
    engine.register("image", handle_image, description="Image analysis with optional question", category="tools", visible=False)
    engine.register("cal", handle_cal, description="Calendar events list", category="tools", visible=False)
    engine.register("watch", handle_watch, description="Screen watch start/stop", category="tools", visible=False)
    engine.register("skills", handle_skills, description="Show consolidated skill chains", category="core")
    engine.register("skill", handle_skill, description="Load a skill into context", category="core", visible=False)
    engine.register("skill-unload", handle_skill_unload, description="Remove a loaded skill", category="core", visible=False)
    engine.register("skill-clear", handle_skill_clear, description="Clear all loaded skills", category="core", visible=False)
    engine.register("skill-loaded", handle_skill_loaded, description="Show currently loaded skills", category="core", visible=False)


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

    _ensure_commands_registered(sup)
    engine = get_command_engine()
    result = engine.execute(inp, output_mode="stdout", sup=sup, orch=orch)

    if result.success:
        return None

    if result.data.get("similar"):
        return None

    try:
        if inp.startswith("/") and len(inp) > 1:
            similar = difflib.get_close_matches(inp.split()[0], _AVAILABLE_COMMANDS, n=3, cutoff=0.6)
            if similar:
                sys.stdout.write(f"Unknown command: {inp.split()[0]}. Did you mean: {', '.join(similar)}?\n")
            else:
                sys.stdout.write(f"Unknown command: {inp.split()[0]}. Type /help for available commands.\n")
            return None

        sup.run(inp)
    except Exception as e:
        logger.error("Dispatch error: %s", e)
        sys.stdout.write("Error processing request. Try: Use /help for commands, or rephrase your request.\n")

    return None
