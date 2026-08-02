from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request

from .common import (DATA_DIR, HOST, LOG_FILE, OPENWEBUI_BIN, PID_FILE, PORT, SECRET_FILE,
                     SERVICE_ROOT, VERSION, Failure, ensure_dirs, ensure_gateway_running,
                     install_openwebui, installed_version, request_json, runtime_env, verify_gateway)


def direct_stream_smoke(*, accept_charges: bool) -> None:
    if not accept_charges:
        raise Failure("real streaming smoke may use provider credits; rerun with --accept-charges")
    base, secret = verify_gateway()
    body = json.dumps({"model": "kitty-default", "messages": [{"role": "user", "content": "Reply with exactly: ready"}], "stream": True}).encode()
    request = urllib.request.Request(f"{base}/v1/chat/completions", data=body, method="POST",
        headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json", "Accept": "text/event-stream"})
    started, first = time.monotonic(), None
    parts: list[str] = []
    done = False
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
                    content = event["choices"][0]["delta"].get("content")
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    continue
                if isinstance(content, str) and content:
                    first = first or time.monotonic()
                    parts.append(content)
    except urllib.error.HTTPError as exc:
        raise Failure(f"streaming smoke returned HTTP {exc.code}: {exc.read().decode(errors='replace')[:500]}") from exc
    except urllib.error.URLError as exc:
        raise Failure(f"streaming smoke failed: {exc.reason}") from exc
    if first is None or not done:
        raise Failure("streaming smoke did not produce a complete SSE response")
    print(f"Direct stream OK: TTFT={first-started:.2f}s total={time.monotonic()-started:.2f}s text={''.join(parts).strip()!r}")


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_pid() -> int | None:
    try:
        pid = int(PID_FILE.read_text().strip())
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
    deadline, last = time.monotonic() + timeout, ""
    while time.monotonic() < deadline:
        try:
            request_json(f"http://{HOST}:{PORT}/health", timeout=3)
            print(f"Open WebUI ready: http://{HOST}:{PORT}")
            return
        except Failure as exc:
            last = str(exc)
            time.sleep(1)
    raise Failure(f"Open WebUI did not become healthy: {last}; see {LOG_FILE}")


def start_webui(*, foreground: bool = False) -> None:
    ensure_dirs(); install_openwebui(); ensure_gateway_running()
    if read_pid():
        wait_for_webui(timeout=5)
        return
    if port_open():
        raise Failure(f"port {PORT} is already in use by another process")
    command = [str(OPENWEBUI_BIN), "serve", "--host", HOST, "--port", str(PORT)]
    if foreground:
        PID_FILE.write_text(f"{os.getpid()}\n")
        os.execve(str(OPENWEBUI_BIN), command, runtime_env())
    with LOG_FILE.open("ab", buffering=0) as log:
        process = subprocess.Popen(command, cwd=SERVICE_ROOT, env=runtime_env(), stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    PID_FILE.write_text(f"{process.pid}\n")
    wait_for_webui()


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
        try: os.kill(-pid if os.getpgid(pid) == pid else pid, signal.SIGKILL)
        except ProcessLookupError: pass
    PID_FILE.unlink(missing_ok=True)
    print("Open WebUI stopped")


def print_status() -> None:
    pid = read_pid()
    print(f"service root : {SERVICE_ROOT}\nversion      : {installed_version() or 'not installed'}\ndata         : {DATA_DIR}")
    print(f"url          : http://{HOST}:{PORT}\nprocess      : {'running pid '+str(pid) if pid else 'not running'}\nport         : {'open' if port_open() else 'closed'}")
    try: verify_gateway()
    except Failure as exc: print(f"gateway      : FAIL — {exc}")
    try:
        request_json(f"http://{HOST}:{PORT}/health", timeout=3); print("open webui   : healthy")
    except Failure as exc: print(f"open webui   : FAIL — {exc}")


def open_browser() -> None:
    url = f"http://{HOST}:{PORT}"
    subprocess.run(["open", url], check=False) if shutil.which("open") else print(url)


def show_logs() -> None:
    ensure_dirs(); LOG_FILE.touch(exist_ok=True)
    subprocess.run(["tail", "-n", "120", "-F", LOG_FILE], check=False)


def doctor() -> None:
    failures: list[str] = []
    if installed_version() != VERSION: failures.append(f"Open WebUI {VERSION} is not installed")
    for check in (verify_gateway, lambda: request_json(f"http://{HOST}:{PORT}/health", timeout=3)):
        try: check()
        except Failure as exc: failures.append(str(exc))
    if not SECRET_FILE.exists(): failures.append(f"missing persistent WebUI secret: {SECRET_FILE}")
    if not DATA_DIR.exists(): failures.append(f"missing data directory: {DATA_DIR}")
    if failures:
        for item in failures: print(f"FAIL: {item}")
        raise Failure(f"{len(failures)} doctor check(s) failed")
    print("All Open WebUI doctor checks passed")
