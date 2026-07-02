"""Central path definitions for the Kitty gateway.

All directory paths live here. Callers import from this module rather than
constructing paths inline. Call validate_dirs() once at startup to fail fast
if any essential directory is missing.
"""
import os as _os
from pathlib import Path

# Project root — two levels up from this file (gateway/paths.py → gateway/ → kitty/)
ROOT = Path(__file__).parent.parent

PROJECT_ROOT = ROOT  # Alias for backward compatibility

DATA_DIR = ROOT / "data"
LOGS_DIR = ROOT / "logs"
PROMPTS_DIR = ROOT / "prompts"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
KITTY_DATA_DIR = DATA_DIR / "kitty"
KITTY_DB_FILE = KITTY_DATA_DIR / "kitty.db"
DB_MIGRATIONS_DIR = ROOT / "gateway" / "migrations"
CONFIG_DIR = ROOT / "config"
USER_DIR = CONFIG_DIR / "USER"  # Jacob's TELOS identity files (mission/goals/etc.)
ACTION_TIERS_FILE = CONFIG_DIR / "action_tiers.json"  # signed risk-tier sheet (P3)
DESKTOP_DIR = DATA_DIR / "desktop"
DRAFTS_DIR = DATA_DIR / "drafts"  # local-only artifacts from note.draft actions (P3)
INBOX_FILE = DATA_DIR / "inbox.jsonl"
KITTY_TOKEN_LOG_FILE = DATA_DIR / "kitty_token_log.jsonl"
MODEL_DIGEST_DB = DATA_DIR / "model_digest.db"
BUILDS_DB = DATA_DIR / "builds.db"
TASK_DB = DATA_DIR / "task_queue.db"
TASK_OUTPUT_DIR = DATA_DIR / "task_outputs"
DESKTOP_LOG_FILE = LOGS_DIR / "desktop.log"
DESKTOP_PID_DIR = DESKTOP_DIR / "run"

LOG_FILE = LOGS_DIR / "gateway_trace.jsonl"

ESSENTIAL_DIRS = [DATA_DIR, LOGS_DIR, PROMPTS_DIR]

# LiteLLM proxy settings — single source of truth for the gateway.
# Use 127.0.0.1 to avoid localhost resolving to an address family the proxy
# did not bind on.
LITELLM_BASE = _os.environ.get("LITELLM_BASE", "http://127.0.0.1:8001")
LITELLM_KEY = _os.environ.get("LITELLM_KEY", "kitty-local-key-change-me")


def validate_env() -> None:
    """Warn at startup if security-critical env vars are missing."""
    import logging
    import os
    log = logging.getLogger("kitty.startup")
    if not os.environ.get("GATEWAY_SECRET"):
        log.warning(
            "GATEWAY_SECRET is not set — authentication fails closed unless "
            "KITTY_ENV=test. Configure a secret before desktop startup."
        )


def validate_dirs() -> None:
    """Fail fast at startup if any essential directory is missing."""
    missing = [str(p) for p in ESSENTIAL_DIRS if not p.exists()]
    if missing:
        raise RuntimeError(
            f"Kitty gateway cannot start — missing required directories: {missing}\n"
            "Run scripts/setup.sh or create them manually."
        )
