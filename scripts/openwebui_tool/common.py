from __future__ import annotations

import json
import os
import secrets
import shutil
import stat
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOT = Path(
    os.environ.get(
        "KITTY_OPENWEBUI_HOME",
        Path.home() / "kitty-services/openwebui",
    )
).expanduser()
VERSION = os.environ.get("KITTY_OPENWEBUI_VERSION", "0.10.2")
PORT = int(os.environ.get("KITTY_OPENWEBUI_PORT", "3000"))
HOST = os.environ.get("KITTY_OPENWEBUI_HOST", "127.0.0.1")
# The existing Next.js UI, i.e. what `rollback` hands the day back to. Matches
# UI_PORT in ./kitty.
KITTY_UI_PORT = int(os.environ.get("UI_PORT", "4000"))
# The routing id the health check looks for. Must exist in the Gateway's
# /v1/models — its absence means the Gateway is not really up.
DEFAULT_MODEL = "kitty-auto"
TASK_MODEL = "kitty-fast"
# What Jacob actually opens on and sees pinned. These are Open WebUI workspace
# agents (see AGENTS in service.py), each backed by one of the routing ids
# above; the raw ids stay selectable but are plumbing, not the daily menu.
DEFAULT_AGENT = "daily-kitty"
PINNED_AGENTS = "daily-kitty,research,coding,tutor,builder-operator"
VENV_DIR = SERVICE_ROOT / f"venv-{VERSION}"
DATA_DIR = SERVICE_ROOT / "data-fresh"
BACKUP_ROOT = SERVICE_ROOT / "backups"
LOG_DIR = SERVICE_ROOT / "logs"
RUN_DIR = SERVICE_ROOT / "run"
PID_FILE = RUN_DIR / "openwebui.pid"
LOG_FILE = LOG_DIR / "openwebui.log"
SECRET_FILE = SERVICE_ROOT / "webui-secret"
LAUNCH_AGENT = Path.home() / "Library/LaunchAgents/com.kitty.openwebui.plist"
DESKTOP_SHORTCUT = Path.home() / "Desktop/Kitty Chat.webloc"
OPENWEBUI_BIN = VENV_DIR / "bin/open-webui"


class Failure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise Failure(message)


def run(
    args: Iterable[str | os.PathLike[str]],
    *,
    check: bool = True,
    capture: bool = False,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        check=check,
        text=True,
        capture_output=capture,
        env=env,
        cwd=str(cwd) if cwd else None,
    )


def read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()

        key, separator, value = line.partition("=")
        if not separator:
            continue
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value

    return values


def repo_env() -> dict[str, str]:
    values = read_dotenv(ROOT / ".env")
    values.update(os.environ)
    return values


def gateway_config() -> tuple[str, str]:
    values = repo_env()
    port = values.get("GATEWAY_PORT", "8000")
    secret = values.get("GATEWAY_SECRET") or values.get("KITTY_GATEWAY_SECRET") or ""
    return f"http://127.0.0.1:{port}", secret


def ensure_dirs() -> None:
    for path in (SERVICE_ROOT, DATA_DIR, BACKUP_ROOT, LOG_DIR, RUN_DIR):
        path.mkdir(parents=True, exist_ok=True)


def uv_path() -> str:
    candidates = (
        shutil.which("uv"),
        Path.home() / ".local/bin/uv",
        "/opt/homebrew/bin/uv",
        "/usr/local/bin/uv",
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    fail("uv is required but was not found in PATH, ~/.local/bin, or Homebrew")


def installed_version() -> str | None:
    python = VENV_DIR / "bin/python"
    if not python.exists():
        return None

    result = run(
        [
            python,
            "-c",
            "import importlib.metadata; print(importlib.metadata.version('open-webui'))",
        ],
        check=False,
        capture=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def install_openwebui() -> None:
    ensure_dirs()
    current = installed_version()
    if current == VERSION and OPENWEBUI_BIN.exists():
        print(f"Open WebUI {VERSION} already installed")
        return
    if VENV_DIR.exists() and current not in {None, VERSION}:
        fail(f"{VENV_DIR} contains Open WebUI {current}; refusing an in-place upgrade")

    uv = uv_path()
    if not VENV_DIR.exists():
        print(f"Creating Python 3.11 environment at {VENV_DIR}")
        run([uv, "venv", "--python", "3.11", VENV_DIR])

    print(f"Installing pinned Open WebUI {VERSION}")
    run(
        [
            uv,
            "pip",
            "install",
            "--python",
            VENV_DIR / "bin/python",
            f"open-webui=={VERSION}",
        ]
    )
    if installed_version() != VERSION:
        fail(f"Open WebUI version verification failed; expected {VERSION}")


def ensure_webui_secret() -> str:
    ensure_dirs()
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32) + "\n", encoding="utf-8")
        SECRET_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)

    secret = SECRET_FILE.read_text(encoding="utf-8").strip()
    if len(secret) < 32:
        fail(f"Open WebUI secret at {SECRET_FILE} is unexpectedly short")
    return secret


def request_json(url: str, *, auth: str = "", timeout: float = 5.0) -> dict:
    headers = {"Accept": "application/json"}
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    request = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        fail(f"{url} returned HTTP {exc.code}: {detail[:300]}")
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        fail(f"cannot read {url}: {exc}")

    raise AssertionError("unreachable")


def verify_gateway() -> tuple[str, str]:
    base, secret = gateway_config()
    request_json(f"{base}/health", timeout=5)
    if not secret:
        fail("Gateway is healthy but no Gateway secret was found in .env")

    models = request_json(f"{base}/v1/models", auth=secret, timeout=5)
    model_ids = {
        item.get("id")
        for item in models.get("data", [])
        if isinstance(item, dict)
    }
    if DEFAULT_MODEL not in model_ids:
        rendered = sorted(str(model_id) for model_id in model_ids)
        fail(f"Kitty model discovery is missing {DEFAULT_MODEL}: {rendered}")

    print(f"Gateway ready: {base} ({len(model_ids)} models, {DEFAULT_MODEL} present)")
    return base, secret


def wait_for_gateway(attempts: int) -> tuple[str, str] | None:
    for _ in range(attempts):
        try:
            return verify_gateway()
        except Failure:
            time.sleep(1)
    return None


def ensure_gateway_running() -> tuple[str, str]:
    ready = wait_for_gateway(12)
    if ready is not None:
        return ready

    # `./kitty install` reloads the launchd jobs in place. `./kitty down`/`up`
    # was worse than the problem: `down` boots those jobs out entirely, so a
    # Gateway that was merely slow came back as a shell-owned process that dies
    # with the terminal and never returns after a reboot.
    print("Gateway is unhealthy; reloading the Kitty launch services")
    run([ROOT / "kitty", "install"], cwd=ROOT)

    ready = wait_for_gateway(60)
    if ready is not None:
        return ready

    base, _ = gateway_config()
    fail(
        "Kitty Gateway did not become ready after a clean restart. "
        f"Run './kitty logs' and inspect {base}/health."
    )


# Kitty's repo root holds a top-level ``mcp`` package, and ``./kitty`` exports
# PYTHONPATH=<repo root>. Open WebUI's own ``mcp`` is the MCP SDK, so any
# inherited PYTHONPATH turns its tool client into
# "ImportError: cannot import name 'ClientSession' from 'mcp'". Nothing Open
# WebUI needs comes from Kitty's interpreter, so drop the import-path knobs
# outright rather than trying to filter individual entries.
SHADOWING_ENV_VARS = ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP")


def sanitized_env(source: dict[str, str] | None = None) -> dict[str, str]:
    """Return ``source`` with every Kitty import-path knob removed."""
    env = dict(os.environ if source is None else source)
    for name in SHADOWING_ENV_VARS:
        env.pop(name, None)
    # ~/.local/lib can shadow the pinned venv the same way PYTHONPATH does.
    env["PYTHONNOUSERSITE"] = "1"
    return env


def tool_server_connections(base: str, gateway_secret: str) -> str:
    """Point Open WebUI at Kitty's own tool surface, not the whole Gateway.

    ``/tools/v1/openapi.json`` lists six operations. The Gateway's own
    ``/openapi.json`` lists more than two hundred, and Open WebUI turns every one
    into a tool the model has to read past.
    """
    # `config`, `info`, and `type` are required by Open WebUI's own
    # ToolServerConnection model. Omitting them made /api/v1/configs/tool_servers
    # answer 500 — and log the whole connection, Gateway secret included.
    return json.dumps(
        [
            {
                "url": base,
                "path": "/tools/v1/openapi.json",
                "type": "openapi",
                "auth_type": "bearer",
                "key": gateway_secret,
                "config": {"enable": True},
                "info": {"id": "kitty", "name": "Kitty"},
            }
        ]
    )


# The chips on an empty chat. Life before code (ADR 0016), and each one is
# answerable only by calling a tool — a starter prompt Kitty cannot act on
# teaches Jacob the tools do not work.
STARTER_PROMPTS = json.dumps(
    [
        {
            "title": ["What's next", "on the thing that actually matters"],
            "content": "Look at my projects and my calendar. What is the one next step worth doing today? Life before code.",
        },
        {
            "title": ["Catch me up", "on what you know about me"],
            "content": "Search your memory and tell me what you know about me and what I am working on. Say plainly if it is thin.",
        },
        {
            "title": ["Find it in my notes", "search what I've written down"],
            "content": "Search my notes for ",
        },
        {
            "title": ["Builder status", "what needs a decision"],
            "content": "Check KittyBuilder. What is queued, what is blocked, and what needs a decision from me?",
        },
    ]
)


def runtime_env() -> dict[str, str]:
    base, gateway_secret = gateway_config()
    if not gateway_secret:
        fail("missing Gateway secret; run './kitty up' first")

    env = sanitized_env()
    env.update(
        {
            "DATA_DIR": str(DATA_DIR),
            "WEBUI_SECRET_KEY": ensure_webui_secret(),
            "WEBUI_URL": f"http://{HOST}:{PORT}",
            "WEBUI_NAME": "Kitty",
            "DEFAULT_PROMPT_SUGGESTIONS": STARTER_PROMPTS,
            # A phone is the common case, not the exception.
            "ENABLE_TITLE_GENERATION": "True",
            "ENABLE_AUTOCOMPLETE_GENERATION": "False",
            "ENABLE_MESSAGE_RATING": "False",
            "ENABLE_TAGS_GENERATION": "False",
            "WEBUI_AUTH": "False",
            # 0.10.2 inserts a new account with DEFAULT_USER_ROLE (normally
            # "pending") and only promotes it when it is the only row *after*
            # the insert. Concurrent first-load signins therefore leave every
            # account pending — the "Account Activation Pending" wall Jacob hit.
            # This is a single-user local install; there is no one to approve.
            "DEFAULT_USER_ROLE": "admin",
            "ENABLE_OPENAI_API": "True",
            "OPENAI_API_BASE_URL": f"{base}/v1",
            "OPENAI_API_KEY": gateway_secret,
            "TOOL_SERVER_CONNECTIONS": tool_server_connections(base, gateway_secret),
            "ENABLE_OLLAMA_API": "False",
            "DEFAULT_MODELS": DEFAULT_AGENT,
            "DEFAULT_PINNED_MODELS": PINNED_AGENTS,
            # Titles and tag suggestions are throwaway work; they do not need
            # the tier the conversation is on.
            "TASK_MODEL_EXTERNAL": TASK_MODEL,
            "ENABLE_PERSISTENT_CONFIG": "False",
            "ENABLE_VERSION_UPDATE_CHECK": "False",
            "ENABLE_COMMUNITY_SHARING": "False",
            # Open WebUI ships an "arena-model" entry that appears next to
            # kitty-default in the model menu and routes nowhere Kitty owns.
            "ENABLE_EVALUATION_ARENA_MODELS": "False",
            "ANONYMIZED_TELEMETRY": "False",
            "DO_NOT_TRACK": "true",
            "SCARF_NO_ANALYTICS": "true",
            "ENABLE_BASE_MODELS_CACHE": "True",
            "MODELS_CACHE_TTL": "300",
            "SAFE_MODE": "True",
            "CORS_ALLOW_ORIGIN": (
                f"http://{HOST}:{PORT};http://localhost:{PORT}"
            ),
            "UVICORN_WORKERS": "1",
        }
    )
    return env
