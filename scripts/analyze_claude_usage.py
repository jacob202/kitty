#!/usr/bin/env python3
"""Rank Claude Code sessions by token spend, using the local JSONL transcripts.

Claude Code writes one JSONL file per session under ``~/.claude/projects/``.
Every assistant line carries the provider's own ``usage`` object, so these
files are the ground truth for what a session actually cost — no estimation,
no API call.

The two leaks this is built to find:
  1. A session that should have been three sessions (huge cache_read, many turns).
  2. A file that should never have been read (see the biggest-payload column).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("~/.claude/projects").expanduser()

# Only used to turn a tool_result's character count into a rough token figure
# for the "biggest payload" column. Reported as an estimate, never summed into
# the billed totals above it.
CHARS_PER_TOKEN = 4


@dataclass
class ToolUse:
    """An assistant tool_use block, kept so its result can be named later."""

    name: str
    input: dict[str, Any]


@dataclass
class Payload:
    """One oversized tool result — the per-session leak candidate."""

    label: str
    chars: int

    @property
    def estimated_tokens(self) -> int:
        return self.chars // CHARS_PER_TOKEN


@dataclass
class Session:
    path: Path
    project: str
    session_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    assistant_turns: int = 0
    compactions: int = 0
    models: set[str] = field(default_factory=set)
    first_ts: str = ""
    last_ts: str = ""
    payloads: list[Payload] = field(default_factory=list)
    # First billed turn's non-cached input: system prompt + CLAUDE.md + rules +
    # tool schemas. The floor cost of saying hello, before any work happens.
    startup_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_tokens
            + self.cache_read_tokens
        )

    @property
    def full_price_tokens(self) -> int:
        """Tokens billed at full rate — cache reads are discounted, so exclude them."""
        return self.input_tokens + self.output_tokens + self.cache_creation_tokens

    @property
    def biggest_payload(self) -> Payload | None:
        return max(self.payloads, key=lambda p: p.chars, default=None)

    @property
    def avg_context_per_turn(self) -> int:
        """Mean context re-sent per turn. The quadratic cost of one long session,
        as a single number: it climbs with every turn that isn't a fresh start."""
        if not self.assistant_turns:
            return 0
        return self.cache_read_tokens // self.assistant_turns

    @property
    def startup_share(self) -> float:
        """Fraction of full-price spend that was just loading the session."""
        if not self.full_price_tokens:
            return 0.0
        return self.startup_tokens / self.full_price_tokens

    def as_dict(self) -> dict[str, Any]:
        biggest = self.biggest_payload
        return {
            "session_id": self.session_id,
            "project": self.project,
            "path": str(self.path),
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
            "assistant_turns": self.assistant_turns,
            "compactions": self.compactions,
            "models": sorted(self.models),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "total_tokens": self.total_tokens,
            "full_price_tokens": self.full_price_tokens,
            "startup_tokens": self.startup_tokens,
            "startup_share": round(self.startup_share, 4),
            "avg_context_per_turn": self.avg_context_per_turn,
            "biggest_payload": (
                {
                    "label": biggest.label,
                    "chars": biggest.chars,
                    "estimated_tokens": biggest.estimated_tokens,
                }
                if biggest
                else None
            ),
        }


def _payload_label(block: dict[str, Any], tool_uses: dict[str, ToolUse]) -> str:
    """Name a tool_result by the tool_use that produced it.

    A tool_result carries only a tool_use_id — the tool's name and arguments live
    on the assistant's earlier tool_use block, so the two have to be joined or the
    label degrades to an opaque `toolu_…`.
    """
    call = tool_uses.get(str(block.get("tool_use_id") or ""))
    name = (call.name if call else None) or block.get("name") or "tool_result"
    payload_input = call.input if call else block.get("input")
    if isinstance(payload_input, dict):
        for key in ("file_path", "path", "notebook_path", "pattern", "command", "url"):
            value = payload_input.get(key)
            if isinstance(value, str) and value:
                return f"{name}: {value[:80]}"
    return str(name)[:80]


def _content_chars(content: Any) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(_content_chars(item) for item in content)
    if isinstance(content, dict):
        return sum(
            _content_chars(value)
            for key, value in content.items()
            if key in ("content", "text")
        )
    return 0


def _record_payloads(
    session: Session, message: dict[str, Any], tool_uses: dict[str, ToolUse]
) -> None:
    content = message.get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "tool_use":
            call_id = block.get("id")
            name = block.get("name")
            if isinstance(call_id, str) and isinstance(name, str):
                payload_input = block.get("input")
                tool_uses[call_id] = ToolUse(
                    name, payload_input if isinstance(payload_input, dict) else {}
                )
        elif block_type == "tool_result":
            chars = _content_chars(block.get("content"))
            if chars:
                session.payloads.append(
                    Payload(_payload_label(block, tool_uses), chars)
                )


def parse_session(path: Path) -> Session:
    """Aggregate one transcript. Malformed lines are skipped, not silently zeroed."""
    session = Session(path=path, project=path.parent.name)
    tool_uses: dict[str, ToolUse] = {}
    bad_lines = 0

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            bad_lines += 1
            continue
        if not isinstance(entry, dict):
            bad_lines += 1
            continue

        if not session.session_id:
            session.session_id = str(entry.get("sessionId") or path.stem)

        timestamp = entry.get("timestamp")
        if isinstance(timestamp, str) and timestamp:
            if not session.first_ts or timestamp < session.first_ts:
                session.first_ts = timestamp
            if timestamp > session.last_ts:
                session.last_ts = timestamp

        if entry.get("type") == "summary" or entry.get("isCompactSummary") is True:
            session.compactions += 1

        message = entry.get("message")
        if not isinstance(message, dict):
            continue

        _record_payloads(session, message, tool_uses)

        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue

        model = message.get("model")
        if isinstance(model, str) and model:
            session.models.add(model)

        if session.assistant_turns == 0:
            for key in ("input_tokens", "cache_creation_input_tokens"):
                value = usage.get(key)
                if isinstance(value, int) and value > 0:
                    session.startup_tokens += value

        session.assistant_turns += 1

        for key, attr in (
            ("input_tokens", "input_tokens"),
            ("output_tokens", "output_tokens"),
            ("cache_creation_input_tokens", "cache_creation_tokens"),
            ("cache_read_input_tokens", "cache_read_tokens"),
        ):
            value = usage.get(key)
            if isinstance(value, int) and value > 0:
                setattr(session, attr, getattr(session, attr) + value)

    if bad_lines:
        print(
            f"warning: {path}: skipped {bad_lines} unparseable line(s)",
            file=sys.stderr,
        )
    return session


def collect_sessions(root: Path) -> list[Session]:
    return [parse_session(path) for path in sorted(root.glob("*/*.jsonl"))]


SORT_KEYS = {
    "total": lambda s: s.total_tokens,
    "full_price": lambda s: s.full_price_tokens,
    "output": lambda s: s.output_tokens,
    "cache_read": lambda s: s.cache_read_tokens,
    "turns": lambda s: s.assistant_turns,
    "startup": lambda s: s.startup_tokens,
    "avg_context": lambda s: s.avg_context_per_turn,
}


def _thousands(value: int) -> str:
    return f"{value:,}"


def render_table(sessions: list[Session]) -> str:
    header = (
        f"{'session':<10} {'project':<24} {'turns':>6} {'in':>10} {'out':>10} "
        f"{'cache_w':>11} {'cache_r':>12} {'total':>12}"
    )
    lines = [header, "-" * len(header)]
    for session in sessions:
        lines.append(
            f"{session.session_id[:8]:<10} {session.project[-24:]:<24} "
            f"{session.assistant_turns:>6} {_thousands(session.input_tokens):>10} "
            f"{_thousands(session.output_tokens):>10} "
            f"{_thousands(session.cache_creation_tokens):>11} "
            f"{_thousands(session.cache_read_tokens):>12} "
            f"{_thousands(session.total_tokens):>12}"
        )
        if session.avg_context_per_turn:
            lines.append(
                f"{'':<10} └─ avg context re-sent per turn: "
                f"{_thousands(session.avg_context_per_turn)} tokens "
                f"over {session.assistant_turns} turns"
            )
        if session.startup_tokens:
            lines.append(
                f"{'':<10} └─ startup: {_thousands(session.startup_tokens)} tokens "
                f"({session.startup_share:.0%} of full-price spend) — "
                "system prompt + CLAUDE.md + rules + tool schemas"
            )
        biggest = session.biggest_payload
        if biggest:
            lines.append(
                f"{'':<10} └─ biggest read: {biggest.label} "
                f"(~{_thousands(biggest.estimated_tokens)} est. tokens)"
            )
        if session.compactions:
            lines.append(
                f"{'':<10} └─ {session.compactions} compaction(s) — "
                "a /clear here would have cost less"
            )
    return "\n".join(lines)


def render_totals(sessions: list[Session], shown: list[Session]) -> str:
    grand = sum(s.total_tokens for s in sessions)
    top = sum(s.total_tokens for s in shown)
    share = (top / grand * 100) if grand else 0.0
    startup = sum(s.startup_tokens for s in sessions)
    full_price = sum(s.full_price_tokens for s in sessions)
    startup_share = (startup / full_price * 100) if full_price else 0.0
    return (
        f"\n{len(sessions)} session(s), {_thousands(grand)} total tokens. "
        f"The {len(shown)} shown account for {share:.0f}% of it.\n"
        f"Startup overhead: {_thousands(startup)} tokens across all sessions "
        f"({startup_share:.0f}% of full-price spend), paid once per session.\n"
        "cache_r is billed at a fraction of full rate — treat in/out/cache_w as the "
        "expensive columns."
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rank Claude Code sessions by token spend from local transcripts."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"Transcript root to scan (default: {DEFAULT_ROOT}).",
    )
    parser.add_argument(
        "--top", type=int, default=10, help="How many sessions to show (default: 10)."
    )
    parser.add_argument(
        "--sort",
        choices=sorted(SORT_KEYS),
        default="total",
        help="Ranking key (default: total).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.expanduser()

    if not root.is_dir():
        print(f"No transcript root at {root}", file=sys.stderr)
        return 2

    sessions = collect_sessions(root)
    if not sessions:
        print(f"No *.jsonl transcripts under {root}", file=sys.stderr)
        return 2

    sessions.sort(key=SORT_KEYS[args.sort], reverse=True)
    shown = sessions[: max(args.top, 1)]

    if args.json:
        print(
            json.dumps(
                {
                    "root": str(root),
                    "sort": args.sort,
                    "session_count": len(sessions),
                    "total_tokens": sum(s.total_tokens for s in sessions),
                    "startup_tokens": sum(s.startup_tokens for s in sessions),
                    "sessions": [s.as_dict() for s in shown],
                },
                indent=2,
            )
        )
        return 0

    print(render_table(shown))
    print(render_totals(sessions, shown))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
