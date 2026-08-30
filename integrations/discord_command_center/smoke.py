from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from .adapters.codex import CodexAdapter
from .config import DEFAULT_CODEX
from .runner import SubprocessRunner
from .service import VibeService
from .workspace import GitWorktreeManager

DEFAULT_PROMPT = "Read-only smoke: inspect the repository root and report its purpose in two sentences."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test Discord Command Center Phase 0 locally")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--codex", default=os.environ.get("COMMAND_CENTER_CODEX_PATH", DEFAULT_CODEX))
    parser.add_argument("--model", default=os.environ.get("COMMAND_CENTER_CODEX_MODEL", "gpt-5.4-mini"))
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--timeout", type=int, default=120)
    return parser


async def run_smoke(args: argparse.Namespace) -> int:
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive")
    repo = args.repo.expanduser().resolve()
    service = VibeService(
        workspace=GitWorktreeManager(repo=repo, base_ref=args.base_ref),
        adapter=CodexAdapter(args.codex, args.model),
        runner=SubprocessRunner(),
        timeout_seconds=args.timeout,
        environment=os.environ,
    )
    exit_code = 1
    async for event in service.run(args.prompt):
        print(f"[{event.kind}] {event.message}")
        if event.kind == "done":
            exit_code = 0
        elif event.kind == "failed":
            exit_code = 1
    return exit_code


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(run_smoke(args))


if __name__ == "__main__":
    raise SystemExit(main())
