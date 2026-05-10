import asyncio
import os
import tempfile
from typing import Any


class JITSandboxRunner:
    """
    Safely executes AI-generated single-use scripts in an isolated process.
    """

    def __init__(self, execution_timeout_seconds: int = 5):
        self.timeout = execution_timeout_seconds
        self._successful_snippets: list[str] = []

    async def execute_generated_code(self, code_string: str) -> dict[str, Any]:
        fd, script_path = tempfile.mkstemp(suffix=".py", prefix="kitty_jit_")
        sentinel = "__KITTY_CURRENT_SNIPPET_OUTPUT__"
        script = "\n\n".join(
            [
                *self._successful_snippets,
                f"print({sentinel!r})",
                code_string,
            ]
        )

        try:
            with os.fdopen(fd, "w") as f:
                f.write(script)

            process = await asyncio.create_subprocess_exec(
                "python3",
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)

                decoded_stdout = stdout.decode("utf-8").strip()
                if sentinel in decoded_stdout:
                    decoded_stdout = decoded_stdout.split(sentinel, 1)[1].strip()

                success = process.returncode == 0
                if success and code_string.strip():
                    self._successful_snippets.append(code_string)

                return {
                    "success": success,
                    "exit_code": process.returncode,
                    "stdout": decoded_stdout,
                    "stderr": stderr.decode("utf-8").strip(),
                    "status": "completed",
                }

            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                return {
                    "success": False,
                    "exit_code": 124,
                    "stdout": "",
                    "stderr": f"Execution halted: Script exceeded {self.timeout}-second timeout limit.",
                    "status": "timed_out",
                }

        finally:
            if os.path.exists(script_path):
                os.remove(script_path)
