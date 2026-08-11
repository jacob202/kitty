from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Mapping, Sequence
from pathlib import Path

from .models import ProgressEvent

_ENV_ALLOWLIST = {
    "HOME",
    "USER",
    "LOGNAME",
    "PATH",
    "SHELL",
    "TMPDIR",
    "TMP",
    "TEMP",
    "LANG",
    "LC_ALL",
    "TERM",
    "CODEX_HOME",
}


def build_child_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    source = source or os.environ
    child = {key: value for key, value in source.items() if key in _ENV_ALLOWLIST and value}
    child.setdefault("PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
    child.setdefault("HOME", str(Path.home()))
    child.setdefault("TMPDIR", "/private/tmp")
    return child


class SubprocessRunner:
    def __init__(
        self,
        *,
        sandbox_executable: str = "/usr/bin/sandbox-exec",
        kill_grace_seconds: int = 10,
        max_lines: int = 2000,
    ) -> None:
        self.sandbox_executable = sandbox_executable
        self.kill_grace_seconds = kill_grace_seconds
        self.max_lines = max_lines

    async def stream(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        environment: Mapping[str, str],
        timeout_seconds: int,
    ) -> AsyncIterator[ProgressEvent]:
        wrapped = self._sandbox_command(tuple(command), cwd, environment)
        process = await asyncio.create_subprocess_exec(
            *wrapped,
            cwd=str(cwd),
            env=dict(environment),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert process.stdout is not None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        seen = 0
        try:
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    await self._terminate(process)
                    yield ProgressEvent(
                        kind="process_exit",
                        message=f"codex timed out after {timeout_seconds}s",
                        exit_code=124,
                        code="timeout",
                    )
                    return
                try:
                    line = await asyncio.wait_for(process.stdout.readline(), timeout=remaining)
                except TimeoutError:
                    await self._terminate(process)
                    yield ProgressEvent(
                        kind="process_exit",
                        message=f"codex timed out after {timeout_seconds}s",
                        exit_code=124,
                        code="timeout",
                    )
                    return
                if not line:
                    break
                seen += 1
                if seen <= self.max_lines:
                    yield ProgressEvent(
                        kind="progress",
                        message=line.decode("utf-8", errors="replace").rstrip(),
                    )
            exit_code = await process.wait()
            yield ProgressEvent(
                kind="process_exit",
                message=f"codex exited with {exit_code}",
                exit_code=exit_code,
            )
        except asyncio.CancelledError:
            await self._terminate(process)
            raise

    async def _terminate(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=self.kill_grace_seconds)
        except TimeoutError:
            process.kill()
            await process.wait()

    def _sandbox_command(
        self,
        command: tuple[str, ...],
        cwd: Path,
        environment: Mapping[str, str],
    ) -> tuple[str, ...]:
        profile = build_sandbox_profile(cwd, environment)
        return (self.sandbox_executable, "-p", profile, *command)


def build_sandbox_profile(cwd: Path, environment: Mapping[str, str]) -> str:
    worktree = cwd.resolve()
    for key in ("TMPDIR", "TMP", "TEMP"):
        value = environment.get(key)
        if value and not Path(value).resolve().is_relative_to(worktree):
            raise ValueError(f"{key} must be inside the run worktree")

    escaped = _escape_sbpl(str(worktree))
    return (
        f'(version 1) (allow default) '
        f'(deny file-write* (require-not (subpath "{escaped}"))) '
        '(allow file-write* (literal "/dev/null"))'
    )


def _escape_sbpl(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
