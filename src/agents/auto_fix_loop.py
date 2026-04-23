"""
Pillar 4: Auto-Fix Loop - Silent code generation, execution, and self-healing.

Inspired by Aider's silent file writes and Open Interpreter's execution loops.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()

MAX_RETRIES = 2

CODEGEN_SYSTEM_PROMPT = """You are a code generator. Given a task description, write Python code to accomplish it.
- Output ONLY the code, no explanations
- The code should be complete and runnable
- Handle errors gracefully"""

EXECUTION_ERROR_PROMPT = """The previous code execution failed with this error:
{error}

Fix the Python code to resolve the error. Output ONLY the corrected code."""


class CodeGenerator:
    def __init__(self):
        import os

        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.use_requests = False
        try:
            import requests

            self.requests = requests
            self.use_requests = True
        except ImportError:
            pass

    def _call_openrouter(self, model: str, messages: list, **kwargs) -> str:
        """Call OpenRouter API with fallback between requests and urllib."""
        import json

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://kitty.local",
            "X-Title": "Kitty Auto-Fix Loop",
        }
        payload = {"model": model, "messages": messages, **kwargs}

        if self.use_requests:
            response = self.requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            import urllib.request

            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                return data["choices"][0]["message"]["content"]

    def generate(self, task: str) -> str:
        """Generate code from task description."""
        messages = [
            {"role": "system", "content": CODEGEN_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Task: {task}\n\nWrite Python code to accomplish this task.",
            },
        ]
        return self._call_openrouter(
            model="deepseek/deepseek-chat-v3",
            messages=messages,
            temperature=0.2,
            max_tokens=2000,
        )

    def regenerate_with_error(self, task: str, error: str) -> str:
        """Generate fixed code given a previous error."""
        messages = [
            {"role": "system", "content": EXECUTION_ERROR_PROMPT.format(error=error)},
            {"role": "user", "content": f"Task: {task}"},
        ]
        return self._call_openrouter(
            model="deepseek/deepseek-chat-v3",
            messages=messages,
            temperature=0.2,
            max_tokens=2000,
        )


def _execute_code(file_path: str) -> tuple[int, str, str]:
    """Execute Python code and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, file_path], capture_output=True, text=True, timeout=120
    )
    return result.returncode, result.stdout, result.stderr


def _save_to_temp(code: str) -> str:
    """Save code to a temporary file and return the path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        return f.name


def _notify_success(attempts: int, output: str):
    """Display clean success notification."""
    console.print(
        Panel(
            f"[green]✓ Task completed successfully[/green]\n"
            f"[dim]Attempts: {attempts}[/dim]",
            title="Auto-Fix Loop",
            border_style="green",
            expand=False,
        )
    )
    if output.strip():
        console.print(f"[dim]{output[:500]}[/dim]")


def _notify_failure(error: str, attempts: int):
    """Display failure notification with handoff guidance."""
    console.print(
        Panel(
            f"[red]✗ Auto-fix exhausted after {attempts} attempts[/red]\n\n"
            f"[yellow]Handing off to CLI menu for clarification...[/yellow]",
            title="Auto-Fix Loop",
            border_style="red",
            expand=False,
        )
    )


def _extract_code(response: str) -> str:
    """Extract code from model response, handling markdown code blocks."""
    code = response.strip()

    if code.startswith("```"):
        lines = code.split("\n")
        if len(lines) >= 2:
            code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    if code.startswith("```python"):
        code = code[9:]
    if code.startswith("```py"):
        code = code[5:]
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]

    return code.strip()


def _copy_to_target(temp_path: str, target_file: str):
    """Copy executed code to the target file."""
    content = Path(temp_path).read_text()
    Path(target_file).parent.mkdir(parents=True, exist_ok=True)
    Path(target_file).write_text(content)


def execute_task(task: str, target_file: str, model: str = "flash") -> dict:
    """
    Execute a coding task with automatic error recovery.

    Args:
        task: Description of the task to accomplish
        target_file: Path to the target file to create/modify
        model: Model to use (reserved for future use)

    Returns:
        dict with keys: success (bool), output (str), error (str), attempts (int)
    """
    result = {"success": False, "output": "", "error": "", "attempts": 0}

    temp_path: str | None = None

    generator = CodeGenerator()

    for attempt in range(MAX_RETRIES + 1):
        result["attempts"] = attempt + 1

        try:
            if attempt == 0:
                raw_code = generator.generate(task)
            else:
                raw_code = generator.regenerate_with_error(task, result["error"])

            code = _extract_code(raw_code)
            temp_path = _save_to_temp(code)

            returncode, stdout, stderr = _execute_code(temp_path)

            if returncode == 0:
                _copy_to_target(temp_path, target_file)
                result["success"] = True
                result["output"] = stdout
                _notify_success(result["attempts"], stdout)
                return result
            else:
                result["error"] = stderr or f"Exit code: {returncode}"

        except Exception as e:
            result["error"] = f"{type(e).__name__}: {str(e)}"

        finally:
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink(missing_ok=True)

        if attempt < MAX_RETRIES:
            console.print(f"[dim]Attempt {attempt + 1} failed, retrying...[/dim]")

    _notify_failure(result["error"], result["attempts"])
    return result


def handoff_to_cli(error: str, task: str) -> str | None:
    """
    Hand off to CLI menu for user clarification.

    Returns:
        Clarified task description or None to abort
    """
    try:
        from src.cli_menus import show_clarity_menu

        options = [
            f"Simplify: {task}",
            f"Clarify: {task} (add more details)",
            "Abort task",
        ]

        choice = show_clarity_menu(task, options)

        if choice == "Abort task":
            return None
        return choice

    except ImportError:
        console.print("[yellow]CLI menus not available, returning None[/yellow]")
        return None


if __name__ == "__main__":
    import json

    result = execute_task("print hello world", "/tmp/test.py")
    print(json.dumps(result, indent=2))
