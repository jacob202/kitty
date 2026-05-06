#!/usr/bin/env python3
"""Run a single scenario and print results as JSON — designed to be called in parallel."""

import json, sys, time
from pathlib import Path
from openai import OpenAI

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

MODEL_A = "qwen2.5-coder:7b"
MODEL_B = "deepseek-coder-v2:16b"
CLIENT_KWARGS = dict(base_url="http://localhost:11434/v1", api_key="ollama")

SYSTEM_PROMPT = """You are Kitty, Jacob's quiet, capable, and warm AI builder. 
You speak directly to Jacob. You are helpful but concise.
You manage the Kitty AI Router project in: {root}

--- TOOLS AVAILABLE ---
- run_command(command)
- read_file(path)
- write_file(path, content)
- modify_project_tasks(action, milestone_id, task, note, title) -> actions: add_task, mark_task_done, move_to_backlog, add_note, add_milestone
- search_web(query)
- launch_kitty()

--- TOOL USAGE RULES (STRICT!) ---
1. You ALREADY know the project state (see below). If Jacob asks "where are we", "project details", or just chats, you MUST reply in natural language. DO NOT use a tool.
2. NEVER use 'modify_project_tasks' to add conversational notes. ONLY use it if Jacob explicitly commands: "add a task", "mark done", etc.
3. If Jacob explicitly asks you to do an action (e.g. "run pytest", "add a task"), you MUST output ONLY a JSON block like this:
```json
{{
  "tool": "modify_project_tasks",
  "args": {{ "action": "add_task", "milestone_id": 1, "task": "example task" }}
}}
```

--- CURRENT PROJECT STATE ---
{project}
"""


def format_project(proj: dict) -> str:
    lines = [f"Name: {proj.get('project_name', '')}", f"Notes: {proj.get('notes', '')}", "Milestones:"]
    for m in proj.get('milestones', []):
        lines.append(f"  - [{m.get('id')}] {m.get('title')} ({m.get('status')})")
        lines.append(f"    Tasks: {len(m.get('tasks', []))} pending, {len(m.get('done_tasks', []))} done.")
    lines.append(f"Backlog: {len(proj.get('backlog', []))} items")
    return "\n".join(lines)


def run(client, model, user, project_state):
    sys_msg = SYSTEM_PROMPT.format(root=PROJECT_ROOT, project=format_project(project_state))
    messages = [{"role": "system", "content": sys_msg}, {"role": "user", "content": user}]
    t0 = time.time()
    try:
        resp = client.chat.completions.create(model=model, messages=messages, max_tokens=400, temperature=0.7)
        text = resp.choices[0].message.content or ""
    except Exception as e:
        text = f"[ERROR] {e}"
    return text, time.time() - t0


def extract_json(text):
    import re
    block = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    raw = block.group(1) if block else text
    start = raw.find('{')
    if start == -1:
        return None
    try:
        return json.JSONDecoder().raw_decode(raw[start:])[0]
    except json.JSONDecodeError:
        return None


if __name__ == "__main__":
    scenario_idx = int(sys.argv[1])
    client = OpenAI(**CLIENT_KWARGS)

    project_file = PROJECT_ROOT / "project.json"
    if project_file.exists():
        with open(project_file) as f:
            project_state = json.load(f)
    else:
        project_state = {"project_name": "Kitty", "milestones": [{"id": 1, "title": "Core", "status": "doing", "tasks": ["t1"], "done_tasks": []}], "notes": "", "backlog": []}

    SCENARIOS = [
        ("Status query", "Hey Kitty, where are we at with the project right now?"),
        ("Task assignment", "Add a task to milestone 1 to improve the JSON parser"),
        ("Run command", "Run the test suite for me"),
        ("Inline audit", "What bug should I be most worried about in kitty_builder right now?"),
        ("Read file", "Read the main.py file and tell me what it does"),
        ("Refactoring advice", "Is it worth adding a retry decorator to all the API calls? What are the tradeoffs?"),
    ]

    name, user = SCENARIOS[scenario_idx]
    text_a, t_a = run(client, MODEL_A, user, project_state)
    text_b, t_b = run(client, MODEL_B, user, project_state)

    json_a = extract_json(text_a)
    json_b = extract_json(text_b)

    result = {
        "scenario": name,
        "A": {"model": MODEL_A, "time": round(t_a, 1), "length": len(text_a), "tool": (json_a or {}).get("tool"), "text": text_a[:300]},
        "B": {"model": MODEL_B, "time": round(t_b, 1), "length": len(text_b), "tool": (json_b or {}).get("tool"), "text": text_b[:300]},
    }
    print(json.dumps(result))