#!/usr/bin/env python3
"""
Autonomous Task Runner & Evaluator (V6) - Stabilized

Takes a task description, feeds it to KittyBuilder,
executes the generated plan, and verifies the output.
Includes utility functions for test-driven task tracking.
"""

import sys
import json
import argparse
import re
import os
import time
from pathlib import Path
from dataclasses import dataclass

# Force OpenRouter and R1 model for everything BEFORE imports
os.environ["USE_OPENROUTER"] = "true"
os.environ["OPENROUTER_MODEL"] = "deepseek/deepseek-r1"

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.space_kitty.llm_client import call_llm
from src.builder.intent_compiler import compile_intent
from scripts.kitty_builder import chat, session, save_session

@dataclass
class RetryState:
    status: str
    count: int
    limit: int
    error: str

def parse_retry_state(line: str) -> RetryState | None:
    """Parse a line like: Task A - BLOCKED (Retries: 2/3 - Error: timeout)"""
    pat = r"(BLOCKED|NEEDS_HUMAN)\s*\(Retries:\s*(\d+)/(\d+)\s*[-—]\s*Error:\s*(.*?)\)"
    match = re.search(pat, line)
    if not match:
        return None
    return RetryState(
        status=match.group(1),
        count=int(match.group(2)),
        limit=int(match.group(3)),
        error=match.group(4).strip()
    )

def update_tasks_text(text: str, task_query: str, error_msg: str, retry_limit: int = 3) -> tuple[str, RetryState]:
    """Find a task line and update its retry state."""
    lines = text.splitlines()
    new_lines = []
    found = False
    updated_state = None

    for line in lines:
        if not found and "[ ]" in line and task_query.lower() in line.lower():
            state = parse_retry_state(line)
            if state:
                new_count = state.count + 1
                new_status = "NEEDS_HUMAN" if new_count >= retry_limit else "BLOCKED"
            else:
                new_count = 1
                new_status = "BLOCKED"
            
            updated_state = RetryState(new_status, new_count, retry_limit, error_msg)
            # Remove existing state if any
            clean_line = re.sub(r"\s*[-—]\s*(BLOCKED|NEEDS_HUMAN).*$", "", line)
            new_line = f"{clean_line} - {new_status} (Retries: {new_count}/{retry_limit} - Error: {error_msg})"
            new_lines.append(new_line)
            found = True
        else:
            new_lines.append(line)

    if not found:
        raise ValueError(f"no open [ ] task matched '{task_query}'")

    return "\n".join(new_lines) + ("\n" if text.endswith("\n") else ""), updated_state


def run_task(task_description: str):
    print(f"=== Starting Autonomous Task Runner V6 ===")
    print(f"Task: {task_description}\n")

    # 1. Compile Intent
    print("[1] Compiling Intent (Brain Tier)...")
    try:
        brief = compile_intent(PROJECT_ROOT, task_description)
        print(f"Goal: {brief.normalized_goal}")
        # Note: assumptions[-1] is the critique in our new LLM-driven compiler
        print(f"Critique: {brief.assumptions[-1] if brief.assumptions else 'None'}")
    except Exception as e:
        print(f"Failed to compile intent: {e}")
        return 1

    # 2. Execution Loop
    print("\n[2] Beginning Execution Loop (Autonomy Level: Max)...")
    if brief.validation_commands:
        session.project_state["goal_verify"] = brief.validation_commands[0]
        print(f"Goal Verifier: {brief.validation_commands[0]}")
    
    # Force implementation by explicitly stating approval
    initial_prompt = (
        f"Technical plan APPROVED. Proceed to implementation.\n"
        f"OBJECTIVE: {brief.normalized_goal}\n"
        f"PLAN: {json.dumps(brief.to_dict(), indent=2)}\n\n"
        "Instructions:\n"
        "1. Read the current code.\n"
        "2. Implement the changes.\n"
        "3. Run tests/gates.\n\n"
        "Use the XML format for tools: <invoke name='tool'><parameter name='p'>v</parameter></invoke>"
    )
    
    try:
        chat(initial_prompt, max_iters=10)
    except Exception as e:
        print(f"\n[!] Error during execution loop: {e}")

    # 3. Final Evaluation
    print("\n[3] Final Evaluation (Grading Reasoning & Output)...")
    
    history_text = ""
    for m in session.history[-12:]:
        role = m.get('role', 'unknown').upper()
        content = m.get('content', '')
        if len(content) > 1200:
            content = content[:600] + "...[truncated]..." + content[-600:]
        history_text += f"\n--- {role} ---\n{content}\n"
    
    eval_prompt = (
        "You are the Senior Architect. Review the history below and determine if the code changes were made AND verified.\n\n"
        f"GOAL: {brief.normalized_goal}\n"
        f"HISTORY:\n{history_text}\n\n"
        "Output ONLY a JSON object with this format:\n"
        "{\n"
        "  'grade': 0-100,\n"
        "  'reasoning_critique': 'One sentence critique',\n"
        "  'output_critique': 'One sentence critique',\n"
        "  'is_finished': true/false\n"
        "}"
    )
    
    try:
        result = call_llm(eval_prompt, system_prompt="You are a JSON evaluator.")
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            report = json.loads(json_match.group(0).replace("'", '"'))
            print("\n=== ARCHITECT REPORT ===")
            print(f"Grade: {report.get('grade')}%")
            print(f"Reasoning: {report.get('reasoning_critique')}")
            print(f"Output: {report.get('output_critique')}")
            
            if report.get('is_finished'):
                print("\n✅ Task marked as SUCCESSFUL.")
                save_session()
                return 0
            else:
                print(f"\n❌ Task marked as INCOMPLETE.")
                save_session()
                return 1
        else:
            print(f"Result: {result.strip()}")
            save_session()
            return 2
            
    except Exception as e:
        print(f"Evaluation failed: {e}")
        save_session()
        return 2

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("task", help="The task to execute")
    args = parser.parse_args()
    sys.exit(run_task(args.task))
