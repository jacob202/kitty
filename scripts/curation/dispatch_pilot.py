import json
import re
import subprocess
import time


def run_orca(args):
    cmd = ["orca"] + args + ["--json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        print(f"Error parsing Orca output: {result.stdout}")
        return None


def main():
    # 1. Create workers
    print("Creating worker terminals...")
    run_orca(["terminal", "create", "--worktree", "active", "--title", "librarian-1"])
    run_orca(["terminal", "create", "--worktree", "active", "--title", "librarian-2"])
    time.sleep(2)

    # 2. Get terminal handles
    terms = run_orca(["terminal", "list"])
    if not terms or "result" not in terms:
        print("Failed to list terminals")
        return

    handles = [
        t["handle"]
        for t in terms["result"]["terminals"]
        if "librarian" in t.get("title", "")
    ]
    if not handles:
        print("No worker handles found")
        return

    print(f"Found handles: {handles}")

    # 3. Get ready tasks
    tasks_resp = run_orca(["orchestration", "task-list", "--ready"])
    if not tasks_resp or "result" not in tasks_resp:
        print("No tasks found")
        return

    tasks = tasks_resp["result"]["tasks"][:10]
    print(f"Dispatching {len(tasks)} tasks...")

    for i, task in enumerate(tasks):
        task_id = task["id"]
        spec = task["spec"]
        target = handles[i % len(handles)]

        # Extract book_id and source_path from spec
        match = re.search(
            r"Create Smart Markdown Asset for: (.*) \(Source: (.*)\)", spec
        )
        if not match:
            print(f"Could not parse spec: {spec}")
            continue

        book_id, source_path = match.groups()

        # Build command
        worker_cmd = f'export PYTHONPATH=$PYTHONPATH:. && python scripts/curation/curation_worker.py "{book_id}" "{source_path}" && orca orchestration send --to @gemini --subject "Task Complete" --type worker_done --payload \'{{"task_id": "{task_id}"}}\''

        print(f"Dispatching {task_id} to {target}...")
        run_orca(
            ["terminal", "send", "--terminal", target, "--text", worker_cmd, "--enter"]
        )


if __name__ == "__main__":
    main()
