#!/usr/bin/env python3
"""Run bounded, read-only opinions from local coding-agent CLIs.

The persistent Kitty/Letta agent can invoke this for an explicit ``council:``
request. Each worker is isolated as a subprocess and receives the same prompt;
the caller remains responsible for synthesis and any later mutation.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_CODEX = "/Applications/ChatGPT.app/Contents/Resources/codex"
DEFAULT_CLAUDE = "/opt/homebrew/bin/claude"
DEFAULT_CLAUDE_FALLBACK_MODEL = "opencode/claude-sonnet-4"


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    output: str


@dataclass(frozen=True)
class Worker:
    name: str
    command: tuple[str, ...]
    environment: dict[str, str] | None = None
    fallback_command: tuple[str, ...] | None = None
    fallback_environment: dict[str, str] | None = None
    fallback_label: str | None = None


def _executable(preferred: str, fallback: str) -> str:
    if Path(preferred).is_file():
        return preferred
    found = shutil.which(fallback)
    return found or preferred


def build_workers(repo: Path, prompt: str) -> tuple[Worker, ...]:
    """Build safe worker commands without invoking a shell."""

    instruction = (
        "You are a read-only member of an agent council. Do not edit files, "
        "run mutating commands, publish anything, contact external services, "
        "or spend money. Analyze the request independently and return concise "
        "evidence, risks, and a recommendation.\n\nREQUEST:\n" + prompt
    )
    codex_model = os.environ.get("COUNCIL_CODEX_MODEL", "gpt-5.4-mini")
    opencode_model = os.environ.get(
        "COUNCIL_OPENCODE_MODEL", "opencode/deepseek-v4-flash-free"
    )
    claude_model = os.environ.get("COUNCIL_CLAUDE_MODEL")
    claude_fallback_model = os.environ.get(
        "COUNCIL_CLAUDE_FALLBACK_MODEL", DEFAULT_CLAUDE_FALLBACK_MODEL
    )

    codex = [
        _executable(DEFAULT_CODEX, "codex"),
        "exec",
        "--ephemeral",
        "--cd",
        str(repo),
        "--sandbox",
        "read-only",
        "--model",
        codex_model,
        instruction,
    ]
    claude = [
        _executable(DEFAULT_CLAUDE, "claude"),
        "-p",
        instruction,
        "--permission-mode",
        "plan",
        "--output-format",
        "text",
    ]
    if claude_model:
        claude.extend(["--model", claude_model])
    opencode = [
        _executable("/opt/homebrew/bin/opencode", "opencode"),
        "run",
        "--format",
        "default",
        "--model",
        opencode_model,
        "--dir",
        str(repo),
        instruction,
    ]
    opencode_environment = {
        "OPENCODE_CONFIG_CONTENT": json.dumps(
            {
                "permission": {
                    "edit": "deny",
                    "bash": "deny",
                    "external_directory": "deny",
                }
            }
        )
    }
    claude_fallback = None
    if claude_fallback_model:
        claude_fallback = (
            _executable("/opt/homebrew/bin/opencode", "opencode"),
            "run",
            "--format",
            "default",
            "--model",
            claude_fallback_model,
            "--dir",
            str(repo),
            instruction,
        )
    return (
        Worker("Codex", tuple(codex)),
        Worker(
            "Claude",
            tuple(claude),
            fallback_command=claude_fallback,
            fallback_environment=opencode_environment if claude_fallback else None,
            fallback_label=(
                f"OpenCode fallback model {claude_fallback_model}"
                if claude_fallback
                else None
            ),
        ),
        Worker("OpenCode", tuple(opencode), opencode_environment),
    )


def _run_command(
    command: tuple[str, ...],
    timeout: int,
    environment: dict[str, str] | None = None,
) -> CommandResult:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **(environment or {})},
        )
    except FileNotFoundError as exc:
        return CommandResult(False, f"ERROR: executable unavailable: {exc.filename}")
    except subprocess.TimeoutExpired:
        return CommandResult(False, f"ERROR: timed out after {timeout}s")

    output = (result.stdout or result.stderr).strip()
    if not output:
        output = "(worker returned no output)"
    if result.returncode:
        return CommandResult(False, f"ERROR: exit {result.returncode}\n{output}")
    return CommandResult(True, output)


def run_worker(worker: Worker, timeout: int, dry_run: bool) -> str:
    if dry_run:
        lines = [f"$ {' '.join(worker.command)}"]
        if worker.fallback_command and worker.fallback_label:
            lines.append(
                f"Fallback ({worker.fallback_label}): $ {' '.join(worker.fallback_command)}"
            )
        return "\n".join(lines)

    primary = _run_command(worker.command, timeout, worker.environment)
    if primary.ok or not worker.fallback_command or not worker.fallback_label:
        return primary.output

    fallback = _run_command(
        worker.fallback_command, timeout, worker.fallback_environment
    )
    return (
        f"WARNING: primary worker failed; retrying via {worker.fallback_label}.\n"
        f"Primary result:\n{primary.output}\n\n"
        f"Fallback result:\n{fallback.output}"
    )


def run_council(
    repo: Path, prompt: str, timeout: int, dry_run: bool = False
) -> str:
    workers = build_workers(repo, prompt)
    results: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(workers)) as pool:
        futures = {
            pool.submit(run_worker, worker, timeout, dry_run): worker.name
            for worker in workers
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    sections = [f"## {worker.name}\n{results[worker.name]}" for worker in workers]
    return "\n\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="question for the agent council")
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="read-only repository context (default: current directory)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"per-worker timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="show commands without invoking workers"
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    print(run_council(args.repo.resolve(), args.prompt, args.timeout, args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
