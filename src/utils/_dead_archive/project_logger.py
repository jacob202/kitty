import datetime
import json
from pathlib import Path

LOG_DIR = Path("docs/logs")
LOG_FILE = LOG_DIR / "session_logs.jsonl"

def _ensure_log_dir_exists():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

def log_activity(event_type: str, details: dict):
    _ensure_log_dir_exists()
    timestamp = datetime.datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "event_type": event_type,
        "details": details
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

if __name__ == "__main__":
    # Example usage:
    log_activity("test_event", {"message": "This is a test log entry."})
    log_activity("tool_invocation", {"tool": "read_file", "file": "README.md"})
    print(f"Logged example activities to {LOG_FILE}")
