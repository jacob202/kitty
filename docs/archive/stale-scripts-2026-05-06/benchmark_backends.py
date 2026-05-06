#!/usr/bin/env python3
"""Side-by-side benchmark comparing two model backends on kitty_builder scenarios.

Uses Ollama as the runtime (already running at localhost:11434) to compare:
  - mlx-community/Qwen2.5-3B-Instruct-4bit  (4-bit, ~2GB VRAM)
  - qwen2.5-coder:7b                     (7B, ~4.7GB VRAM)
  
Both via Ollama's local inference server (Apple Silicon-native).
"""

import json, sys, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from openai import OpenAI

MODEL_A = "qwen2.5-coder:7b"
MODEL_B = "deepseek-coder-v2:16b"

# System prompt (identical to kitty_builder's SYSTEM_PROMPT)
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


def build_messages(user_input: str, project_state: dict) -> list:
    sys_msg = SYSTEM_PROMPT.format(root=PROJECT_ROOT, project=format_project(project_state))
    return [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": user_input},
    ]


def extract_json(text: str) -> dict | None:
    block = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL) if 're' in dir() else None
    import re as _re
    block = _re.search(r'```json\s*(.*?)\s*```', text, _re.DOTALL)
    raw = block.group(1) if block else text
    start = raw.find('{')
    if start == -1:
        return None
    try:
        decoder = json.JSONDecoder()
        obj, end = decoder.raw_decode(raw[start:])
        return obj
    except json.JSONDecodeError:
        return None


def score(name: str, text: str, s: dict) -> dict:
    text_lower = text.lower()
    tool_json = extract_json(text)
    tool_found = tool_json is not None and "tool" in tool_json
    passed = True
    reason = "OK"

    if tool_found and not s["expect_tool"]:
        passed = False
        reason = "Emitted tool when shouldn't have"
    if not tool_found and s["expect_tool"]:
        passed = False
        reason = "Expected a tool call but none found"
    elif s["avoid_tool"] and tool_found:
        passed = False
        reason = "Emitted tool when should respond directly"

    if s.get("text_contains") and s["text_contains"] not in text_lower:
        passed = False
        reason = f"Expected '{s['text_contains']}' in response"

    if s.get("tool_action") and tool_json:
        if tool_json.get("tool") != s["tool_action"]:
            passed = False
            reason = f"Wrong tool: expected '{s['tool_action']}', got '{tool_json.get('tool')}'"
        if s.get("tool_milestone_id") is not None:
            args = tool_json.get("args", {})
            mid = args.get("milestone_id") or args.get("milestone_number")
            if mid != s["tool_milestone_id"]:
                passed = False
                reason = f"Wrong milestone_id: expected {s['tool_milestone_id']}, got {mid}"

    return {
        "passed": passed,
        "reason": reason,
        "tool_emitted": tool_found,
        "tool_name": tool_json.get("tool") if tool_json else None,
        "length": len(text),
        "preview": text[:250].strip(),
    }


# ── Test scenarios ─────────────────────────────────────────────────────────────
SCENARIOS = [
    {
        "name": "Status query",
        "description": "Should reply conversationally about milestones — no tool",
        "user": "Hey Kitty, where are we at with the project right now?",
        "expect_tool": False,
        "avoid_tool": False,
        "text_contains": "milestone",
    },
    {
        "name": "Task assignment",
        "description": "Should emit add_task JSON tool call with correct milestone_id",
        "user": "Add a task to milestone 1 to improve the JSON parser",
        "expect_tool": True,
        "avoid_tool": False,
        "text_contains": "tool",
        "tool_action": "add_task",
        "tool_milestone_id": 1,
    },
    {
        "name": "Run command",
        "description": "Should emit run_command or launch_kitty JSON tool call",
        "user": "Run the test suite for me",
        "expect_tool": True,
        "avoid_tool": False,
        "text_contains": "tool",
    },
    {
        "name": "Inline audit",
        "description": "Should give direct advice, not emit a tool",
        "user": "What bug should I be most worried about in kitty_builder right now?",
        "expect_tool": False,
        "avoid_tool": True,
        "text_contains": None,
    },
    {
        "name": "Read file",
        "description": "Should emit read_file JSON tool call",
        "user": "Read the main.py file and tell me what it does",
        "expect_tool": True,
        "avoid_tool": False,
        "text_contains": "tool",
    },
    {
        "name": "Refactoring advice",
        "description": "Should give substantive direct advice mentioning retry logic",
        "user": "Is it worth adding a retry decorator to all the API calls? What are the tradeoffs?",
        "expect_tool": False,
        "avoid_tool": True,
        "text_contains": "retry",
    },
]


def run_scenario(client: OpenAI, model: str, user: str, project_state: dict) -> tuple[str, float]:
    messages = build_messages(user, project_state)
    start = time.time()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=600,
            temperature=0.7,
        )
        text = resp.choices[0].message.content or ""
    except Exception as e:
        text = f"[ERROR] {e}"
    elapsed = time.time() - start
    return text, elapsed


def run_report(project_state: dict):
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=120)

    print("\n" + "=" * 90)
    print("KITTYBUILDER BACKEND COMPARISON")
    print(f"  Model A (7B Qwen): {MODEL_A}")
    print(f"  Model B (16B DeepSeek): {MODEL_B}")
    print("=" * 90)

    results = []
    for s in SCENARIOS:
        name = s["name"]
        user = s["user"]

        text_a, t_a = run_scenario(client, MODEL_A, user, project_state)
        text_b, t_b = run_scenario(client, MODEL_B, user, project_state)

        score_a = score(name, text_a, s)
        score_b = score(name, text_b, s)

        results.append({
            "name": name,
            "desc": s["description"],
            "A": {**score_a, "time": round(t_a, 1), "text": text_a},
            "B": {**score_b, "time": round(t_b, 1), "text": text_b},
        })

    # ── Print per-scenario ───────────────────────────────────────────────
    for r in results:
        s = r["name"]
        a = r["A"]
        b = r["B"]
        a_tag = "PASS" if a["passed"] else "FAIL"
        b_tag = "PASS" if b["passed"] else "FAIL"

        print(f"\n{'─' * 90}")
        print(f"SCENARIO: {s}")
        print(f"  {s}")
        print(f"  MLX 4bit [{a_tag}] ({a['time']}s, {a['length']} chars):")
        print(f"    Reason: {a['reason']}")
        for line in a["preview"].split("\n"):
            print(f"    | {line}")
        print()
        print(f"  7B [{b_tag}] ({b['time']}s, {b['length']} chars):")
        print(f"    Reason: {b['reason']}")
        for line in b["preview"].split("\n"):
            print(f"    | {line}")

    # ── Summary table ───────────────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print("SUMMARY")
    print("=" * 90)
    print(f"{'Scenario':<25} {'MLX 4bit':>10} {'7B':>10}  {'Winner'}")
    print("-" * 70)
    for r in results:
        a_win = r["A"]["passed"] and (not r["B"]["passed"] or r["A"]["length"] > r["B"]["length"])
        b_win = r["B"]["passed"] and (not r["A"]["passed"] or r["B"]["length"] > r["A"]["length"])
        tie = r["A"]["passed"] == r["B"]["passed"] and abs(r["A"]["length"] - r["B"]["length"]) < 50
        if tie:
            winner = "TIE"
        elif a_win:
            winner = "MLX 4bit"
        elif b_win:
            winner = "7B"
        else:
            winner = "TIE"
        print(f"  {r['name']:<23} {r['A']['time']:.1f}s/{r['A']['length']}c {r['B']['time']:.1f}s/{r['B']['length']}c  {winner}")

    a_passed = sum(1 for r in results if r["A"]["passed"])
    b_passed = sum(1 for r in results if r["B"]["passed"])
    print()
    print(f"  MLX 4bit:  {a_passed}/{len(results)} PASS")
    print(f"  7B:       {b_passed}/{len(results)} PASS")


if __name__ == "__main__":
    project_file = PROJECT_ROOT / "project.json"
    if project_file.exists():
        with open(project_file) as f:
            project_state = json.load(f)
    else:
        project_state = {
            "project_name": "Kitty",
            "milestones": [
                {"id": 1, "title": "Core Routing", "status": "doing", "tasks": ["Write tests"], "done_tasks": []},
            ],
            "notes": "Working on backend comparison.",
            "backlog": [],
        }

    run_report(project_state)