from __future__ import annotations

import os
import plistlib
import shutil
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .common import (
    BACKUP_ROOT,
    DATA_DIR,
    DESKTOP_SHORTCUT,
    HOST,
    KITTY_UI_PORT,
    LAUNCH_AGENT,
    LOG_FILE,
    PORT,
    ROOT,
    SECRET_FILE,
    SERVICE_ROOT,
    VERSION,
    Failure,
    ensure_dirs,
    ensure_webui_secret,
    install_openwebui,
    run,
    verify_gateway,
)
from .service import (
    direct_stream_smoke,
    open_browser,
    port_open,
    read_pid,
    start_webui,
    stop_webui,
    wait_for_webui,
    webui_db_path,
)


def install_launch_agent() -> None:
    ensure_dirs()
    install_openwebui()
    ensure_webui_secret()
    LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)

    python = ROOT / "venv/bin/python"
    if not python.exists():
        python = Path(sys.executable).resolve()

    plist = {
        "Label": "com.kitty.openwebui",
        "ProgramArguments": [
            str(python),
            str(ROOT / "scripts/openwebui_local.py"),
            "service",
        ],
        # Never the repo root: Python puts the working directory on sys.path and
        # Kitty's top-level ``mcp`` package shadows Open WebUI's MCP SDK from
        # there. PYTHONPATH is deliberately absent rather than empty — launchd
        # does not inherit the shell's copy, and an empty PYTHONPATH would put
        # the working directory back on the path.
        "WorkingDirectory": str(SERVICE_ROOT),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ProcessType": "Interactive",
        "StandardOutPath": str(LOG_FILE),
        "StandardErrorPath": str(LOG_FILE),
        "EnvironmentVariables": {
            "PATH": (
                "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:"
                f"{Path.home() / '.local/bin'}"
            ),
            "PYTHONNOUSERSITE": "1",
            "KITTY_OPENWEBUI_HOME": str(SERVICE_ROOT),
            "KITTY_OPENWEBUI_VERSION": VERSION,
            "KITTY_OPENWEBUI_PORT": str(PORT),
            "KITTY_OPENWEBUI_HOST": HOST,
        },
    }
    with LAUNCH_AGENT.open("wb") as handle:
        plistlib.dump(plist, handle, sort_keys=False)

    domain = f"gui/{os.getuid()}"
    run(["launchctl", "bootout", domain, LAUNCH_AGENT], check=False)
    stop_webui()
    run(["launchctl", "bootstrap", domain, LAUNCH_AGENT])
    run(
        ["launchctl", "enable", f"{domain}/com.kitty.openwebui"],
        check=False,
    )
    wait_for_webui()
    # rollback repoints this at the Next.js UI, so re-installing has to claim it
    # back or the Desktop shortcut opens the interface Jacob just left.
    write_desktop_shortcut()
    print(f"Installed login service: {LAUNCH_AGENT}")


def uninstall_launch_agent() -> None:
    domain = f"gui/{os.getuid()}"
    run(["launchctl", "bootout", domain, LAUNCH_AGENT], check=False)
    stop_webui()
    LAUNCH_AGENT.unlink(missing_ok=True)
    print("Removed Open WebUI login service")


def backup_state(*, label: str = "manual") -> Path:
    """Copy the chat database and secret somewhere restore can find them.

    sqlite3's own backup API rather than a file copy: Open WebUI runs in WAL
    mode, so copying webui.db while it serves gives a database missing whatever
    is still in the write-ahead log.
    """
    ensure_dirs()
    database = webui_db_path()
    if not database.exists():
        raise Failure(f"nothing to back up: {database} does not exist")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = BACKUP_ROOT / f"{stamp}-{label}"
    target.mkdir(parents=True, exist_ok=False)
    target.chmod(0o700)

    source = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        destination = sqlite3.connect(target / "webui.db")
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()

    # Leave one file behind, not three: the sidecars the backup connection
    # created are empty, and a stale -wal next to a restored database is a way
    # to silently resurrect rows the restore was meant to drop.
    for sidecar in ("webui.db-wal", "webui.db-shm"):
        (target / sidecar).unlink(missing_ok=True)

    if SECRET_FILE.exists():
        shutil.copy2(SECRET_FILE, target / SECRET_FILE.name)
        (target / SECRET_FILE.name).chmod(0o600)

    print(f"Backup written: {target}")
    return target


def latest_backup() -> Path:
    candidates = sorted(p for p in BACKUP_ROOT.glob("*") if (p / "webui.db").exists())
    if not candidates:
        raise Failure(f"no backups found under {BACKUP_ROOT}")
    return candidates[-1]


def restore_state(source: str | None) -> None:
    """Put a backup back. Refuses while the service is up — a live server holds
    the WAL open and would write over whatever was just restored."""
    if read_pid() or port_open():
        raise Failure(
            "Open WebUI is still running; run 'openwebui_local.py down' first"
        )

    chosen = Path(source).expanduser() if source else latest_backup()
    database = chosen / "webui.db"
    if not database.exists():
        raise Failure(f"{chosen} does not contain a webui.db")

    ensure_dirs()
    # The pre-restore copy is the undo button for a restore of the wrong backup.
    if webui_db_path().exists():
        backup_state(label="pre-restore")

    for stale in ("webui.db-wal", "webui.db-shm"):
        (DATA_DIR / stale).unlink(missing_ok=True)
    shutil.copy2(database, webui_db_path())

    secret = chosen / SECRET_FILE.name
    if secret.exists():
        shutil.copy2(secret, SECRET_FILE)
        SECRET_FILE.chmod(0o600)

    print(f"Restored from {chosen}; start with 'openwebui_local.py up'")


def rollback_to_kitty_ui() -> None:
    """Hand the day back to the existing Kitty UI.

    ``./kitty install`` only manages gateway and LiteLLM, so it is ``./kitty up``
    that actually serves the Next.js UI. Rolling back without it would leave
    Jacob with the Open WebUI shortcut gone and nothing to open instead.
    """
    if webui_db_path().exists():
        backup_state(label="pre-rollback")
    uninstall_launch_agent()
    # `./kitty install` is idempotent and leaves the launchd gateway/LiteLLM
    # alone; `./kitty up` boots those same jobs out and would take the whole
    # stack down on the way to putting the UI back.
    run([ROOT / "kitty", "install"], cwd=ROOT)
    run([ROOT / "kitty", "ui"], cwd=ROOT, check=False)

    # Not request_json: the Next.js UI serves HTML, so this is a reachability
    # check, not a contract check.
    url = f"http://{HOST}:{KITTY_UI_PORT}"
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{url}/", timeout=3):
                break
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    else:
        raise Failure(
            f"rolled back the login service, but the Kitty UI never answered on {url}. "
            "Run './kitty status' and './kitty logs'."
        )

    write_desktop_shortcut(url=url)
    print(
        f"Rolled back to the Kitty UI at {url}. Open WebUI data is untouched at "
        f"{DATA_DIR}; 'openwebui_local.py install-autostart' brings it back."
    )


def write_desktop_shortcut(*, url: str | None = None) -> None:
    DESKTOP_SHORTCUT.parent.mkdir(parents=True, exist_ok=True)
    with DESKTOP_SHORTCUT.open("wb") as handle:
        plistlib.dump({"URL": url or f"http://{HOST}:{PORT}"}, handle)
    print(f"Desktop shortcut ready: {DESKTOP_SHORTCUT}")


def bootstrap(*, accept_charges: bool, no_autostart: bool) -> None:
    if webui_db_path().exists():
        backup_state(label="pre-bootstrap")
    start_webui()
    if accept_charges:
        direct_stream_smoke(accept_charges=True)
    else:
        print("Direct provider stream smoke skipped (use --accept-charges to run it)")

    if not no_autostart:
        stop_webui()
        run([ROOT / "kitty", "down"], cwd=ROOT)
        run([ROOT / "kitty", "install"], cwd=ROOT)

        last_error = ""
        for _ in range(30):
            try:
                verify_gateway()
                break
            except Failure as exc:
                last_error = str(exc)
                time.sleep(1)
        else:
            raise Failure(
                f"Gateway launchd service did not become healthy: {last_error}"
            )

        install_launch_agent()

    write_desktop_shortcut()
    print("Tomorrow-ready checks complete")
    open_browser()
