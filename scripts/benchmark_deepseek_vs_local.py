#!/usr/bin/env python3
"""
Comprehensive benchmark: DeepSeek V4 Flash (OpenRouter) vs Qwen3.5-4B (local MLX)
Tests kitty_builder on 9 scenarios across capability dimensions.

Usage:
    python3 scripts/benchmark_deepseek_vs_local.py

Requires:
    - mlx_lm (for local Qwen3.5-4B)
    - openai (for OpenRouter DeepSeek V4 Flash)
    - OPENROUTER_API_KEY in .env
"""

import json, os, sys, time, re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# ─── Load API keys from .env ─────────────────────────────────────────
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

DEEPSEEK_MODEL = "deepseek/deepseek-v4-flash"
LOCAL_MODEL = "mlx-community/Qwen3.5-4B-4bit"

# ─── Project State ──────────────────────────────────────────────────
def load_project():
    p = PROJECT_ROOT / "project.json"
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {
        "project_name": "Kitty AI Router",
        "milestones": [
            {"id": 1, "title": "Core Routing", "status": "doing",
             "tasks": ["Write tests"], "done_tasks": []}
        ],
        "notes": "Working on multi-model routing.",
        "backlog": [],
    }

def format_project(proj):
    lines = [
        f"Name: {proj.get('project_name', '')}",
        f"Notes: {proj.get('notes', '')}",
        "Milestones:",
    ]
    for m in proj.get("milestones", []):
        lines.append(f"  - [{m.get('id')}] {m.get('title')} ({m.get('status')})")
        lines.append(f"    Tasks: {len(m.get('tasks', []))} pending, {len(m.get('done_tasks', []))} done.")
    lines.append(f"Backlog: {len(proj.get('backlog', []))} items")
    return "\n".join(lines)

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

# ─── Scenarios ──────────────────────────────────────────────────────
SCENARIOS = [
    {
        "name": "1. Status Query (Conversation)",
        "dimension": "conversation",
        "desc": "Should reply conversationally about milestones — no tool",
        "user": "Hey Kitty, where are we at with the project right now?",
        "expect_tool": False,
        "avoid_tool": False,
        "text_contains": "milestone",
    },
    {
        "name": "2. Task Assignment (Tool Use)",
        "dimension": "tool_use",
        "desc": "Should emit modify_project_tasks JSON with action=add_task, milestone_id=1",
        "user": "Add a task to milestone 1 to improve the JSON parser",
        "expect_tool": True,
        "avoid_tool": False,
        "text_contains": "tool",
        "tool_action": "modify_project_tasks",
        "tool_action_args": {"action": "add_task"},
        "tool_milestone_id": 1,
    },
    {
        "name": "3. Run Command (Tool Execution)",
        "dimension": "tool_use",
        "desc": "Should emit run_command or launch_kitty tool call",
        "user": "Run the test suite for me",
        "expect_tool": True,
        "avoid_tool": False,
        "text_contains": "tool",
        "tool_action_any": ["run_command", "launch_kitty"],
    },
    {
        "name": "4. Inline Audit (Reasoning)",
        "dimension": "reasoning",
        "desc": "Should give direct advice, not emit a tool",
        "user": "What bug should I be most worried about in kitty_builder right now?",
        "expect_tool": False,
        "avoid_tool": True,
        "text_contains": None,
    },
    {
        "name": "5. Read File (Tool Selection)",
        "dimension": "tool_use",
        "desc": "Should emit read_file JSON tool call",
        "user": "Read the main.py file and tell me what it does",
        "expect_tool": True,
        "avoid_tool": False,
        "text_contains": "tool",
        "tool_action": "read_file",
    },
    {
        "name": "6. Refactoring Advice (Domain Knowledge)",
        "dimension": "reasoning",
        "desc": "Should give substantive direct advice mentioning retry",
        "user": "Is it worth adding a retry decorator to all the API calls? What are the tradeoffs?",
        "expect_tool": False,
        "avoid_tool": True,
        "text_contains": "retry",
    },
    {
        "name": "7. Complex Planning (Strategy)",
        "dimension": "planning",
        "desc": "Should propose a multi-step plan without hallucinating tools",
        "user": "What should I build next for this project? Give me a ranked list of 3 features with reasoning.",
        "expect_tool": False,
        "avoid_tool": True,
        "text_contains": None,
    },
    {
        "name": "8. Code Quality Help (Technical)",
        "dimension": "technical",
        "desc": "Should analyze code quality and suggest improvements",
        "user": "I'm getting 'maximum recursion depth exceeded' errors. How should I restructure the code to avoid this while keeping readability high?",
        "expect_tool": False,
        "avoid_tool": True,
        "text_contains": "recursion",
    },
    {
        "name": "9. Edge Case: Ambiguous Request",
        "dimension": "robustness",
        "desc": "Should ask clarifying question rather than guessing or hallucinating",
        "user": "Fix the thing",
        "expect_tool": False,
        "avoid_tool": True,
        "text_contains": None,
    },
]

# ─── Helpers ─────────────────────────────────────────────────────────
def build_messages(user_input, project_state):
    sys_msg = SYSTEM_PROMPT.format(root=PROJECT_ROOT, project=format_project(project_state))
    return [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": user_input},
    ]

def extract_json(text):
    block = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    raw = block.group(1) if block else text
    start = raw.find("{")
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(raw[start:])
        return obj
    except json.JSONDecodeError:
        return None

def score_scenario(name, text, scenario, elapsed):
    text_lower = text.lower()
    tool_json = extract_json(text)
    tool_found = tool_json is not None and "tool" in tool_json
    passed = True
    reasons = []

    if tool_found and not scenario["expect_tool"]:
        passed = False
        reasons.append("Emitted tool when shouldn't have")
    if not tool_found and scenario["expect_tool"]:
        passed = False
        reasons.append("Expected tool call but none found")
    elif scenario.get("avoid_tool") and tool_found:
        passed = False
        reasons.append("Emitted tool when should respond directly")

    if scenario.get("text_contains") and scenario["text_contains"] not in text_lower:
        passed = False
        reasons.append(f"Expected '{scenario['text_contains']}' in response")

    if scenario.get("tool_action") and tool_json:
        if tool_json.get("tool") != scenario["tool_action"]:
            passed = False
            reasons.append(f"Wrong tool: expected '{scenario['tool_action']}', got '{tool_json.get('tool')}'")
        if scenario.get("tool_milestone_id") is not None:
            args = tool_json.get("args", {})
            mid = args.get("milestone_id") or args.get("milestone_number")
            if mid != scenario["tool_milestone_id"]:
                passed = False
                reasons.append(f"Wrong milestone_id: expected {scenario['tool_milestone_id']}, got {mid}")
        if scenario.get("tool_action_args"):
            args = tool_json.get("args", {})
            for k, v in scenario["tool_action_args"].items():
                if args.get(k) != v:
                    passed = False
                    reasons.append(f"Wrong arg '{k}': expected '{v}', got '{args.get(k)}'")

    if scenario.get("tool_action_any") and tool_json:
        if tool_json.get("tool") not in scenario["tool_action_any"]:
            passed = False
            reasons.append(f"Wrong tool: expected one of {scenario['tool_action_any']}, got '{tool_json.get('tool')}'")

    return {
        "passed": passed,
        "reason": "; ".join(reasons) if reasons else "OK",
        "tool_emitted": tool_found,
        "tool_name": tool_json.get("tool") if tool_json else None,
        "length": len(text),
        "time": round(elapsed, 1),
        "text": text,
        "preview": text[:300].strip().replace("\n", "\\n"),
    }

# ─── MLX Local Runner ──────────────────────────────────────────────
class LocalRunner:
    def __init__(self):
        print(f"\n  [Loading local model: {LOCAL_MODEL}]...", end=" ", flush=True)
        t0 = time.time()
        import mlx.core as mx
        mx.metal.clear_cache()
        from mlx_lm import load, generate
        from mlx_lm.sample_utils import make_sampler
        self.model, self.tok = load(
            LOCAL_MODEL,
            tokenizer_config={"trust_remote_code": True},
        )
        self.generate = generate
        self.make_sampler = make_sampler
        print(f"done ({time.time()-t0:.1f}s)")

    def _build_prompt(self, messages, thinking=False):
        try:
            return self.tok.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
                enable_thinking=thinking,
            )
        except TypeError:
            return self.tok.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )

    def chat(self, messages, max_tokens=400, temp=0.7):
        prompt = self._build_prompt(messages)
        sampler = self.make_sampler(temp=temp)
        import gc, mlx.core as mx
        gc.collect()
        mx.metal.clear_cache()
        t0 = time.time()
        text = self.generate(
            self.model, self.tok,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=sampler,
            verbose=False,
        )
        elapsed = time.time() - t0
        return text.strip(), elapsed, {}

# ─── OpenRouter DeepSeek Runner ────────────────────────────────────
class DeepSeekRunner:
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
            timeout=60,
        )
        self.model = DEEPSEEK_MODEL

    def chat(self, messages, max_tokens=400, temp=0.7, retries=3):
        t0 = time.time()
        for attempt in range(retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temp,
                )
                elapsed = time.time() - t0
                text = resp.choices[0].message.content or ""
                usage = {
                    "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                    "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                    "total_tokens": resp.usage.total_tokens if resp.usage else 0,
                }
                return text.strip(), elapsed, usage
            except Exception as e:
                if attempt == retries - 1:
                    elapsed = time.time() - t0
                    return f"[ERROR] {e}", elapsed, {}
                time.sleep(1)

# ─── Report Builder ─────────────────────────────────────────────────
def build_report(results):
    lines = []
    lines.append("=" * 100)
    lines.append("KITTYBUILDER: DeepSeek V4 Flash vs Local Qwen3.5-4B")
    lines.append("=" * 100)

    # Per-scenario breakdown
    for r in results:
        name = r["name"]
        dim = r["dimension"]
        a = r["deepseek"]
        b = r["local"]
        a_tag = "PASS" if a["passed"] else "FAIL"
        b_tag = "PASS" if b["passed"] else "FAIL"

        lines.append(f"\n{'─' * 100}")
        lines.append(f"  [{dim}] {name}")
        lines.append(f"  {r['desc']}")

        deepseek_usage = ""
        if a.get("usage") and a["usage"].get("total_tokens"):
            u = a["usage"]
            deepseek_usage = f" [{u['prompt_tokens']}→{u['completion_tokens']} tok, ${u.get('prompt_tokens',0)*0.14e-6 + u.get('completion_tokens',0)*0.28e-6:.6f}]"

        lines.append(f"\n  ┌─ DEEPSEEK V4 FLASH [{a_tag}] ({a['time']}s{deepseek_usage})")
        lines.append(f"  │ {a['reason']}")
        lines.append(f"  │ Tool: {a['tool_name'] or 'none'} | Length: {a['length']} chars")
        for line in a["preview"].split("\\n"):
            lines.append(f"  │ {line}")

        lines.append(f"\n  ┌─ LOCAL QWEN3.5-4B [{b_tag}] ({b['time']}s)")
        lines.append(f"  │ {b['reason']}")
        lines.append(f"  │ Tool: {b['tool_name'] or 'none'} | Length: {b['length']} chars")
        for line in b["preview"].split("\\n"):
            lines.append(f"  │ {line}")

    # Summary table
    lines.append(f"\n{'=' * 100}")
    lines.append("SUMMARY")
    lines.append("=" * 100)
    lines.append(f"{'Scenario':<43} {'DeepSeek V4 Flash':>18} {'Local Qwen3.5-4B':>18}")
    lines.append("-" * 80)

    deepseek_pass = 0
    local_pass = 0
    deepseek_total_time = 0
    local_total_time = 0

    for r in results:
        a = r["deepseek"]
        b = r["local"]
        a_tag = "✓" if a["passed"] else "✗"
        b_tag = "✓" if b["passed"] else "✗"
        if a["passed"]: deepseek_pass += 1
        if b["passed"]: local_pass += 1
        deepseek_total_time += a["time"]
        local_total_time += b["time"]
        lines.append(f"  {r['name']:<40} {a_tag} {a['time']:>5.1f}s/{a['length']:>4}c {b_tag} {b['time']:>5.1f}s/{b['length']:>4}c")

    lines.append("-" * 80)
    lines.append(f"  {'TOTAL':<40} {deepseek_pass}/{len(results)} pass {deepseek_total_time:>5.1f}s total  {local_pass}/{len(results)} pass {local_total_time:>5.1f}s total")

    # Dimension breakdown
    lines.append(f"\n{'─' * 100}")
    lines.append("BREAKDOWN BY DIMENSION")
    lines.append("─" * 100)
    dims = {}
    for r in results:
        d = r["dimension"]
        if d not in dims:
            dims[d] = {"deepseek": {"pass": 0, "total": 0}, "local": {"pass": 0, "total": 0}}
        dims[d]["deepseek"]["total"] += 1
        dims[d]["local"]["total"] += 1
        if r["deepseek"]["passed"]:
            dims[d]["deepseek"]["pass"] += 1
        if r["local"]["passed"]:
            dims[d]["local"]["pass"] += 1

    for d, counts in sorted(dims.items()):
        ds = counts["deepseek"]
        lc = counts["local"]
        lines.append(f"  {d:<20} DeepSeek: {ds['pass']}/{ds['total']}  |  Local: {lc['pass']}/{lc['total']}")

    # Winner determination
    lines.append(f"\n{'─' * 100}")
    lines.append("WINNERS")
    lines.append("─" * 100)
    for r in results:
        a = r["deepseek"]
        b = r["local"]
        a_win = a["passed"] and (not b["passed"] or a["length"] > b["length"])
        b_win = b["passed"] and (not a["passed"] or b["length"] > a["length"])
        tie = a["passed"] == b["passed"] and abs(a["length"] - b["length"]) < 50
        if tie:
            winner = "TIE"
        elif a_win:
            winner = "DEEPSEEK"
        elif b_win:
            winner = "LOCAL"
        else:
            winner = "TIE"
        lines.append(f"  {r['name']:<40} {winner}")

    return "\n".join(lines)

# ─── Main ────────────────────────────────────────────────────────────
def main():
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    project = load_project()
    print(f"Project: {project.get('project_name', 'Unnamed')}")
    print(f"Milestones: {len(project.get('milestones', []))}")
    print(f"Backlog: {len(project.get('backlog', []))} items\n")

    # Initialize runners
    print("Initializing runners...")
    if not OPENROUTER_API_KEY:
        print("  ⚠ No OPENROUTER_API_KEY — DeepSeek V4 Flash will fail")
    deepseek = DeepSeekRunner()
    print(f"  DeepSeek: {DEEPSEEK_MODEL}")
    local = LocalRunner()

    # Run scenarios
    results = []
    for s in SCENARIOS:
        name = s["name"]
        user = s["user"]
        messages = build_messages(user, project)

        print(f"\n{'─' * 60}")
        print(f"  [{name}]")

        # DeepSeek
        print(f"  DeepSeek V4 Flash...", end=" ", flush=True)
        text_a, t_a, usage_a = deepseek.chat(messages)
        score_a = score_scenario(name, text_a, s, t_a)
        score_a["usage"] = usage_a
        tag_a = "✓" if score_a["passed"] else "✗"
        print(f"{tag_a} ({t_a:.1f}s)")
        if score_a["reason"] != "OK":
            print(f"    → {score_a['reason']}")

        # Local
        print(f"  Local Qwen3.5-4B...", end=" ", flush=True)
        text_b, t_b, usage_b = local.chat(messages)
        score_b = score_scenario(name, text_b, s, t_b)
        score_b["usage"] = usage_b
        tag_b = "✓" if score_b["passed"] else "✗"
        print(f"{tag_b} ({t_b:.1f}s)")
        if score_b["reason"] != "OK":
            print(f"    → {score_b['reason']}")

        results.append({
            "name": name,
            "dimension": s["dimension"],
            "desc": s["desc"],
            "deepseek": score_a,
            "local": score_b,
        })

    # Print full report
    report = build_report(results)
    print(report)

    # Save to file
    report_path = PROJECT_ROOT / "docs" / "benchmark_deepseek_vs_local.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\nReport saved to: {report_path}")

if __name__ == "__main__":
    main()
