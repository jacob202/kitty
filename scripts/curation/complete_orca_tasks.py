
import json
import subprocess


def run_orca(args):
    cmd = ["orca"] + args + ["--json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None

def main():
    # 1. Check inbox for worker_done
    inbox = run_orca(["orchestration", "check", "--types", "worker_done"])
    if not inbox or "result" not in inbox:
        print("Inbox empty or error")
        return

    messages = inbox["result"]["messages"]
    print(f"Found {len(messages)} completion messages.")

    for msg in messages:
        payload = json.loads(msg["payload"])
        task_id = payload.get("task_id")
        if task_id:
            print(f"Completing task: {task_id}")
            run_orca(["orchestration", "task-update", "--id", task_id, "--status", "completed"])

if __name__ == "__main__":
    main()
