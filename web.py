#!/usr/bin/env python3
"""Kitty Web — Flask + SSE entry point.

Run:
    python3.12 web.py
    # or for dev reload:
    FLASK_DEBUG=1 python3.12 web.py

Mobile access:  http://<your-mac-ip>:5000
"""

import logging
import os
import secrets
import socket
import sys
import queue
import threading
from pathlib import Path

from src.core.watchers import OBDWatcher

# Ensure project root is on sys.path so `src.*` imports resolve
_root = Path(__file__).parent.resolve()
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# Load .env before anything else reads os.environ
try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed — env vars must be set in shell

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

from src.api import (
    ai_dev_bp,
    brief_bp,
    bom_bp,
    commands_bp,
    core_bp,
    eval_bp,
    memory_bp,
    memory_product_bp,
    news_bp,
    reasoning_bp,
    settings_bp,
    streaming_bp,
    swarm_bp,
    system_bp,
    voice_bp,
    quarantine_bp,
)
from src.api.emitters import init_socketio
from src.api.shared import TokenCapture
from src.api.socket_handlers import register_socket_handlers
from src.api.web_llm import WebLLMClient

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("kitty.web")


# ── Minimal supervisor shim ──────────────────────────────────────────────────
# The CoreOrchestrator handles all NL processing.  This shim satisfies the
# `current_app.supervisor` guard in streaming_routes and any fallback calls.

class _MemShim:
    def __init__(self):
        self.data = {}

    def get_facts(self):
        return self.data

    def set_facts(self, facts: dict):
        self.data.update(facts)


class _SupervisorShim:
    """Thin stand-in for the CLI Supervisor when running the web server."""

    def __init__(self):
        self.config = {
            "flash_model": os.environ.get("KITTY_MODEL", "deepseek/deepseek-v4-flash"),
            "cheap_model": os.environ.get("KITTY_MODEL", "deepseek/deepseek-v4-flash"),
            "supervisor_model": os.environ.get("KITTY_MODEL", "deepseek/deepseek-v4-flash"),
            "enable_experimental_swarm": False,
        }
        try:
            from src.core.specialists.registry import list_specialists
            self.specialists = [{"name": name} for name in list_specialists()]
        except Exception:
            self.specialists = []
        
        self.tools = {
            "calendar_list": type('Cal', (), {'list_events': lambda days: "Calendar access not configured in web environment."}),
        }
        self.history = []
        self.memory = _MemShim()
        self._active_mode = None
        self._web_orchestrator = None

    def run(self, inp: str):
        if not inp: return
        sys.stdout.write(f"{inp}\n")
        sys.stdout.flush()

    def morning_brief(self):
        try:
            from src.core.morning_brief import brief_to_text, generate_brief
            brief = generate_brief()
            self.run(brief_to_text(brief))
        except Exception as e:
            logger.error(f"Brief error: {e}")
            self.run("Failed to generate morning brief.")

    def stuck_recovery(self, what: str = ""):
        try:
            from src.core.stuck import get_stuck_action
            action = get_stuck_action()
            resp = f"Stuck? Here's your next step: {action['next_action']}"
            if action.get("do_not"):
                resp += f"\n\nDo not: {', '.join(action['do_not'])}"
            self.run(resp)
        except Exception as e:
            logger.error(f"Stuck error: {e}")
            self.run("Rescue protocol failed. Just pick the smallest possible task.")

    def start_chatbox(self, **kw): return "chatbox unavailable in web mode"
    def chatbox_stop(self): return "stopped"
    def clear_mode(self): self._active_mode = None
    def set_mode(self, mode: str, ctx: str = ""): self._active_mode = mode
    def prescriber_prep(self): self.run("Prescriber prep initiated (stub).")
    def screen_capture(self, q: str = ""): self.run("Screen capture not available in server environment.")
    def ocr_image(self, path: str): self.run("OCR not available in server environment.")

    def scrape_webpage(self, url: str):
        try:
            import httpx
            from bs4 import BeautifulSoup
            r = httpx.get(url, timeout=10, follow_redirects=True)
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]): tag.decompose()
            text = " ".join(soup.get_text(" ", strip=True).split())
            self.run(f"Scraped {url}:\n\n{text[:2000]}...")
        except Exception as e:
            self.run(f"Failed to scrape {url}: {e}")

    def repair_image(self, path: str, context: str = ""): self.run("Image repair not available in server environment.")
    def analyze_image(self, path: str, question: str = ""): self.run("Image analysis not available in server environment.")
    
    def deep_search(self, query: str):
        try:
            from src.tools.deep_search import deep_search, format_for_llm
            from tavily import TavilyClient
            api_key = os.environ.get("TAVILY_API_KEY")
            if not api_key:
                self.run("Deep search requires TAVILY_API_KEY.")
                return
            client = TavilyClient(api_key=api_key)
            results = deep_search(query, tavily_client=client)
            self.run(format_for_llm(results))
        except Exception as e:
            self.run(f"Deep search failed: {e}")

    def save_session(self): pass

    @property
    def session_cost(self): return 0.0

    def screen_watch_stop(self): return "Screen watch stopped"
    def screen_watch_start(self, interval: int = 5): return f"Screen watch started ({interval}s interval)"
    def handle_unified_request(self, message: str): self.run("Unified request handler (stub).")
    def assemble_council(self, context: str = ""): self.run("Specialist council not available in web mode.")


# ── App factory ──────────────────────────────────────────────────────────────

def create_app() -> tuple[Flask, SocketIO]:
    app = Flask(
        __name__,
        template_folder="src/templates",
        static_folder="src/static",
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))

    cors_env = os.environ.get("KITTY_CORS_ORIGINS", "*")
    allowed_origins = cors_env.split(",") if cors_env != "*" else "*"
    CORS(app, resources={r"/*": {"origins": allowed_origins}})
    socketio = SocketIO(app, cors_allowed_origins=allowed_origins, async_mode="threading")
    enable_experimental_swarm = os.environ.get("KITTY_ENABLE_EXPERIMENTAL_SWARM", "").lower() in {
        "1", "true", "yes", "on",
    }
    enable_internal_api = os.environ.get("KITTY_ENABLE_INTERNAL_API", "").lower() in {
        "1", "true", "yes", "on",
    }
    app.config["ENABLE_EXPERIMENTAL_SWARM"] = enable_experimental_swarm
    app.config["ENABLE_INTERNAL_API"] = enable_internal_api

    init_socketio(socketio)
    register_socket_handlers(socketio)

    blueprints = [
        ai_dev_bp, bom_bp, core_bp, eval_bp,
        memory_bp, memory_product_bp, news_bp, reasoning_bp, settings_bp,
        streaming_bp, system_bp, voice_bp, brief_bp, commands_bp, quarantine_bp,
    ]
    if enable_experimental_swarm:
        blueprints.append(swarm_bp)

    for bp in blueprints:
        app.register_blueprint(bp)

    # Attach supervisor shim — satisfies guards without loading CLI deps
    app.supervisor = _SupervisorShim()
    app.supervisor.config["enable_experimental_swarm"] = enable_experimental_swarm
    app.web_llm = WebLLMClient()

    # Attach real orchestrator
    try:
        from src.space_kitty.core_orchestrator import CoreOrchestrator
        app.orchestrator = CoreOrchestrator(socketio=socketio, enable_voice_components=False)
        app.supervisor._web_orchestrator = app.orchestrator
        
        # Start OBD Watcher
        obd_queue: queue.Queue = queue.Queue()
        obd_watcher = OBDWatcher(obd_queue)
        obd_watcher.start()
        
        # Background thread to bridge OBD notifications to SocketIO
        def obd_bridge():
            while True:
                msg = obd_queue.get()
                socketio.emit('token', {'text': f"\n\n{msg}\n"})
                obd_queue.task_done()
        
        threading.Thread(target=obd_bridge, daemon=True).start()

        resume_info = app.orchestrator.get_resume_summary()
        if resume_info:
            logger.info(resume_info)
        else:
            logger.info("CoreOrchestrator ready (fresh session)")
    except Exception:
        logger.exception("CoreOrchestrator unavailable during app startup")
        app.orchestrator = None

    # Pipe stdout through SSE broadcaster so tokens stream to the browser
    sys.stdout = TokenCapture(sys.stdout)

    return app, socketio


# ── Entry point ──────────────────────────────────────────────────────────────

def _local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def main():
    host = os.environ.get("KITTY_HOST", "0.0.0.0")
    port = int(os.environ.get("KITTY_PORT", "5001"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    app, socketio = create_app()

    ip = _local_ip()
    print(f"""
┌─────────────────────────────────────────┐
│  🐱  KITTY — web server starting        │
│                                         │
│  Local   →  http://localhost:{port}      │
│  Mobile  →  http://{ip}:{port}  │
└─────────────────────────────────────────┘
""")

    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()
