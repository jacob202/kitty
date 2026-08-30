"""Network reachability routes (phone-access status)."""
from __future__ import annotations

import json
import logging
import subprocess

from fastapi import APIRouter

logger = logging.getLogger("kitty.routes.network")

router = APIRouter(tags=["network"])

UI_PORT = 4000

_NOT_CONNECTED = {"ok": False, "tailnet_ip": None, "ui_url": None}


@router.get("/network/tailnet")
def get_tailnet_status() -> dict:
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            return _NOT_CONNECTED
        status = json.loads(result.stdout)
        tailnet_ip = status["Self"]["TailscaleIPs"][0]
    except Exception as exc:  # noqa: BLE001  # tailscale CLI absence/output shape is heterogeneous across platforms
        logger.info("tailscale status unavailable: %s", exc)
        return _NOT_CONNECTED

    return {"ok": True, "tailnet_ip": tailnet_ip, "ui_url": f"http://{tailnet_ip}:{UI_PORT}"}
