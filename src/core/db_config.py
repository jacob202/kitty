"""
Centralized database path configuration.

All SQLite/DuckDB paths are defined here so modules don't invent their own
conventions. Uses a single data root (default: project_root/data/).
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data"
DATA_ROOT.mkdir(exist_ok=True)

DB_PATHS = {
    "event_store": DATA_ROOT / "event_store.db",
    "job_queue": DATA_ROOT / "job_queue.db",
    "circuit_breaker": DATA_ROOT / "circuit_breaker.db",
    "profiler": DATA_ROOT / "db" / "orange_lab_pka.db",
    "ingest_registry": DATA_ROOT / "ingest_registry.db",
    "mem0_checkpoints": DATA_ROOT / "session_checkpoints.db",
    "mem0_history": DATA_ROOT / "mem0_history.db",
    "performance_metrics": DATA_ROOT / "performance_metrics.db",
    "hardware_bom": DATA_ROOT / "hardware_bom.db",
    "honcho": DATA_ROOT / "honcho.db",
    "journal": DATA_ROOT / "journal.db",
}


def get_db_path(name: str) -> Path:
    """Get a database path by name, ensuring parent dirs exist."""
    if name not in DB_PATHS:
        raise ValueError(f"Unknown database: {name}. Available: {list(DB_PATHS.keys())}")
    path = DB_PATHS[name]
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
