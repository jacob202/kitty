from __future__ import annotations

import json
import os
import re
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

# A version change can run irreversible database migrations. Upgrades therefore
# need an explicit, backed-up flow rather than an environment override that
# silently points a new binary at the old data directory.
VERSION = "0.10.2"
PORT = int(os.environ.get("KITTY_OPENWEBUI_PORT", "3000"))
HOST = os.environ.get("KITTY_OPENWEBUI_HOST", "127.0.0.1").strip()
DEFAULT_MODEL = "kitty-auto"
TASK_MODEL = "kitty-fast"
DEFAULT_AGENT = "daily-kitty"
PINNED_AGENTS = "daily-kitty,research,coding,tutor,builder-operator"
VENV_DIR = SERVICE_ROOT / f"venv-{VERSION}"
DATA_DIR = SERVICE_ROOT / f"data-{VERSION}"
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


def _require_loopback_host(host: str) -> None:
    # WEBUI_AUTH=False is intentional for this single-user local shell. That is
    # safe only while the listener is unreachable from the LAN.
    if host not in {"127.0.0.1", "localhost"}:
        fail(
            "KITTY_OPENWEBUI_HOST must be 127.0.0.1 or localhost while "
            "WEBUI_AUTH is disabled"
        )


_require_loopback_host(HOST)


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


_VAR_PATTERN = re.compile(r"\$(\w+|\{[^}]+\})")


def _expand_with_env(raw_value: str, env_map: dict[str, str]) -> str:
    def replace_var(match: re.Match[str]) -> str:
        token = match.group(1)
        if token.startswith("{") and token.endswith("}"):
            token = token[1:-1]
        return env_map.get(token, match.group(0))

    return _VAR_PATTERN.sub(replace_var, raw_value)


def read_dotenv(path: Path, *, base: dict[str, str] | None = None) -> dict[str, str]:
    """Read the assignment subset accepted by Kitty's canonical launcher."""
    values: dict[str, str] = {}
    resolved = dict(os.environ if base is None else base)
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
        if not key or not (key[0].isalpha() or key[0] == "_"):
            continue
        if not all(character.isalnum() or character == "_" for character in key):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        value = _expand_with_env(value, resolved)
        values[key] = value
        resolved[key] = value

    return values


def repo_env() -> dict[str, str]:
    """Resolve configuration with the same precedence as ``./kitty``.

    The shell is the expansion base, but repository assignments win. A stale
    exported GATEWAY_PORT or secret must not redirect Open WebUI away from the
    Gateway the canonical launcher actually starts.
    """
    values = dict(os.environ)
    values.update(read_dotenv(ROOT / ".env", base=values))
    return values


def gateway_config() -> tuple[str, str]:
    values = repo_env()
    port = values.get("GATEWAY_PORT", "8000")
    secret = values.get("GATEWAY_SECRET") or values.get("KITTY_GATEWAY_SECRET") or ""
    return f"http://127.0.0.1:{port}", secret


def kitty_ui_port() -> int:
    return int(repo_env().get("UI_PORT", "4000"))


# Compatibility export for callers that import the constant. It is resolved from
# repository configuration, not the ambient shell.
KITTY_UI_PORT = kitty_ui_port()


def ensure_dirs() -> None:
    for path in (SERVICE_ROOT, DATA_DIR, BACKUP_ROOT, LOG_DIR, RUN_DIR):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)


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
            (
                "import importlib.metadata as m, sys; "
                "\ntry: print(m.version('open-webui'))"
                "\nexcept m.PackageNotFoundError: sys.exit(44)"
            ),
        ],
        check=False,
        capture=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    if result.returncode == 44:
        return None
    detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
    fail(f"cannot inspect Open WebUI in {VENV_DIR}: {detail[:500]}")


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


_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def open_local(request: str | urllib.request.Request, *, timeout: float):
    """Open a loopback request without consulting ambient proxy variables."""
    return _NO_PROXY_OPENER.open(request, timeout=timeout)


def request_json(url: str, *, auth: str = "", timeout: float = 5.0) -> dict:
    headers = {"Accept": "application/json"}
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    request = urllib.request.Request(url, headers=headers)

    try:
        with open_local(request, timeout=timeout) as response:
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


def wait_for_gateway(attempts: int, *, last_error: list[str] | None = None) -> tuple[str, str] | None:
    latest = ""
    for _ in range(attempts):
        try:
            return verify_gateway()
        except Failure as exc:
            latest = str(exc)
            time.sleep(1)
    if last_error is not None:
        last_error[:] = [latest]
    if latest:
        print(f"Gateway not ready: {latest}")
    return None


def ensure_gateway_running() -> tuple[str, str]:
    errors: list[str] = []
    ready = wait_for_gateway(12, last_error=errors)
    if ready is not None:
        return ready

    print("Gateway is unhealthy; reloading the Kitty launch services")
    run([ROOT / "kitty", "install"], cwd=ROOT)

    ready = wait_for_gateway(60, last_error=errors)
    if ready is not None:
        return ready

    base, _ = gateway_config()
    cause = errors[-1] if errors else "no diagnostic was captured"
    fail(
        "Kitty Gateway did not become ready after a clean restart: "
        f"{cause}. Run './kitty logs' and inspect {base}/health."
    )


_RUNTIME_ENV_KEYS = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "SHELL",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
    }
)


def sanitized_env(source: dict[str, str] | None = None) -> dict[str, str]:
    """Return the minimal non-secret environment Open WebUI needs to run."""
    incoming = dict(os.environ if source is None else source)
    env = {
        key: value
        for key, value in incoming.items()
        if key in _RUNTIME_ENV_KEYS and isinstance(value, str) and value
    }
    env.setdefault("PATH", os.defpath)
    env.setdefault("HOME", str(Path.home()))
    env["PYTHONNOUSERSITE"] = "1"
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["no_proxy"] = env["NO_PROXY"]
    return env


def tool_server_connections(base: str, gateway_secret: str) -> str:
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
    _require_loopback_host(HOST)
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
            "ENABLE_TITLE_GENERATION": "True",
            "ENABLE_AUTOCOMPLETE_GENERATION": "False",
            "ENABLE_MESSAGE_RATING": "False",
            "ENABLE_TAGS_GENERATION": "False",
            "WEBUI_AUTH": "False",
            "DEFAULT_USER_ROLE": "admin",
            "ENABLE_OPENAI_API": "True",
            "OPENAI_API_BASE_URL": f"{base}/v1",
            "OPENAI_API_KEY": gateway_secret,
            "TOOL_SERVER_CONNECTIONS": tool_server_connections(base, gateway_secret),
            "ENABLE_OLLAMA_API": "False",
            "DEFAULT_MODELS": DEFAULT_AGENT,
            "DEFAULT_PINNED_MODELS": PINNED_AGENTS,
            "TASK_MODEL_EXTERNAL": TASK_MODEL,
            "ENABLE_PERSISTENT_CONFIG": "False",
            "ENABLE_VERSION_UPDATE_CHECK": "False",
            "ENABLE_COMMUNITY_SHARING": "False",
            "ENABLE_EVALUATION_ARENA_MODELS": "False",
            "ANONYMIZED_TELEMETRY": "False",
            "DO_NOT_TRACK": "true",
            "SCARF_NO_ANALYTICS": "true",
            "ENABLE_BASE_MODELS_CACHE": "True",
            "MODELS_CACHE_TTL": "300",
            "SAFE_MODE": "True",
            "CORS_ALLOW_ORIGIN": f"http://{HOST}:{PORT};http://localhost:{PORT}",
            "UVICORN_WORKERS": "1",
        }
    )
    return env
