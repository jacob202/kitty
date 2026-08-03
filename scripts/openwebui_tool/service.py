from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from .common import (
    DATA_DIR,
    DEFAULT_AGENT,
    DEFAULT_MODEL,
    HOST,
    LOG_FILE,
    OPENWEBUI_BIN,
    PID_FILE,
    PORT,
    SECRET_FILE,
    SERVICE_ROOT,
    VERSION,
    Failure,
    ensure_dirs,
    ensure_gateway_running,
    install_openwebui,
    installed_version,
    open_local,
    request_json,
    runtime_env,
    verify_gateway,
)

SYSTEM_ADMIN_EMAIL = "admin@localhost"
SYSTEM_ADMIN_PASSWORD = "admin"
START_LOCK = PID_FILE.with_name("openwebui-start.lock")
SMOKE_DEADLINE_SECONDS = 90.0
SMOKE_MAX_TOKENS = 8


def webui_db_path() -> Path:
    return DATA_DIR / "webui.db"


def _tables_referencing_user(connection: sqlite3.Connection) -> list[str]:
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    ]
    owning = []
    for table in tables:
        if table in {"user", "auth"}:
            continue
        columns = {
            row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')
        }
        if "user_id" in columns:
            owning.append(table)
    return owning


def count_system_admins() -> int:
    database = webui_db_path()
    if not database.exists():
        return 0
    try:
        with sqlite3.connect(database) as connection:
            (count,) = connection.execute(
                "SELECT COUNT(*) FROM user WHERE email = ?", (SYSTEM_ADMIN_EMAIL,)
            ).fetchone()
    except sqlite3.Error:
        return 0
    return int(count)


def _promote_sole_admin(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        "SELECT id, role FROM user WHERE email = ?", (SYSTEM_ADMIN_EMAIL,)
    ).fetchone()
    if row is None or row[1] == "admin":
        return False
    connection.execute("UPDATE user SET role = 'admin' WHERE id = ?", (row[0],))
    return True


def dedupe_system_admin() -> str:
    """Collapse duplicate system accounts without deleting owned data."""
    database = webui_db_path()
    if not database.exists():
        return "no database yet"

    with sqlite3.connect(database) as connection:
        rows = list(
            connection.execute(
                "SELECT id FROM user WHERE email = ? ORDER BY created_at, id",
                (SYSTEM_ADMIN_EMAIL,),
            )
        )
        if len(rows) <= 1:
            promoted = _promote_sole_admin(connection)
            connection.commit()
            suffix = ", promoted to admin" if promoted else ""
            return f"{len(rows)} admin account{suffix}"

        keeper, extras = rows[0][0], [row[0] for row in rows[1:]]
        owning = _tables_referencing_user(connection)
        for table in owning:
            placeholders = ",".join("?" * len(extras))
            (count,) = connection.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE user_id IN ({placeholders})',
                extras,
            ).fetchone()
            if count:
                raise Failure(
                    f"{len(extras)} duplicate {SYSTEM_ADMIN_EMAIL} account(s) own "
                    f"{count} row(s) in {table!r}; refusing to delete them. "
                    f"Inspect {database} before rerunning."
                )

        placeholders = ",".join("?" * len(extras))
        connection.execute(f"DELETE FROM auth WHERE id IN ({placeholders})", extras)
        connection.execute(f"DELETE FROM user WHERE id IN ({placeholders})", extras)
        _promote_sole_admin(connection)
        connection.commit()

    return f"removed {len(extras)} duplicate admin account(s), kept {keeper} as admin"


def claim_system_admin() -> str:
    """Sign in once serially and return the local session token."""
    body = json.dumps(
        {"email": SYSTEM_ADMIN_EMAIL, "password": SYSTEM_ADMIN_PASSWORD}
    ).encode()
    request = urllib.request.Request(
        f"http://{HOST}:{PORT}/api/v1/auths/signin",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with open_local(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise Failure(
            f"Open WebUI rejected the system signin (HTTP {exc.code}): {detail}"
        ) from exc
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise Failure(f"Open WebUI system signin failed: {exc}") from exc

    token = payload.get("token")
    if not isinstance(token, str) or not token:
        raise Failure("Open WebUI signin succeeded but returned no session token")
    return token


def direct_stream_smoke(*, accept_charges: bool) -> None:
    """Run one tightly bounded paid turn and require the advertised answer."""
    if not accept_charges:
        raise Failure(
            "real streaming smoke may use provider credits; rerun with --accept-charges"
        )

    base, secret = verify_gateway()
    body = json.dumps(
        {
            "model": "kitty-default",
            "messages": [
                {"role": "user", "content": "Reply with exactly: ready"}
            ],
            "stream": True,
            "max_tokens": SMOKE_MAX_TOKENS,
            "temperature": 0,
        }
    ).encode()
    request = urllib.request.Request(
        f"{base}/v1/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )
    started = time.monotonic()
    deadline = started + SMOKE_DEADLINE_SECONDS
    first_token_at: float | None = None
    parts: list[str] = []
    done = False
    gateway_error: str | None = None

    try:
        with open_local(request, timeout=SMOKE_DEADLINE_SECONDS) as response:
            for raw in response:
                if time.monotonic() >= deadline:
                    raise Failure(
                        f"streaming smoke exceeded {SMOKE_DEADLINE_SECONDS:.0f}s overall deadline"
                    )
                line = raw.decode(errors="replace").strip()
                if not line.startswith("data:"):
                    continue

                data = line[5:].strip()
                if data == "[DONE]":
                    done = True
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue

                error = event.get("error") if isinstance(event, dict) else None
                if isinstance(error, dict):
                    gateway_error = (
                        f"{error.get('kind', 'unknown')}: "
                        f"{error.get('message', 'no message')}"
                    )
                    continue

                try:
                    content = event["choices"][0]["delta"].get("content")
                except (KeyError, IndexError, TypeError):
                    continue
                if isinstance(content, str) and content:
                    first_token_at = first_token_at or time.monotonic()
                    parts.append(content)
    except Failure:
        raise
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise Failure(
            f"streaming smoke returned HTTP {exc.code}: {detail}"
        ) from exc
    except (OSError, urllib.error.URLError) as exc:
        raise Failure(f"streaming smoke failed: {exc}") from exc

    if gateway_error is not None:
        raise Failure(f"Gateway refused the streaming turn — {gateway_error}")
    if first_token_at is None:
        raise Failure(
            "streaming smoke received no assistant content; "
            f"see the Gateway log for the turn ({base}/health is reachable)"
        )
    if not done:
        raise Failure(
            "streaming smoke never saw the [DONE] boundary; the stream was cut short"
        )

    total = time.monotonic() - started
    ttft = first_token_at - started
    text = "".join(parts).strip()
    if text.casefold() != "ready":
        raise Failure(
            f"streaming smoke expected exactly 'ready', got {text!r}; "
            f"the request was capped at {SMOKE_MAX_TOKENS} output tokens"
        )
    print(f"Direct stream OK: TTFT={ttft:.2f}s total={total:.2f}s text={text!r}")


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _process_command(pid: int) -> str:
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _pid_owned_by_openwebui(pid: int) -> bool:
    command = _process_command(pid)
    if not command:
        return False
    service_entry = str(Path(__file__).resolve().parents[1] / "openwebui_local.py")
    return (
        str(OPENWEBUI_BIN) in command
        or (service_entry in command and " service" in f" {command}")
    )


def read_pid() -> int | None:
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None

    if not pid_alive(pid) or not _pid_owned_by_openwebui(pid):
        PID_FILE.unlink(missing_ok=True)
        return None
    return pid


def _write_pid(pid: int) -> None:
    PID_FILE.write_text(f"{pid}\n", encoding="utf-8")
    PID_FILE.chmod(0o600)


def port_open() -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((HOST, PORT)) == 0


def wait_for_webui(timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            request_json(f"http://{HOST}:{PORT}/health", timeout=3)
            print(f"Open WebUI ready: http://{HOST}:{PORT}")
            return
        except Failure as exc:
            last_error = str(exc)
            time.sleep(1)

    raise Failure(
        f"Open WebUI did not become healthy: {last_error}; see {LOG_FILE}"
    )


@contextmanager
def _start_lock():
    ensure_dirs()
    with START_LOCK.open("a+") as handle:
        os.fchmod(handle.fileno(), 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _signal_pid(pid: int, sig: signal.Signals) -> None:
    try:
        target = -pid if os.getpgid(pid) == pid else pid
        os.kill(target, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _terminate_tracked_pid(pid: int) -> None:
    if not _pid_owned_by_openwebui(pid):
        PID_FILE.unlink(missing_ok=True)
        return
    _signal_pid(pid, signal.SIGTERM)
    for _ in range(50):
        if not pid_alive(pid):
            break
        time.sleep(0.2)
    if pid_alive(pid) and _pid_owned_by_openwebui(pid):
        _signal_pid(pid, signal.SIGKILL)
    PID_FILE.unlink(missing_ok=True)


def start_webui(*, foreground: bool = False) -> None:
    ensure_dirs()
    install_openwebui()
    ensure_gateway_running()

    with _start_lock():
        pid = read_pid()
        if pid is not None:
            try:
                wait_for_webui(timeout=5)
                return
            except Failure:
                print(f"Open WebUI pid {pid} is alive but unhealthy; restarting it")
                _terminate_tracked_pid(pid)

        if port_open():
            raise Failure(f"port {PORT} is already in use by another process")

        print(f"accounts: {dedupe_system_admin()}")
        command = [str(OPENWEBUI_BIN), "serve", "--host", HOST, "--port", str(PORT)]

        if foreground:
            _write_pid(os.getpid())
            os.chdir(SERVICE_ROOT)
            os.execve(str(OPENWEBUI_BIN), command, runtime_env())

        with LOG_FILE.open("ab", buffering=0) as log:
            process = subprocess.Popen(
                command,
                cwd=SERVICE_ROOT,
                env=runtime_env(),
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        _write_pid(process.pid)
        try:
            wait_for_webui()
        except Exception:
            _terminate_tracked_pid(process.pid)
            raise

        token = claim_system_admin()
        print(f"agents: {ensure_agents(token)}")


def launch_agent_loaded() -> bool:
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/com.kitty.openwebui"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def stop_webui() -> None:
    if launch_agent_loaded():
        result = subprocess.run(
            ["launchctl", "bootout", f"gui/{os.getuid()}/com.kitty.openwebui"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise Failure(f"could not unload Open WebUI launchd job: {detail}")
        for _ in range(50):
            if not port_open():
                break
            time.sleep(0.2)
        print(
            "Login startup is now off. "
            "Run 'openwebui_local.py install-autostart' to turn it back on."
        )

    pid = read_pid()
    if pid is None:
        print("Open WebUI is not running")
        return

    _terminate_tracked_pid(pid)
    print("Open WebUI stopped")


def print_status() -> None:
    pid = read_pid()
    version = installed_version() or "not installed"
    process = f"running pid {pid}" if pid else "not running"
    port_state = "open" if port_open() else "closed"
    print(
        f"service root : {SERVICE_ROOT}\n"
        f"version      : {version}\n"
        f"data         : {DATA_DIR}"
    )
    print(
        f"url          : http://{HOST}:{PORT}\n"
        f"process      : {process}\n"
        f"port         : {port_state}"
    )

    try:
        verify_gateway()
    except Failure as exc:
        print(f"gateway      : FAIL — {exc}")

    try:
        request_json(f"http://{HOST}:{PORT}/health", timeout=3)
        print("open webui   : healthy")
    except Failure as exc:
        print(f"open webui   : FAIL — {exc}")


def open_browser() -> None:
    url = f"http://{HOST}:{PORT}"
    if shutil.which("open"):
        subprocess.run(["open", url], check=False)
    else:
        print(url)


def show_logs() -> None:
    ensure_dirs()
    LOG_FILE.touch(exist_ok=True)
    subprocess.run(["tail", "-n", "120", "-F", LOG_FILE], check=False)


def _visible_model_ids(payload: object) -> set[str]:
    rows: object = payload
    if isinstance(payload, dict):
        rows = payload.get("data", payload.get("models", []))
    if not isinstance(rows, list):
        return set()
    return {
        str(row.get("id"))
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }


def doctor() -> None:
    failures: list[str] = []
    try:
        version = installed_version()
    except Failure as exc:
        failures.append(str(exc))
        version = None
    if version != VERSION:
        failures.append(f"Open WebUI {VERSION} is not installed")

    try:
        verify_gateway()
    except Failure as exc:
        failures.append(str(exc))

    try:
        request_json(f"http://{HOST}:{PORT}/health", timeout=3)
        token = claim_system_admin()
        visible = _visible_model_ids(_webui_request("/api/models", token=token))
        if DEFAULT_AGENT not in visible and DEFAULT_MODEL not in visible:
            failures.append(
                "Open WebUI is healthy but cannot see Kitty's default agent/model; "
                f"visible ids: {sorted(visible)[:20]}"
            )
    except Failure as exc:
        failures.append(str(exc))

    if not SECRET_FILE.exists():
        failures.append(f"missing persistent WebUI secret: {SECRET_FILE}")
    if not DATA_DIR.exists():
        failures.append(f"missing data directory: {DATA_DIR}")

    duplicates = count_system_admins() - 1
    if duplicates > 0:
        failures.append(
            f"{duplicates} duplicate {SYSTEM_ADMIN_EMAIL} account(s); "
            "run 'openwebui_local.py down' then 'up' to collapse them"
        )

    if failures:
        for item in failures:
            print(f"FAIL: {item}")
        raise Failure(f"{len(failures)} doctor check(s) failed")

    print("All Open WebUI doctor checks passed")


AGENTS: tuple[dict[str, object], ...] = (
    {
        "id": "daily-kitty",
        "name": "Daily Kitty",
        "base": "kitty-auto",
        "description": "Everyday Kitty, with access to your memory, notes, projects, and calendar.",
        "tools": True,
        "vision": True,
        "system": (
            "You are Kitty, working with Jacob rather than for him. Life comes "
            "before code: when you suggest what is next, put job search, "
            "benefits, education, health, and money ahead of any code project, "
            "including Kitty itself.\n\n"
            "You have tools onto Jacob's own memory, notes, projects, calendar, "
            "and build queue. Anything personal or current is a tool call, never "
            "a guess. If a tool says it has nothing, say that plainly."
        ),
    },
    {
        "id": "research",
        "name": "Research",
        "base": "kitty-think",
        "description": "Slower, careful reasoning over Jacob's own notes and memory.",
        "tools": True,
        "vision": False,
        "system": (
            "You are Kitty in research mode. Work from what Jacob has actually "
            "written down: search his notes and memory before reasoning, cite "
            "which source each claim came from, and say when a claim rests on "
            "nothing you retrieved."
        ),
    },
    {
        "id": "coding",
        "name": "Coding",
        "base": "kitty-code",
        "description": "Implementation and debugging. No tools, no distractions.",
        "tools": False,
        "vision": False,
        "system": (
            "You are Kitty writing code. Prefer the standard library, the "
            "platform, and dependencies already present over anything new. No "
            "speculative abstractions. Explain what you skipped and when it "
            "would be worth adding."
        ),
    },
    {
        "id": "tutor",
        "name": "Tutor",
        "base": "kitty-auto",
        "description": "Teaches only from documents you have ingested, and admits when it has none.",
        "tools": True,
        "vision": False,
        "system": (
            "You are Kitty's Tutor. Answer only from ingested documents via the "
            "tutor tool. Never fill a gap from general knowledge — when the "
            "tutor has nothing, say so and relay the command that fixes it. "
            "Define every term before you use it; assume no background."
        ),
    },
    {
        "id": "builder-operator",
        "name": "Builder Operator",
        "base": "kitty-auto",
        "description": "Reads KittyBuilder's queue and tells you what needs a decision.",
        "tools": True,
        "vision": False,
        "system": (
            "You report KittyBuilder state from the builder tool and nothing "
            "else. You do not start, approve, publish, or merge anything — say "
            "what is queued, what is blocked, and what needs Jacob's decision. "
            "Never infer state the tool did not report."
        ),
    },
)


def ensure_agents(token: str) -> str:
    """Create or update the workspace agents. Safe to run on every bootstrap."""
    created, updated = 0, 0
    for agent in AGENTS:
        body = {
            "id": agent["id"],
            "base_model_id": agent["base"],
            "name": agent["name"],
            "meta": {
                "description": agent["description"],
                "capabilities": {
                    "vision": bool(agent.get("vision", False)),
                    "citations": True,
                },
            },
            "params": {"system": agent["system"]},
            "is_active": True,
        }
        if agent["tools"]:
            body["meta"]["toolIds"] = ["server:kitty"]
        existing = _webui_request(
            f"/api/v1/models/model?id={agent['id']}", token=token, allow_missing=True
        )
        if existing is None:
            _webui_request("/api/v1/models/create", token=token, body=body)
            created += 1
        else:
            _webui_request(
                f"/api/v1/models/model/update?id={agent['id']}", token=token, body=body
            )
            updated += 1
    return f"{created} agent(s) created, {updated} updated"


def _webui_request(
    path: str, *, token: str, body: dict | None = None, allow_missing: bool = False
):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"http://{HOST}:{PORT}{path}",
        data=data,
        method="POST" if data else "GET",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with open_local(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if allow_missing and exc.code == 404:
            return None
        detail = exc.read().decode(errors="replace")[:200]
        raise Failure(f"Open WebUI {path} returned HTTP {exc.code}: {detail}") from exc
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise Failure(f"Open WebUI {path} failed: {exc}") from exc
