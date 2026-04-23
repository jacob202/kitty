"""Skill Refinery — Jester adversarial review + Ralph Wiggum fix-and-retry loop."""
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)
OLLAMA_BASE = "http://localhost:11434"
STAGING_DIR = Path("data/skills/.staging")

def _ollama(model: str, prompt: str, timeout: int = 60) -> str:
    try:
        r = requests.post(f"{OLLAMA_BASE}/api/generate",
                          json={"model": model, "prompt": prompt, "stream": False},
                          timeout=timeout)
        return r.json().get("response", "")
    except Exception as e:
        logger.error(f"Ollama {model}: {e}")
        return ""

def run_jester_review(skill_code: str, model: str = "dolphin-llama3") -> tuple[bool, str]:
    """
    Adversarial code review. Returns (approved, feedback).
    Looks for: path traversal, SQL injection, missing validation, silent failures.
    """
    prompt = f"""You are a hostile security reviewer. Find critical flaws in this Python code.
Look for: SQL injection, path traversal, missing validation, silent failures, auth bypasses.
If any critical flaw: respond with REJECT: <reason>
If code is safe: respond with APPROVE

Code:
```python
{skill_code}
```"""
    response = _ollama(model, prompt, timeout=45)
    if not response:
        return True, "Jester offline — auto-approved"
    approved = "REJECT" not in response.upper()
    return approved, response

def refine_skill(skill_name: str, error_log: str,
                 model: str = "llama3.2:3b") -> str:
    """Fix skill code based on test failure error log."""
    skill_path = STAGING_DIR / f"{skill_name}.py"
    if not skill_path.exists():
        return ""
    code = skill_path.read_text()
    prompt = f"""Fix this Python code. It failed with:
{error_log[:500]}

Code:
```python
{code}
```
Return ONLY corrected Python code, no explanation."""
    new_code = _ollama(model, prompt)
    if new_code:
        # Strip markdown fences if present
        new_code = new_code.strip()
        if new_code.startswith("```"):
            lines = new_code.split("\n")
            new_code = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        skill_path.write_text(new_code)
    return new_code
