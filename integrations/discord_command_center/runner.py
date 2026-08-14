from __future__ import annotations

import asyncio
import json
import os
import signal
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
    "CODEX_AUTH_FILE",
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
        max_line_bytes: int = 1_048_576,
    ) -> None:
        self.sandbox_executable = sandbox_executable
        self.kill_grace_seconds = kill_grace_seconds
        self.max_lines = max_lines
        self.max_line_bytes = max_line_bytes

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
            start_new_session=True,
            limit=self.max_line_bytes + 1,
        )
        assert process.stdout is not None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        seen = 0
        terminal_evidence_seen = False
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
                except Exception:
                    await self._terminate(process)
                    raise
                if not line:
                    break
                if len(line) > self.max_line_bytes:
                    await self._terminate(process)
                    raise ValueError(
                        f"worker stdout record exceeds {self.max_line_bytes} bytes"
                    )
                seen += 1
                terminal_evidence = _terminal_evidence(line)
                if terminal_evidence:
                    terminal_evidence_seen = True
                if terminal_evidence == "error":
                    yield ProgressEvent(
                        kind="process_error",
                        message=line.decode("utf-8", errors="replace").rstrip(),
                        code="worker_error",
                    )
                elif seen <= self.max_lines or terminal_evidence:
                    yield ProgressEvent(
                        kind="progress",
                        message=line.decode("utf-8", errors="replace").rstrip(),
                    )
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
                exit_code = await asyncio.wait_for(process.wait(), timeout=remaining)
            except TimeoutError:
                await self._terminate(process)
                yield ProgressEvent(
                    kind="process_exit",
                    message=f"codex timed out after {timeout_seconds}s",
                    exit_code=124,
                    code="timeout",
                )
                return
            if seen > self.max_lines and not terminal_evidence_seen:
                yield ProgressEvent(
                    kind="process_exit",
                    message="worker terminal evidence was not trusted after progress limit",
                    exit_code=exit_code,
                    code="terminal_evidence_untrusted",
                )
                return
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
        _signal_process_group(process, signal.SIGTERM)
        try:
            await asyncio.wait_for(process.wait(), timeout=self.kill_grace_seconds)
        except TimeoutError:
            _signal_process_group(process, signal.SIGKILL)
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
    read_paths = [str(worktree), "/dev/null", "/dev/urandom", "/dev/random"]
    read_paths.extend(("/bin", "/sbin", "/usr/bin", "/usr/sbin", "/usr/lib", "/usr/local/bin"))
    if Path("/opt/homebrew").exists():
        read_paths.append("/opt/homebrew")
    auth_file = environment.get("CODEX_AUTH_FILE")
    if auth_file:
        read_paths.append(str(Path(auth_file).resolve()))
    read_rules = " ".join(f'(allow file-read* (subpath "{_escape_sbpl(path)}"))' for path in read_paths)
    return (
        f'(version 1) (allow process*) (allow sysctl-read) (allow mach-lookup) '
        f'(deny file-read*) {read_rules} '
        f'(deny file-write* (require-not (subpath "{escaped}"))) '
        '(allow file-write* (literal "/dev/null"))'
    )


def _terminal_evidence(line: bytes) -> str | None:
    try:
        payload = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("type") in {"error", "turn.failed"}:
        return "error"
    if payload.get("type") in {"turn.completed", "response.completed"}:
        return "answer"
    item = payload.get("item")
    if isinstance(item, dict) and item.get("type") == "agent_message":
        return "answer"
    return None


def _escape_sbpl(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _signal_process_group(process: asyncio.subprocess.Process, sig: int) -> None:
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        if process.returncode is None:
            raise
