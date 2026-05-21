#!/usr/bin/env python3
"""Review the current git diff using the dedicated @reviewer agent."""
import sys
import subprocess
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from gateway.agents import get_agent_prompt
from gateway.llm_client import call_llm

def main():
    print("Gathering git diff...")
    diff_proc = subprocess.run(["git", "diff", "HEAD"], capture_output=True, text=True)
    diff_text = diff_proc.stdout.strip()
    
    if not diff_text:
        print("No changes found to review.")
        return 0

    reviewer_prompt = get_agent_prompt("reviewer")
    if not reviewer_prompt:
        print("Error: @reviewer agent persona not found in AGENTS.md.")
        return 1

    messages = [
        {"role": "system", "content": reviewer_prompt},
        {"role": "user", "content": f"Please review the following changes:\n\n```diff\n{diff_text}\n```"}
    ]

    print("Analyzing changes with @reviewer agent...")
    try:
        # Use reasoning model for thorough code review
        response = call_llm(messages, model="reasoning")
        print("\n--- Code Review ---\n")
        print(response)
        print("\n-------------------\n")
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
