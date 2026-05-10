from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR     = PROJECT_ROOT / "data"
PROMPTS_DIR  = PROJECT_ROOT / "prompts"
LOGS_DIR     = PROJECT_ROOT / "logs"

def validate_dirs() -> None:
    """Assert essential directories exist. Call once at startup."""
    for d in (DATA_DIR, PROMPTS_DIR, LOGS_DIR):
        if not d.exists():
            raise RuntimeError(f"Required directory missing: {d}")
