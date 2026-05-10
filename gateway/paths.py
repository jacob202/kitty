"""Central path definitions for the Kitty gateway.

All directory paths live here. Callers import from this module rather than
constructing paths inline. Call validate_dirs() once at startup to fail fast
if any essential directory is missing.
"""
from pathlib import Path

# Project root — two levels up from this file (gateway/paths.py → gateway/ → kitty/)
ROOT = Path(__file__).parent.parent

DATA_DIR = ROOT / "data"
LOGS_DIR = ROOT / "logs"
PROMPTS_DIR = ROOT / "prompts"
KNOWLEDGE_DIR = ROOT / "data" / "knowledge"
CONFIG_DIR = ROOT / "config"

LOG_FILE = LOGS_DIR / "gateway_trace.jsonl"

ESSENTIAL_DIRS = [DATA_DIR, LOGS_DIR, PROMPTS_DIR]


def validate_dirs() -> None:
    """Fail fast at startup if any essential directory is missing."""
    missing = [str(p) for p in ESSENTIAL_DIRS if not p.exists()]
    if missing:
        raise RuntimeError(
            f"Kitty gateway cannot start — missing required directories: {missing}\n"
            "Run scripts/setup.sh or create them manually."
        )
