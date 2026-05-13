"""Thread-safe JSONL token telemetry to data/kitty_token_log.jsonl.

Schema (one object per line), aligned with AGENTS.md:
  ts, date, provider, model, operation, usage, metadata

``usage`` uses API-native prompt_tokens / completion_tokens / total_tokens when present.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.token_usage_log")

TOKEN_LOG_PATH: Path = DATA_DIR / "kitty_token_log.jsonl"
_lock = threading.Lock()


def normalize_usage_payload(raw: dict[str, Any] | None) -> dict[str, int]:
    """Normalize provider ``usage`` objects to int fields (best-effort)."""
    out: dict[str, int] = {}
    if not raw or not isinstance(raw, dict):
        return out

    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        val = raw.get(key)
        if isinstance(val, int) and val >= 0:
            out[key] = val

    if "total_tokens" not in out and "prompt_tokens" in out and "completion_tokens" in out:
        out["total_tokens"] = out["prompt_tokens"] + out["completion_tokens"]

    ctd = raw.get("completion_tokens_details")
    if isinstance(ctd, dict):
        rt = ctd.get("reasoning_tokens")
        if isinstance(rt, int) and rt >= 0:
            out["reasoning_tokens"] = rt

    ptd = raw.get("prompt_tokens_details")
    if isinstance(ptd, dict):
        ct = ptd.get("cached_tokens")
        if isinstance(ct, int) and ct >= 0:
            out["cached_tokens"] = ct

    return out


def log_llm_usage(
    provider: str,
    model: str,
    operation: str,
    usage: dict[str, int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append one usage row. Never raises — failures log at WARNING."""
    try:
        row = {
            "ts": time.time(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "provider": provider,
            "model": model,
            "operation": operation,
            "usage": usage or {},
            "metadata": metadata or {},
        }
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, ensure_ascii=False) + "\n"
        with _lock:
            with TOKEN_LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(line)
    except OSError as e:
        logger.warning("token log write failed: %s", e)
