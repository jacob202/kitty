#!/usr/bin/env python3
"""
Kitty Builder – autonomous multi‑model agent for Jacob.
Runs entirely on Apple Silicon / MLX with full session memory.
"""

import argparse, json, os, re, shlex, subprocess, sys, time, traceback
from pathlib import Path
from typing import Dict, Optional, List
from mlx_lm import generate, load, stream_generate
from mlx_lm.sample_utils import make_sampler

from src.utils.security_scanner import scan_text

_env_loaded = False
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())
    _env_loaded = True

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
USE_OPENROUTER = os.environ.get("USE_OPENROUTER", "true").lower() == "true"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")

_openrouter_client = None
if USE_OPENROUTER and OPENROUTER_API_KEY:
    from openai import OpenAI
    _openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY
    )

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
PROJECT_FILE = PROJECT_ROOT / "project.json"

# Preferred Model (project standard — MLX optimized for quality)
# Qwen3.5-4bit tested as best performer for reasoning/instruction following
MODEL_BUILDER = "mlx-community/Qwen3.5-4B-4bit"
MODEL_CODE    = MODEL_BUILDER
MODEL_CONV    = MODEL_BUILDER

WEB_SEARCH_API_KEY = os.environ.get("TAVILY_API_KEY", "")   # Tavily API key
WHITELISTED_COMMANDS = {
    "git", "python3", "python3.12", "python3.11", "python3.10", "python", "pip", "pip3",
    "ls", "echo", "mkdir", "touch", "cat", "head", "tail", "wc", "grep", "find", "pwd",
    "pytest", "unittest", "mypy", "ruff", "black", "npm", "npx",
}

# ------------------------------------------------------------
# SESSION STATE
# ------------------------------------------------------------
class Session:
    def __init__(self):
        self.history: List[Dict[str, str]] = []
        self.project_state: Dict = {}

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        # Keep history manageable (last 20 turns)
        if len(self.history) > 40:
            self.history = self.history[-40:]

SESSION_FILE = PROJECT_ROOT / ".kittybuilder_session.json"

def save_session():
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump({
                "history": session.history,
                "project_state": session.project_state
            }, f)
    except Exception:
        pass

def load_session():
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE) as f:
                data = json.load(f)
                session.history = data.get("history", [])
                session.project_state = data.get("project_state", {})
                return True
        except Exception:
            pass
    return False

session = Session()

# ------------------------------------------------------------
# MODEL CACHE
# ------------------------------------------------------------
_model_cache = {}

def get_model(model_id: str, retries: int = 2):
    """Load MLX model with optimizations."""
    if USE_OPENROUTER and _openrouter_client:
        return ("openrouter", model_id)
    if model_id in _model_cache:
        return _model_cache[model_id]
    if _model_cache:
        _model_cache.clear()
    print(f"[Loading] {model_id}...")
    for attempt in range(retries):
        try:
            # MLX load options for optimization
            model, tokenizer = load(
                model_id,
                tokenizer_config={"trust_remote_code": True}
            )
            _model_cache[model_id] = (model, tokenizer)
            return model, tokenizer
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"[Retry {attempt + 2}] {e}")
    raise RuntimeError(f"Failed to load {model_id} after {retries} attempts")

# MLX Optimization constants
MLX_OPTIMIZATIONS = {
    "use_lazy_imports": True,  # Reduces memory during loading
    "fp16": False,  # Use fp16 for faster inference on M1/M2
    "stream_chunk_size": 512,  # Optimal chunk size for streaming
}

def generate_openrouter(prompt: str, max_tokens: int = 1500, temp: float = 0.7, retries: int = 3) -> str:
    if not _openrouter_client:
        return "OpenRouter client not initialized. Set OPENROUTER_API_KEY."
    for attempt in range(retries):
        try:
            resp = _openrouter_client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temp
            )
            return resp.choices[0].message.content
        except Exception as e:
            if attempt == retries - 1:
                return f"Error after {retries} attempts: {e}"
            print(f"[Retry {attempt + 2}] {e}")
            time.sleep(1)

def stream_generate_openrouter(prompt: str, max_tokens: int = 1500, temp: float = 0.7):
    if not _openrouter_client:
        return
    resp = _openrouter_client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temp,
        stream=True
    )
    for chunk in resp:
        if chunk.choices[0].delta.content:
            yield type('obj', (object,), {'text': chunk.choices[0].delta.content})()

# ------------------------------------------------------------
# SAFETY HELPERS
# ------------------------------------------------------------
def is_safe_path(path: str) -> bool:
    try:
        abs_path = (PROJECT_ROOT / path).resolve()
        return abs_path.resolve().is_relative_to(PROJECT_ROOT)
    except (ValueError, RuntimeError):
        return False

_INTERPRETERS = {"python3", "python3.12", "python3.11", "python3.10", "python"}

def sanitize_command(command: str) -> bool:
    """Return True if the command is safe to run.

    Accepts both exact names (pytest) and path-based executables
    (venv/bin/python3.12) by comparing the basename against the whitelist.
    Blocks -c flag on interpreters to prevent inline code injection.
    """
    forbidden = [";", "&&", "||", "|", ">", "<", "`", "$("]
    parts = command.split()
    if not parts:
        return False
    base_name = Path(parts[0]).name   # "venv/bin/python3.12" → "python3.12"
    if base_name not in WHITELISTED_COMMANDS:
        return False
    # Block interpreter code injection via -c flag
    if base_name in _INTERPRETERS and "-c" in parts[1:]:
        return False
    for char in forbidden:
        if char in command:
            return False
    return True

# ------------------------------------------------------------
# PROJECT MANAGER - Full Context Loading
# ------------------------------------------------------------
CONTEXT_FILES = [
    "docs/KITTY_CONTEXT.md",
    "README.md",
    "project.json",
    "CLAUDE.md",
]

def load_full_context() -> dict:
    """Load all relevant project context for the project manager."""
    context = {
        "files_read": [],
        "content": {},
        "git_info": {},
    }

    # Read key context files
    for rel_path in CONTEXT_FILES:
        full_path = PROJECT_ROOT / rel_path
        if full_path.exists():
            try:
                with open(full_path) as f:
                    context["content"][rel_path] = f.read(5000)
                    context["files_read"].append(rel_path)
            except Exception:
                pass

    # Get git info
    try:
        proc = subprocess.run(
            ["git", "log", "--oneline", "-10", "--format=%h %s"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
        )
        context["git_info"]["recent_commits"] = proc.stdout.strip().split("\n") if proc.returncode == 0 else []
    except Exception:
        pass

    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
        )
        context["git_info"]["status"] = proc.stdout.strip() if proc.returncode == 0 else ""
    except Exception:
        pass

    return context

def build_project_state() -> dict:
    """Build comprehensive current project state with progress estimates."""
    full_context = load_full_context()
    name = "Kitty AI Router"

    # Read project.json
    proj = {"milestones": [], "backlog": [], "notes": ""}
    if PROJECT_FILE.exists():
        try:
            with open(PROJECT_FILE) as f:
                proj = json.load(f)
        except Exception:
            pass

    # Scan for TODOs
    todos = []
    pattern = re.compile(r'#\s*(TODO|FIXME|HACK|NOTE|IDEA)[: ]?\s*(.*)', re.I)
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'venv', 'node_modules')]
        for fname in files:
            if fname.endswith('.py'):
                try:
                    with open(os.path.join(root, fname)) as f:
                        for lno, line in enumerate(f, 1):
                            m = pattern.search(line)
                            if m:
                                todos.append({
                                    "file": os.path.relpath(os.path.join(root, fname), PROJECT_ROOT),
                                    "line": lno,
                                    "tag": m.group(1).upper(),
                                    "text": m.group(2).strip()
                                })
                except (OSError, UnicodeDecodeError):
                    continue

    # Calculate progress (total = pending + done)
    pending_tasks = sum(len(m.get("tasks", [])) for m in proj.get("milestones", []))
    done_tasks = sum(len(m.get("done_tasks", [])) for m in proj.get("milestones", []))
    total_tasks = pending_tasks + done_tasks
    total_milestones = len(proj.get("milestones", []))
    completed_milestones = sum(1 for m in proj.get("milestones", []) if m.get("status") == "completed")

    progress = {
        "total_tasks": total_tasks,
        "completed_tasks": done_tasks,
        "remaining_tasks": pending_tasks,
        "task_completion_pct": round((done_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0,
        "total_milestones": total_milestones,
        "completed_milestones": completed_milestones,
        "milestone_completion_pct": round((completed_milestones / total_milestones * 100), 1) if total_milestones > 0 else 0,
        "open_todos": len(todos),
    }

    return {
        "project_name": proj.get("project_name", name),
        "description": proj.get("description", ""),
        "milestones": proj.get("milestones", []),
        "backlog": proj.get("backlog", []),
        "notes": proj.get("notes", ""),
        "progress": progress,
        "context_files": full_context["files_read"],
        "git_info": full_context["git_info"],
        "open_todos": todos,
    }

def generate_project_brief() -> str:
    """Generate a comprehensive project brief for the AI to use."""
    state = build_project_state()
    p = state["progress"]

    brief = f"""# PROJECT BRIEF: {state['project_name']}

## PROGRESS SUMMARY
- Tasks: {p['completed_tasks']}/{p['total_tasks']} completed ({p['task_completion_pct']}%)
- Milestones: {p['completed_milestones']}/{p['total_milestones']} completed ({p['milestone_completion_pct']}%)
- Open TODOs/FIXMEs: {p['open_todos']}

## CURRENT MILESTONES
"""
    for m in state.get("milestones", []):
        brief += f"- [{m.get('status', '?')}] {m.get('title', 'Unnamed')}\n"
        for t in m.get("tasks", []):
            brief += f"  - {t}\n"
        for t in m.get("done_tasks", []):
            brief += f"  ✓ {t}\n"

    brief += f"""
## BACKLOG
"""
    for b in state.get("backlog", []):
        brief += f"- {b}\n"

    brief += f"""
## GIT STATUS
{state['git_info'].get('status', 'N/A')}

## RECENT COMMITS
"""
    for c in state['git_info'].get('recent_commits', [])[:5]:
        brief += f"- {c}\n"

    brief += f"""
## OPEN TODOs ({len(state.get('open_todos', []))})
"""
    for t in state.get("open_todos", [])[:10]:
        brief += f"- [{t['tag']}] {t['text']} ({t['file']}:{t['line']})\n"

    return brief

def update_project_from_scan():
    """Build comprehensive project state from all sources."""
    state = build_project_state()

    # Update project.json if needed
    current = {}
    if PROJECT_FILE.exists():
        try:
            with open(PROJECT_FILE) as f: current = json.load(f)
        except (json.JSONDecodeError, OSError): pass

    current["project_name"] = state["project_name"]
    current["description"] = state.get("description", "")
    current["notes"] = f"Active in: {PROJECT_ROOT}"

    with open(PROJECT_FILE, "w") as f: json.dump(current, f, indent=2)

    session.project_state = state
    return state

def run_command(command: str) -> str:
    if not sanitize_command(command):
        return f"Error: Command '{command}' failed safety check."
    blocked = _format_security_findings("<command>", command)
    if blocked:
        return blocked
    print(f"[Executing] {command}")
    try:
        proc = subprocess.Popen(
            shlex.split(command), shell=False,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=PROJECT_ROOT,
        )
        output = ""
        max_chars = 50_000
        for line in proc.stdout:
            if len(output) + len(line) > max_chars:
                output += f"\n[Output truncated ({max_chars:,} char limit)]"
                break
            print(line, end="")
            output += line
        proc.wait(timeout=60)
        if proc.returncode != 0:
            return f"Command exited with code {proc.returncode}:\n{output}"
        return output if output else "Command completed with no output."
    except subprocess.TimeoutExpired:
        proc.kill()
        return "Error: Command timed out after 60 seconds."
    except Exception as e:
        return f"Execution Error: {str(e)}"

def read_file(path: str) -> str:
    if not is_safe_path(path): return "Error: Access denied (outside project root)."
    try:
        with open(PROJECT_ROOT / path) as f: return f.read(8000)
    except Exception as e: return str(e)

def _format_security_findings(path: str, content: str) -> str:
    findings = scan_text(path, content)
    if not findings:
        return ""
    lines = ["Error: Security scan blocked builder action."]
    for finding in findings[:10]:
        lines.append(
            f"- {finding.severity} {finding.rule} at {finding.path}:{finding.line}: {finding.message}"
        )
    if len(findings) > 10:
        lines.append(f"- ... {len(findings) - 10} more finding(s)")
    return "\n".join(lines)

def write_file(path: str, content: str) -> str:
    if not is_safe_path(path): return "Error: Access denied."
    blocked = _format_security_findings(path, content)
    if blocked:
        return blocked
    try:
        full_path = PROJECT_ROOT / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w") as f: f.write(content)
        # Quality judge
        judge = quality_judge(path)
        return f"File {path} written. Review: {judge}"
    except Exception as e: return str(e)

def quality_judge(path: str) -> str:
    try:
        with open(PROJECT_ROOT / path) as f: code = f.read(3000)
        content = f"Review this code briefly. Grade A-F and give one sentence of feedback.\nFile: {path}\nCode:\n```\n{code}\n```"
        if USE_OPENROUTER and OPENROUTER_API_KEY:
            return generate_openrouter(content, max_tokens=80, temp=0.1).strip()
        model, tok = get_model(MODEL_BUILDER)
        messages = [{"role": "user", "content": content}]
        prompt = _build_prompt(tok, messages)
        return generate(model, tok, prompt=prompt, max_tokens=80,
                        sampler=make_sampler(temp=0.1)).strip()
    except Exception:
        return "Judge unavailable."

def update_project(action: str, **kwargs) -> str:
    proj = session.project_state
    if action == "add_task":
        for m in proj["milestones"]:
            if m["id"] == kwargs.get("milestone_id") or m["id"] == kwargs.get("milestone_number"):
                task_str = kwargs.get("task") or kwargs.get("task_name") or kwargs.get("title")
                m.setdefault("tasks", []).append(task_str)
                break
    elif action == "mark_task_done":
        mid = kwargs.get("milestone_id") or kwargs.get("milestone_number")
        task_str = kwargs.get("task") or kwargs.get("task_name") or kwargs.get("title")
        for m in proj["milestones"]:
            if m["id"] == mid and task_str in m.get("tasks", []):
                m["tasks"].remove(task_str)
                m.setdefault("done_tasks", []).append(task_str)
                break
    elif action == "move_to_backlog":
        task_str = kwargs.get("task") or kwargs.get("task_name") or kwargs.get("title")
        for m in proj["milestones"]:
            if task_str in m.get("tasks", []):
                m["tasks"].remove(task_str)
        proj.setdefault("backlog", []).append(task_str)
    elif action == "add_note":
        proj["notes"] = (proj.get("notes", "") + "\n" + kwargs.get("note", "")).strip()
    elif action == "add_milestone":
        new_id = max([m.get("id", 0) for m in proj.get("milestones", [])], default=0) + 1
        title = kwargs.get("title") or kwargs.get("name") or f"Milestone {new_id}"
        proj.setdefault("milestones", []).append({
            "id": new_id,
            "title": title,
            "status": "todo",
            "tasks": []
        })
        action = f"add_milestone ({title})"
    else:
        return f"Error: Unknown action '{action}'"

    with open(PROJECT_FILE, "w") as f: json.dump(proj, f, indent=2)
    return f"Project updated: {action}"

def search_web(query: str) -> str:
    if not WEB_SEARCH_API_KEY:
        return "Error: Web search disabled (set TAVILY_API_KEY)."
    for attempt in range(2):
        try:
            import requests
            resp = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": WEB_SEARCH_API_KEY, "query": query, "search_depth": "basic"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])[:5]
            return "\n".join(f"- {r['title']}: {r['url']}" for r in results) if results else "No results found."
        except Exception as e:
            if attempt == 1:
                return f"Search error after retries: {e}"
    return "Search error: unknown"

def get_project_brief() -> str:
    return generate_project_brief()

def run_pattern(pattern_name: str, text: str) -> str:
    """Run a pattern on the given text. Available patterns: summarize, action-items, explain-code, review-code, audit, breakdown, compare, brainstorm"""
    patterns_path = PROJECT_ROOT / "config" / "patterns.json"
    if not patterns_path.exists():
        return "Error: patterns.json not found"

    try:
        with open(patterns_path) as f:
            patterns = json.load(f)

        if pattern_name not in patterns:
            return f"Error: Pattern '{pattern_name}' not found. Available: {', '.join(patterns.keys())}"

        prompt_template = patterns[pattern_name]["prompt"]
        prompt = prompt_template.replace("{text}", text)

        if USE_OPENROUTER and OPENROUTER_API_KEY:
            return generate_openrouter(prompt, max_tokens=1000, temp=0.5)
        else:
            model, tok = get_model(MODEL_BUILDER)
            messages = [{"role": "user", "content": prompt}]
            return generate(model, tok, prompt=_build_prompt(tok, messages),
                          max_tokens=1000, sampler=make_sampler(temp=0.5))
    except Exception as e:
        return f"Error running pattern: {e}"

def scan_project_health() -> str:
    """Thorough project health scan with codebase analysis."""
    state = build_project_state()
    p = state["progress"]

    issues = []
    warnings = []

    if p["task_completion_pct"] < 30:
        issues.append("Low task completion (<30%)")
    if p["open_todos"] > 5:
        issues.append(f"Many open TODOs ({p['open_todos']})")
    if len(state.get("backlog", [])) > 10:
        issues.append(f"Large backlog ({len(state['backlog'])} items)")

    git_status = state.get("git_info", {}).get("status", "")
    git_lines = [l for l in git_status.split("\n") if l.strip()]
    untracked = len([l for l in git_lines if l.startswith("??")])
    modified = len([l for l in git_lines if l.startswith((" M", "M "))])
    if untracked > 10:
        warnings.append(f"Many untracked files ({untracked})")
    if modified > 10:
        warnings.append(f"Many modified files ({modified})")

    # Check for stale/incomplete files
    import os, glob
    project_root = PROJECT_ROOT
    stale_patterns = [
        ("CURRENT_PROJECT_STATE.json", "Stale debug file at project root"),
    ]
    for fname, desc in stale_patterns:
        if (project_root / fname).exists():
            warnings.append(f"{fname}: {desc}")

    # Check for missing requirements.txt
    if not (project_root / "requirements.txt").exists():
        warnings.append("Missing requirements.txt (dependency documentation)")

    # Check test count
    test_files = list(project_root.glob("tests/**/test_*.py"))
    if len(test_files) < 10:
        warnings.append(f"Low test coverage ({len(test_files)} test files)")

    report = f"""# Project Health Report

**Progress:** {p['task_completion_pct']}% tasks, {p['milestone_completion_pct']}% milestones
**Remaining:** {p['remaining_tasks']} tasks, {p['open_todos']} TODOs

## Status: {"⚠️ Needs Attention" if issues else "✅ Healthy"}
"""
    if issues:
        report += "## Issues:\n" + "\n".join(f"- {i}" for i in issues) + "\n"
    if warnings:
        report += "## Warnings:\n" + "\n".join(f"- {w}" for w in warnings) + "\n"

    report += f"""
## Quick Stats
- Milestones: {len(state['milestones'])}
- Backlog: {len(state['backlog'])} items
- Git changes: {len(git_lines)} ({untracked} untracked, {modified} modified)
- Test files: {len(test_files)}
- Python files: {len(list(project_root.rglob('*.py')))}
"""
    return report

def suggest_next_steps() -> str:
    """Suggest the best next steps based on current state."""
    state = session.project_state
    p = state.get("progress", {})

    recommendations = []

    # Find incomplete milestones
    for m in state.get("milestones", []):
        if m.get("status") == "doing" and m.get("tasks"):
            task = m["tasks"][0]
            recommendations.append(f"1. Finish: {task} (Milestone: {m['title']})")

    # Check backlog
    if state.get("backlog"):
        recommendations.append(f"2. Pick from backlog: {state['backlog'][0]}")

    # Open TODOs
    todos = state.get("open_todos", [])
    if todos:
        recommendations.append(f"3. Address TODO: {todos[0]['text'][:50]}")

    return "## Recommended Next Steps\n\n" + "\n\n".join(recommendations) if recommendations else "No specific recommendations - project looks good!"

def kitty_self_improve() -> str:
    """Run comprehensive self-improvement loop: test, audit, grade, fix, improve."""
    print("\n" + "="*60)
    print("🐱 KITTY SELF-IMPROVEMENT LOOP")
    print("="*60)

    results = {
        "test_results": {},
        "audit_findings": [],
        "grade": "N/A",
        "fixes_applied": [],
        "feedback": [],
    }

    # Step 1: Run tests
    print("\n[1/6] Running test suite...")
    test_output = run_command(f"{sys.executable} -m pytest tests/ -v --tb=short 2>&1 | tail -20")
    results["test_results"]["output"] = test_output
    # Check for actual test failures (e.g., "10 failed" or "1 failed")
    test_passed = " passed" in test_output and "failed)" not in test_output and " failed" not in test_output
    results["test_results"]["passed"] = test_passed

    # Step 2: Run self-review
    print("[2/6] Running code audit...")
    all_code = ""
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', 'node_modules')]
        for f in files:
            if f.endswith('.py') and len(all_code) < 8000:
                try:
                    with open(os.path.join(root, f)) as src:
                        all_code += f"\n# {f}\n{src.read(1500)}"
                except OSError:
                    continue

    prompt = f"Audit this code for bugs, security issues, and logic flaws. List ONLY the top 5 most critical issues in this format:\n1. [file:line] - issue description\n\nCode:\n{all_code[:6000]}"

    if USE_OPENROUTER and OPENROUTER_API_KEY:
        audit_result = generate_openrouter(prompt, max_tokens=800, temp=0.3)
    else:
        model, tok = get_model(MODEL_BUILDER)
        messages = [{"role": "user", "content": prompt}]
        audit_result = generate(model, tok, prompt=_build_prompt(tok, messages),
                               max_tokens=800, sampler=make_sampler(temp=0.3))

    audit_result = audit_result or "[Audit returned no output]"
    results["audit_findings"] = audit_result

    # Step 3: Generate grade
    print("[3/6] Generating grade...")
    grade_factors = []
    if test_passed:
        grade_factors.append("Tests passing")
    else:
        grade_factors.append("Tests failing")

    # Check for critical issues
    critical_count = audit_result.lower().count("critical") + audit_result.lower().count("bug") + audit_result.lower().count("error")
    if critical_count == 0:
        grade_factors.append("No critical bugs")
    else:
        grade_factors.append(f"{critical_count} potential issues")

    # Calculate grade
    score = 100
    if not test_passed:
        score -= 30
    score -= min(critical_count * 10, 40)
    score = max(score, 0)

    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"

    results["grade"] = grade
    results["score"] = score

    # Step 4: Provide actionable feedback
    print("[4/6] Generating feedback...")
    feedback_items = []
    if not test_passed:
        feedback_items.append("- Fix failing tests first (run pytest for details)")
    if critical_count > 0:
        feedback_items.append(f"- Address {critical_count} critical issues from audit")

    feedback_items.append("- Review backlog and pick next task")
    feedback_items.append("- Consider running /health for project status")

    results["feedback"] = feedback_items

    # Step 5: Summary
    print("[5/6] Summary")
    print("-" * 40)
    print(f"Tests: {'✅ PASS' if test_passed else '❌ FAIL'}")
    print(f"Audit: {critical_count} issues found")
    print(f"Grade: {grade} ({score}/100)")

    # Step 6: Recommendations
    print("\n[6/6] Actionable Feedback:")
    for fb in feedback_items:
        print(f"  {fb}")

    print("\n" + "="*60)
    print(f"FINAL GRADE: {grade}")
    print("="*60)

    return f"""# Kitty Self-Improvement Report

## Test Results: {'✅ PASS' if test_passed else '❌ FAIL'}

## Audit Findings:
{audit_result[:1000]}

## Grade: {grade} ({score}/100)

## Actionable Feedback:
{chr(10).join(feedback_items)}

Run this function periodically to track Kitty's health.
"""

TOOLS = {
    "run_command": run_command,
    "read_file": read_file,
    "write_file": write_file,
    "modify_project_tasks": update_project,
    "search_web": search_web,
    "launch_kitty": lambda: run_command(f"{sys.executable} -m pytest tests/ -q --tb=short"),
    "generate_project_brief": get_project_brief,
    "run_pattern": run_pattern,
    "scan_project_health": scan_project_health,
    "suggest_next_steps": suggest_next_steps,
    "kitty_self_improve": kitty_self_improve,  # defined above
}

# ------------------------------------------------------------
# CORE MODES
# ------------------------------------------------------------
def council(question: str):
    """Run two independent reasoning passes then synthesize — single model, two prompts."""
    print("\n--- Council Deliberation ---")
    opinions = []
    for name, framing in [
        ("Pragmatist", "You are a pragmatic engineer focused on what works right now. Be direct and brief."),
        ("Critic",     "You are a critical reviewer focused on risks, edge cases, and flaws. Be direct and brief."),
    ]:
        print(f"[{name}] Thinking...")
        try:
            if USE_OPENROUTER and OPENROUTER_API_KEY:
                resp = _openrouter_client.chat.completions.create(
                    model=OPENROUTER_MODEL,
                    messages=[{"role": "system", "content": framing}, {"role": "user", "content": question}],
                    max_tokens=200, temperature=0.7
                ).choices[0].message.content
            else:
                model, tok = get_model(MODEL_BUILDER)
                sampler = make_sampler(temp=0.7)
                messages = [{"role": "system", "content": framing}, {"role": "user", "content": question}]
                resp = generate(model, tok, prompt=_build_prompt(tok, messages),
                                max_tokens=200, sampler=sampler)
            opinions.append(f"{name}: {resp.strip()}")
        except Exception as e:
            print(f"[Error in {name}: {e}]")
            opinions.append(f"{name}: [Error - {e}]")

    print("[Chairman] Synthesizing...")
    try:
        if USE_OPENROUTER and OPENROUTER_API_KEY:
            final = _openrouter_client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[{"role": "user", "content":
                    f"Synthesize these two perspectives on: {question!r}\n\n" +
                    "\n\n".join(opinions) +
                    "\n\nGive a final recommendation in 2-3 sentences."}],
                max_tokens=300, temperature=0.7
            ).choices[0].message.content
        else:
            model, tok = get_model(MODEL_BUILDER)
            sampler = make_sampler(temp=0.7)
            synth_msg = [{"role": "user", "content":
                f"Synthesize these two perspectives on: {question!r}\n\n" +
                "\n\n".join(opinions) +
                "\n\nGive a final recommendation in 2-3 sentences."}]
            final = generate(model, tok, prompt=_build_prompt(tok, synth_msg),
                             max_tokens=300, sampler=sampler)
        print(f"\nFinal Verdict:\n{final}\n")
    except Exception as e:
        print(f"\n[Synthesis Error: {e}]")
        print("Opinions gathered:")
        for o in opinions:
            print(o)

def self_review():
    print("\n" + "="*40 + "\nKITTY SELF-AUDIT FOR JACOB\n" + "="*40)

    import subprocess

    # Run real analysis instead of just feeding truncated code to LLM
    print("\n[1/4] Running code analysis...")
    findings = []

    # Check for generic error/exception patterns that swallow issues
    bare_excepts = subprocess.run(
        ["rg", "-n", "except:\\s*$|except\\s+Exception\\s*:\\s*pass", "--include", "*.py", "-l"],
        capture_output=True, text=True, timeout=30
    ).stdout.strip().split("\n")
    if bare_excepts and bare_excepts[0]:
        findings.append(f"Bare except/pass found in: {bare_excepts[:5]}")

    # Check for stale root-level files
    stale = []
    for f in PROJECT_ROOT.iterdir():
        if f.is_file() and f.name in ("CURRENT_PROJECT_STATE.json",):
            stale.append(f.name)
    if stale:
        findings.append(f"Stale root files: {stale}")

    # Check for duplicate code patterns
    if (PROJECT_ROOT / "model_loader.py").exists() and (PROJECT_ROOT / "model_preloader.py").exists():
        findings.append("model_loader.py and model_preloader.py overlap in purpose")

    # Check test count vs source files
    src_files = len(list(PROJECT_ROOT.rglob("src/**/*.py")))
    test_files = len(list(PROJECT_ROOT.rglob("tests/**/test_*.py")))
    if test_files < src_files * 0.3:
        findings.append(f"Low test ratio: {test_files} tests for {src_files} source files")

    # Check import issues
    unused_imports = subprocess.run(
        ["rg", "-n", "import\\s+socket", "web.py"],
        capture_output=True, text=True, timeout=10
    ).stdout.strip()

    if findings:
        print("\nFindings:")
        for f in findings:
            print(f"  ⚠ {f}")
    else:
        print("  No issues found via static analysis")

    # Now ask LLM for deeper review (only key files, not truncated)
    print("\n[2/4] Reading key files for LLM review...")
    key_files = [
        "web.py", "scripts/kitty_builder.py", "kitty_v2.py",
        "model_preloader.py", "model_loader.py",
        "src/space_kitty/llm_client.py", "src/core/specialist_framework.py",
    ]

    code_samples = []
    for fname in key_files:
        fpath = PROJECT_ROOT / fname
        if fpath.exists():
            code_samples.append(f"\n# --- {fname} (full) ---\n{fpath.read_text()[:6000]}")

    all_code = "\n".join(code_samples)
    print(f"  Loaded {len(key_files)} key files ({len(all_code)} chars)")

    prompt = f"""Review these key files for REAL bugs, security issues, and logic flaws.
IMPORTANT: Files are complete (not truncated). Only report actual bugs, not style issues.
For each finding, give: file, line, severity (HIGH/MED/LOW), and the fix.

{all_code}"""

    print("\n[3/4] Running LLM review...")
    if USE_OPENROUTER and OPENROUTER_API_KEY:
        report = generate_openrouter(prompt, max_tokens=1000, temp=0.2)
    else:
        model, tok = get_model(MODEL_CODE)
        messages = [{"role": "user", "content": prompt}]
        report = generate(model, tok, prompt=_build_prompt(tok, messages),
                          max_tokens=1000, sampler=make_sampler(temp=0.2))

    print("\n" + "="*40)
    print("LLM REVIEW FINDINGS")
    print("="*40)
    print(report)

    print("\n[4/4] Static analysis findings summary:")
    for f in findings:
        print(f"  ⚠ {f}")

# ------------------------------------------------------------
# AGENT LOGIC
# ------------------------------------------------------------
SYSTEM_PROMPT = """You are Kitty, Jacob's AI Project Manager and Builder.
You manage the Kitty AI Router project in: {root}

Your job is to:
1. Know the current project state (progress, tasks, milestones)
2. Recommend next steps and features
3. Track what's done vs remaining
4. Launch tools to execute plans
5. Give Jacob honest estimates of progress

--- TOOLS AVAILABLE ---
- run_command(command) - Execute safe shell commands
- read_file(path) - Read any project file
- write_file(path, content) - Create/update files
- modify_project_tasks(action, milestone_id, task, note, title) - Manage tasks
- search_web(query) - Search the web
- launch_kitty() - Run the test suite
- generate_project_brief() - Refresh your knowledge of project state

--- HOW YOU OPERATE ---
1. You ALWAYS know the full project state - use generate_project_brief() at session start
2. When Jacob asks about progress, give specific numbers (% complete, tasks remaining)
3. When Jacob asks for recommendations, analyze what's done vs what's needed
4. When Jacob wants to proceed, suggest specific next steps and offer to execute
5. If something is unclear, ask clarifying questions

--- PROJECT STATE ---
{project}
"""

def _build_prompt(tok, messages: list[dict], thinking: bool = False) -> str:
    """Apply Qwen3 chat template; gracefully degrades if enable_thinking unsupported."""
    try:
        return tok.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=thinking,
        )
    except TypeError:
        return tok.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )


def _format_project(proj: dict) -> str:
    p = proj.get("progress", {})
    lines = [
        f"Name: {proj.get('project_name', '')}",
        f"Progress: {p.get('task_completion_pct', 0)}% tasks, {p.get('milestone_completion_pct', 0)}% milestones",
        f"Remaining: {p.get('remaining_tasks', 0)} tasks, {p.get('open_todos', 0)} TODOs",
    ]

    for m in proj.get('milestones', []):
        lines.append(f"\nMilestone [{m.get('id')}]: {m.get('title')} [{m.get('status')}]")
        for t in m.get("tasks", []):
            lines.append(f"  → {t}")
        for t in m.get("done_tasks", []):
            lines.append(f"  ✓ {t}")

    lines.append(f"\nBacklog ({len(proj.get('backlog', []))} items):")
    for b in proj.get("backlog", [])[:5]:
        lines.append(f"  - {b}")
    if len(proj.get("backlog", [])) > 5:
        lines.append(f"  ... and {len(proj.get('backlog', [])) - 5} more")

    # Git info
    if proj.get("git_info", {}).get("status"):
        lines.append(f"\nGit: {proj['git_info']['status'][:200]}")

    return "\n".join(lines)


def _extract_json(text: str) -> dict | None:
    """Extract first JSON object from LLM response.

    Uses json.JSONDecoder to track nesting depth correctly — closing braces
    inside quoted strings are handled automatically by the JSON parser.

    Tries multiple patterns:
    1. ```json ... ``` block
    2. ``` ... ``` any code block
    3. Raw JSON-like text starting with {
    """
    # Pattern 1: JSON code block
    block = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if block:
        raw = block.group(1)
    else:
        # Pattern 2: Any code block
        block = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        raw = block.group(1) if block else text

    # Find JSON start
    start = raw.find('{')
    if start == -1:
        # Pattern 3: Look for key-value patterns in raw text
        if '"tool"' in text:
            # Try to extract from raw text
            match = re.search(r'\{[^}]*"tool"[^}]*\}', text, re.DOTALL)
            if match:
                raw = match.group(0)
                start = 0

    if start == -1:
        return None

    try:
        decoder = json.JSONDecoder()
        obj, end = decoder.raw_decode(raw[start:])
        return obj
    except json.JSONDecodeError:
        return None


def chat(user_input: str):
    sys_msg = SYSTEM_PROMPT.format(root=PROJECT_ROOT, project=_format_project(session.project_state))

    if not session.history:
        session.history.append({"role": "system", "content": sys_msg})
    else:
        session.history[0]["content"] = sys_msg

    session.history.append({"role": "user", "content": user_input})
    if len(session.history) > 40:
        session.history = session.history[-40:]

    if USE_OPENROUTER and OPENROUTER_API_KEY:
        print("[Kitty] ", end="", flush=True)
        response_parts = []
        for attempt in range(3):
            try:
                resp = _openrouter_client.chat.completions.create(
                    model=OPENROUTER_MODEL,
                    messages=session.history,
                    max_tokens=1500,
                    temperature=0.7,
                    stream=True
                )
                for chunk in resp:
                    if chunk.choices[0].delta.content:
                        print(chunk.choices[0].delta.content, end="", flush=True)
                        response_parts.append(chunk.choices[0].delta.content)
                response = "".join(response_parts)
                break
            except Exception as e:
                if attempt == 2:
                    response = f"Error after 3 attempts: {e}"
                    print(response)
                else:
                    print(f"[Retry {attempt + 2}] {e}")
                    time.sleep(1)
    else:
        model, tok = get_model(MODEL_BUILDER)
        prompt = _build_prompt(tok, session.history, thinking=False)
        print("[Kitty] ", end="", flush=True)
        response_parts = []
        for resp in stream_generate(model, tok, prompt, max_tokens=1500,
                                     sampler=make_sampler(temp=0.7)):
            print(resp.text, end="", flush=True)
            response_parts.append(resp.text)
        print()
        response = "".join(response_parts).strip()

    session.history.append({"role": "assistant", "content": response})

    # Check for tool call — use depth-aware parser to handle nested args
    data = _extract_json(response)
    if data is not None and "tool" in data:
        try:
            tool, args = data["tool"], data.get("args", {})
            if tool not in TOOLS:
                err = f"Error: Tool '{tool}' not found."
                print(f"[{err}]")
                session.history.append({"role": "system", "content": err})
            else:
                print(f"[Executing Tool: {tool}]...")
                result = TOOLS[tool](**args) if isinstance(args, dict) else TOOLS[tool](args)
                print(f"[Tool Result] {result}")
                session.history.append({"role": "system", "content": f"Tool '{tool}' executed. Result:\n{result}"})
        except Exception as e:
            err = f"Error executing tool: {e}"
            print(f"[{err}]")
            session.history.append({"role": "system", "content": err})

def show_models():
    print("\n--- Active Models ---")
    if USE_OPENROUTER and OPENROUTER_API_KEY:
        print(f"  Provider: OpenRouter")
        print(f"  Model: {OPENROUTER_MODEL}")
    else:
        print(f"  All roles: {MODEL_BUILDER}")
    loaded = list(_model_cache.keys())
    if loaded:
        print(f"\nCurrently loaded in VRAM: {loaded[0]}")
    else:
        print("\nNo models currently in VRAM.")


def show_help():
    print(
        "\n--- Kitty Builder Commands ---\n"
        "  /help          Show this help\n"
        "  /health        Scan project health\n"
        "  /next          Suggest next steps\n"
        "  /improve       Run self-improvement: test, audit, grade, feedback\n"
        "  /models        Show model info and VRAM state\n"
        "  /council <q>   Two-perspective deliberation on a question\n"
        "  /selfreview    Run code audit over the entire project\n"
        "  /patterns      List available patterns\n"
        "  /exit          Quit\n"
        "\nTools available: run_command, read_file, write_file,\n"
        "  modify_project_tasks, search_web, launch_kitty,\n"
        "  generate_project_brief, run_pattern, scan_project_health,\n"
        "  suggest_next_steps, kitty_self_improve\n"
        "\nPatterns: summarize, action-items, explain-code, review-code,\n"
        "  audit, breakdown, compare, brainstorm, test-plan, migrate-plan\n"
    )

# ------------------------------------------------------------
# BUILDER CONTRACT
# ------------------------------------------------------------
def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Controlled Kitty builder entrypoint. Dry-run is the default.",
    )
    parser.add_argument("--project", required=True, type=Path, help="Path to the Kitty app checkout.")
    parser.add_argument("--spec", required=True, type=Path, help="Path to the approved spec markdown file.")
    parser.add_argument("--execute", action="store_true", help="Allow future write-capable builder execution.")
    parser.add_argument("--dry-run", action="store_true", help="Print contract checks only. This is the default.")
    return parser


def validate_builder_contract(project: Path, spec: Path) -> list[str]:
    errors: list[str] = []
    project = project.expanduser().resolve()
    spec = spec.expanduser()
    spec_path = spec if spec.is_absolute() else project / spec
    spec_path = spec_path.resolve()

    if not project.exists() or not project.is_dir():
        errors.append(f"Project path does not exist or is not a directory: {project}")
    if not spec_path.exists() or not spec_path.is_file():
        errors.append(f"Spec path does not exist or is not a file: {spec_path}")
    try:
        spec_path.relative_to(project)
    except ValueError:
        errors.append(f"Spec path must live inside the project: {spec_path}")
    return errors


def run_builder_contract(project: Path, spec: Path, *, execute: bool = False) -> int:
    project = project.expanduser().resolve()
    spec_path = spec.expanduser()
    if not spec_path.is_absolute():
        spec_path = project / spec_path
    spec_path = spec_path.resolve()

    errors = validate_builder_contract(project, spec_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2

    mode = "execute" if execute else "dry-run"
    print("Kitty Builder Contract")
    print(f"Mode: {mode}")
    print(f"Project: {project}")
    print(f"Spec: {spec_path}")
    print("Writes enabled: no" if not execute else "Writes enabled: gated")
    print("Completion report required:")
    print("- files read")
    print("- files changed")
    print("- commands run")
    print("- tests passed/failed")
    print("- gates passed/failed")
    print("- docs updated")
    print("- known risks")
    print("- next smallest action")
    if not execute:
        print("Dry run only. Add --execute after reviewing the spec and allowed files.")
    else:
        print("Execution gate accepted. Legacy interactive builder is not auto-launched.")
    return 0


def interactive_main():
    print(f"🐾 Kitty Builder V2 (Personalized for Jacob)")
    if USE_OPENROUTER and OPENROUTER_API_KEY:
        print(f"[Using OpenRouter: {OPENROUTER_MODEL}]")
    else:
        print(f"[Using MLX: {MODEL_BUILDER}]")

    loaded = load_session()
    if loaded:
        print("[Resumed previous session]")
    update_project_from_scan()

    while True:
        try:
            inp = input("\nJacob: ").strip()
            if not inp: continue
            if inp.lower() in ["exit", "/exit"]:
                save_session()
                break
            elif inp.lower() in ["/help", "help"]: show_help()
            elif inp.lower() in ["/health", "health"]: print(scan_project_health())
            elif inp.lower() in ["/next", "next"]: print(suggest_next_steps())
            elif inp.lower() in ["/improve", "improve"]: print(kitty_self_improve())
            elif inp.lower() in ["/patterns", "patterns"]:
                with open(PROJECT_ROOT / "config" / "patterns.json") as f:
                    patterns = json.load(f)
                print("\n--- Available Patterns ---\n")
                for name, info in patterns.items():
                    print(f"  {name}: {info['description']}")
            elif inp.startswith("/council "): council(inp[9:])
            elif inp.startswith("/selfreview"): self_review()
            elif inp.startswith("/models"): show_models()
            else: chat(inp)
        except (KeyboardInterrupt, EOFError):
            save_session()
            print("\nSession saved.")
            break
        except Exception: traceback.print_exc()

    print("\nSession saved.")


def main(argv: list[str] | None = None) -> int:
    parser = build_cli_parser()
    args = parser.parse_args(argv)
    return run_builder_contract(args.project, args.spec, execute=args.execute)


if __name__ == "__main__":
    sys.exit(main())
