from __future__ import annotations

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
from pathlib import Path

from .common import (
    DATA_DIR,
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
    request_json,
    runtime_env,
    verify_gateway,
)

# Open WebUI's WEBUI_AUTH=False signin creates admin@localhost when no user
# exists. The check and the insert are not atomic and `user.email` has no unique
# index, so the concurrent signins a first page load fires all pass the check and
# all insert — six identical admins on Jacob's Mac.
SYSTEM_ADMIN_EMAIL = "admin@localhost"
SYSTEM_ADMIN_PASSWORD = "admin"


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
    with sqlite3.connect(database) as connection:
        (count,) = connection.execute(
            "SELECT COUNT(*) FROM user WHERE email = ?", (SYSTEM_ADMIN_EMAIL,)
        ).fetchone()
    return int(count)


def _promote_sole_admin(connection: sqlite3.Connection) -> bool:
    """Give the one remaining account the admin role.

    The race leaves every row at DEFAULT_USER_ROLE, because 0.10.2 promotes the
    first user only when it is the single row *after* its own insert. Six rows
    meant nobody was promoted and Open WebUI showed "Account Activation
    Pending" with no second user to approve it.
    """
    row = connection.execute(
        "SELECT id, role FROM user WHERE email = ?", (SYSTEM_ADMIN_EMAIL,)
    ).fetchone()
    if row is None or row[1] == "admin":
        return False
    connection.execute("UPDATE user SET role = 'admin' WHERE id = ?", (row[0],))
    return True


def dedupe_system_admin() -> str:
    """Collapse duplicate ``admin@localhost`` rows. Safe to run on every start.

    Refuses rather than deleting when a duplicate owns rows: losing a chat to a
    tidy-up would be worse than leaving the duplicates in place.
    """
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


def claim_system_admin() -> None:
    """Sign in once, serially, so the browser cannot race the first signup."""
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
        with urllib.request.urlopen(request, timeout=30) as response:
            json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise Failure(
            f"Open WebUI rejected the system signin (HTTP {exc.code}): {detail}"
        ) from exc
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise Failure(f"Open WebUI system signin failed: {exc}") from exc


def direct_stream_smoke(*, accept_charges: bool) -> None:
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
    first_token_at: float | None = None
    parts: list[str] = []
    done = False
    gateway_error: str | None = None

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            for raw in response:
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

                # The gateway states the real cause here (gateway/chat_errors.py).
                # Reporting "no complete SSE response" instead threw that away and
                # sent whoever ran the smoke looking in the wrong place.
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
    print(f"Direct stream OK: TTFT={ttft:.2f}s total={total:.2f}s text={text!r}")


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_pid() -> int | None:
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None

    if not pid_alive(pid):
        PID_FILE.unlink(missing_ok=True)
        return None
    return pid


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


def start_webui(*, foreground: bool = False) -> None:
    ensure_dirs()
    install_openwebui()
    ensure_gateway_running()

    if read_pid():
        wait_for_webui(timeout=5)
        return
    if port_open():
        raise Failure(f"port {PORT} is already in use by another process")

    # While the server is down is the only safe moment to touch its database.
    print(f"accounts: {dedupe_system_admin()}")

    command = [str(OPENWEBUI_BIN), "serve", "--host", HOST, "--port", str(PORT)]
    if foreground:
        PID_FILE.write_text(f"{os.getpid()}\n", encoding="utf-8")
        # Python puts the working directory on sys.path, and Kitty's repo root
        # holds a top-level ``mcp`` package that shadows Open WebUI's MCP SDK.
        # The background branch already runs from SERVICE_ROOT; execve inherits
        # this process's directory, so it has to move first.
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
    PID_FILE.write_text(f"{process.pid}\n", encoding="utf-8")
    wait_for_webui()
    # One serial signin before a browser can open several at once. On a fresh
    # database this is the request that creates admin@localhost, so every later
    # signin takes the "user already exists" branch instead of racing signup.
    claim_system_admin()


def stop_webui() -> None:
    pid = read_pid()
    if pid is None:
        print("Open WebUI is not running")
        return

    try:
        target = -pid if os.getpgid(pid) == pid else pid
        os.kill(target, signal.SIGTERM)
    except ProcessLookupError:
        pass

    for _ in range(50):
        if not pid_alive(pid):
            break
        time.sleep(0.2)

    if pid_alive(pid):
        try:
            target = -pid if os.getpgid(pid) == pid else pid
            os.kill(target, signal.SIGKILL)
        except ProcessLookupError:
            pass

    PID_FILE.unlink(missing_ok=True)
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


def doctor() -> None:
    failures: list[str] = []
    if installed_version() != VERSION:
        failures.append(f"Open WebUI {VERSION} is not installed")

    checks = (
        verify_gateway,
        lambda: request_json(f"http://{HOST}:{PORT}/health", timeout=3),
    )
    for check in checks:
        try:
            check()
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
