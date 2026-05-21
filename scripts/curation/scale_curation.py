import subprocess
import json
import time
import re
import sqlite3
from pathlib import Path

DB_PATH = Path("data/curation_status.db")


def run_orca(args):
    cmd = ["orca"] + args + ["--json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except:
        return None


def main():
    batch_size = 100

    # 1. Get ready tasks from Orca
    tasks_resp = run_orca(["orchestration", "task-list", "--status", "ready"])
    if not tasks_resp or "result" not in tasks_resp:
        print("No ready tasks found.")
        return

    tasks = tasks_resp["result"]["tasks"][:batch_size]
    print(f"Found {len(tasks)} tasks ready for dispatch.")

    # 2. Ensure 4 worker terminals exist
    worker_names = ["librarian-1", "librarian-2", "librarian-3", "librarian-4"]
    for name in worker_names:
        print(f"Creating/Ensuring worker: {name}")
        run_orca(["terminal", "create", "--worktree", "active", "--title", name])

    time.sleep(3)

    terms = run_orca(["terminal", "list"])
    handles = [
        t["handle"]
        for t in terms["result"]["terminals"]
        if "librarian" in t.get("title", "")
    ]

    print(f"Dispatching to {len(handles)} workers...")

    # 3. Dispatch loop
    for i, task in enumerate(tasks):
        task_id = task["id"]
        spec = task["spec"]
        target = handles[i % len(handles)]

        # Parse spec
        match = re.search(
            r"Create Smart Markdown Asset for: (.*) \(Source: (.*)\)", spec
        )
        if not match:
            continue
        book_id, source_path = match.groups()

        worker_cmd = f'export PYTHONPATH=$PYTHONPATH:. && python scripts/curation/curation_worker.py "{book_id}" "{source_path}" && orca orchestration send --to @gemini --subject "Task Complete" --type worker_done --payload \'{{"task_id": "{task_id}"}}\''

        run_orca(
            ["terminal", "send", "--terminal", target, "--text", worker_cmd, "--enter"]
        )
        if i % 10 == 0:
            print(f" [{i+1}/{len(tasks)}] Dispatched...")


if __name__ == "__main__":
    main()
