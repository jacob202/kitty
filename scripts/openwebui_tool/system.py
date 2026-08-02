from __future__ import annotations

import os
import plistlib
import sys
import time
from pathlib import Path

from .common import (
    DESKTOP_SHORTCUT,
    HOST,
    LAUNCH_AGENT,
    LOG_FILE,
    PORT,
    ROOT,
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
    start_webui,
    stop_webui,
    wait_for_webui,
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
        "WorkingDirectory": str(ROOT),
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
    print(f"Installed login service: {LAUNCH_AGENT}")


def uninstall_launch_agent() -> None:
    domain = f"gui/{os.getuid()}"
    run(["launchctl", "bootout", domain, LAUNCH_AGENT], check=False)
    stop_webui()
    LAUNCH_AGENT.unlink(missing_ok=True)
    print("Removed Open WebUI login service")


def write_desktop_shortcut() -> None:
    DESKTOP_SHORTCUT.parent.mkdir(parents=True, exist_ok=True)
    with DESKTOP_SHORTCUT.open("wb") as handle:
        plistlib.dump({"URL": f"http://{HOST}:{PORT}"}, handle)
    print(f"Desktop shortcut ready: {DESKTOP_SHORTCUT}")


def bootstrap(*, accept_charges: bool, no_autostart: bool) -> None:
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
