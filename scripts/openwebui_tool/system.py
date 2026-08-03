from __future__ import annotations

import json
import os
import plistlib
import shutil
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from .common import (
    BACKUP_ROOT,
    DATA_DIR,
    DESKTOP_SHORTCUT,
    HOST,
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
    kitty_ui_port,
    open_local,
    run,
    verify_gateway,
)
from .service import (
    claim_system_admin,
    direct_stream_smoke,
    ensure_agents,
    open_browser,
    port_open,
    read_pid,
    start_webui,
    stop_webui,
    wait_for_webui,
    webui_db_path,
)


def _launch_domain() -> str:
    return f"gui/{os.getuid()}"


def _verify_launch_agent_enabled(domain: str) -> None:
    result = run(["launchctl", "print-disabled", domain], capture=True)
    disabled_marker = '"com.kitty.openwebui" => true'
    if disabled_marker in result.stdout:
        raise Failure("launchd still reports com.kitty.openwebui as disabled")


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
    temporary = LAUNCH_AGENT.with_suffix(".plist.tmp")
    with temporary.open("wb") as handle:
        plistlib.dump(plist, handle, sort_keys=False)
    os.replace(temporary, LAUNCH_AGENT)

    domain = _launch_domain()
    run(["launchctl", "bootout", domain, LAUNCH_AGENT], check=False)
    stop_webui()
    run(["launchctl", "enable", f"{domain}/com.kitty.openwebui"])
    _verify_launch_agent_enabled(domain)
    run(["launchctl", "bootstrap", domain, LAUNCH_AGENT])
    wait_for_webui()

    # A direct install-autostart on a fresh database must establish the same
    # usable single-user state as bootstrap, not merely leave an HTTP process up.
    token = claim_system_admin()
    print(f"agents: {ensure_agents(token)}")
    write_desktop_shortcut()
    print(f"Installed login service: {LAUNCH_AGENT}")


def uninstall_launch_agent() -> None:
    domain = _launch_domain()
    run(["launchctl", "bootout", domain, LAUNCH_AGENT], check=False)
    stop_webui()
    LAUNCH_AGENT.unlink(missing_ok=True)
    print("Removed Open WebUI login service")


def _validate_database(path: Path) -> None:
    if not path.exists():
        raise Failure(f"database does not exist: {path}")
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            row = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error as exc:
        raise Failure(f"cannot validate SQLite database {path}: {exc}") from exc
    if row is None or row[0] != "ok":
        detail = row[0] if row else "no quick_check result"
        raise Failure(f"SQLite validation failed for {path}: {detail}")


def backup_state(*, label: str = "manual") -> Path:
    """Publish a verified SQLite backup atomically.

    Open WebUI uses WAL mode, so the backup API is required. A failed backup is
    kept under a hidden temporary name and removed; restore never sees it as a
    candidate.
    """
    ensure_dirs()
    database = webui_db_path()
    if not database.exists():
        raise Failure(f"nothing to back up: {database} does not exist")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = BACKUP_ROOT / f"{stamp}-{label}"
    if target.exists():
        target = BACKUP_ROOT / f"{stamp}-{label}-{time.time_ns() % 1_000_000:06d}"
    temporary = Path(tempfile.mkdtemp(prefix=".backup-", dir=BACKUP_ROOT))
    temporary.chmod(0o700)

    try:
        source = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            destination = sqlite3.connect(temporary / "webui.db")
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()

        for sidecar in ("webui.db-wal", "webui.db-shm"):
            (temporary / sidecar).unlink(missing_ok=True)
        (temporary / "webui.db").chmod(0o600)
        _validate_database(temporary / "webui.db")

        if SECRET_FILE.exists():
            shutil.copy2(SECRET_FILE, temporary / SECRET_FILE.name)
            (temporary / SECRET_FILE.name).chmod(0o600)

        (temporary / "backup.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "openwebui_version": VERSION,
                    "label": label,
                    "created_at": time.time(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (temporary / "backup.json").chmod(0o600)
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    print(f"Backup written: {target}")
    return target


def latest_backup() -> Path:
    candidates: list[Path] = []
    for candidate in sorted(BACKUP_ROOT.glob("*")):
        if candidate.name.startswith(".") or not candidate.is_dir():
            continue
        database = candidate / "webui.db"
        try:
            _validate_database(database)
        except Failure:
            continue
        candidates.append(candidate)
    if not candidates:
        raise Failure(f"no valid backups found under {BACKUP_ROOT}")
    return candidates[-1]


def _atomic_copy(source: Path, destination: Path, *, validate_sqlite: bool = False) -> None:
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    temporary.unlink(missing_ok=True)
    try:
        shutil.copy2(source, temporary)
        temporary.chmod(0o600)
        if validate_sqlite:
            _validate_database(temporary)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def restore_state(source: str | None) -> None:
    """Restore only after a verified copy is ready for atomic replacement."""
    if read_pid() or port_open():
        raise Failure(
            "Open WebUI is still running; run 'openwebui_local.py down' first"
        )

    chosen = Path(source).expanduser() if source else latest_backup()
    database = chosen / "webui.db"
    _validate_database(database)

    ensure_dirs()
    if webui_db_path().exists():
        backup_state(label="pre-restore")

    for stale in ("webui.db-wal", "webui.db-shm"):
        (DATA_DIR / stale).unlink(missing_ok=True)
    _atomic_copy(database, webui_db_path(), validate_sqlite=True)

    secret = chosen / SECRET_FILE.name
    if secret.exists():
        _atomic_copy(secret, SECRET_FILE)

    print(f"Restored from {chosen}; start with 'openwebui_local.py up'")


def _wait_for_kitty_identity(url: str, *, attempts: int = 30) -> None:
    identity_url = f"{url}/api/identity"
    last_error = "no response"
    for _ in range(attempts):
        try:
            with open_local(identity_url, timeout=3) as response:
                payload = json.load(response)
            if payload.get("product") == "kitty" and payload.get("surface") == "nextjs":
                return
            last_error = f"unexpected identity payload: {payload!r}"
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise Failure(
        f"Kitty UI identity check failed at {identity_url}: {last_error}. "
        "Run './kitty status' and './kitty logs'."
    )


def rollback_to_kitty_ui() -> None:
    """Hand the day back to the canonical Kitty UI without removing its services."""
    if webui_db_path().exists():
        backup_state(label="pre-rollback")
    uninstall_launch_agent()
    run([ROOT / "kitty", "install"], cwd=ROOT)
    run([ROOT / "kitty", "ui"], cwd=ROOT, check=False)

    url = f"http://127.0.0.1:{kitty_ui_port()}"
    _wait_for_kitty_identity(url)
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
    if not no_autostart and not accept_charges:
        raise Failure(
            "autostart requires the real provider smoke; rerun with --accept-charges "
            "or use --no-autostart"
        )

    if webui_db_path().exists():
        backup_state(label="pre-bootstrap")
    start_webui()
    if accept_charges:
        direct_stream_smoke(accept_charges=True)
    else:
        print("Direct provider stream smoke skipped for this non-autostart run")

    if not no_autostart:
        stop_webui()
        # Reload only Kitty-owned launch services. `./kitty down` kills whatever
        # happens to own Kitty's ports and is not safe in an installer.
        run([ROOT / "kitty", "install"], cwd=ROOT)
        verify_gateway()
        install_launch_agent()

    write_desktop_shortcut()
    print("Tomorrow-ready checks complete")
    open_browser()
