#!/opt/homebrew/bin/python3.12
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
from pathlib import Path

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
    bom_bp,
    core_bp,
    eval_bp,
    hardware_bp,
    honcho_bp,
    memory_bp,
    memory_product_bp,
    reasoning_bp,
    settings_bp,
    streaming_bp,
    swarm_bp,
    system_bp,
    voice_bp,
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
        return {}


class _SupervisorShim:
    """Thin stand-in for the CLI Supervisor when running the web server."""

    def __init__(self):
        self.config = {
            "flash_model": os.environ.get("KITTY_MODEL", "openrouter/free"),
            "cheap_model": os.environ.get("KITTY_MODEL", "openrouter/free"),
            "supervisor_model": os.environ.get("KITTY_MODEL", "openrouter/free"),
            "enable_experimental_swarm": False,
        }
        self.specialists = []
        self.tools = []
        self.history = []
        self.memory = _MemShim()
        self._active_mode = None
        self._web_orchestrator = None

    def run(self, inp: str):
        sys.stdout.write(f"{inp}\n")
        sys.stdout.flush()

    # Stubs for routes that call these methods
    def morning_brief(self):
        summary = None
        if self._web_orchestrator is not None:
            try:
                summary = self._web_orchestrator.get_resume_summary()
            except Exception:
                logger.exception("Failed to build resume summary for /brief")

        if not summary:
            if self._active_mode:
                summary = (
                    f"Fresh session. Current work mode: {self._active_mode}. "
                    "Tell me what feels stuck and I'll give you one next step."
                )
            else:
                summary = (
                    "Fresh session. No saved resume yet. "
                    "Tell me what you're working on and I'll help with the next step."
                )

        self.run(summary)

    def stuck_recovery(self, what: str = ""): pass
    def start_chatbox(self, **kw): return "chatbox unavailable in web mode"
    def chatbox_stop(self): return "stopped"
    def clear_mode(self): self._active_mode = None
    def set_mode(self, mode: str, ctx: str = ""): self._active_mode = mode
    def prescriber_prep(self): pass
    def screen_capture(self, q: str = ""): pass
    def ocr_image(self, path: str): pass


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
        bom_bp, core_bp, eval_bp, hardware_bp, honcho_bp,
        memory_bp, memory_product_bp, reasoning_bp, settings_bp,
        streaming_bp, system_bp, voice_bp,
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
