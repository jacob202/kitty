from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.analyze_claude_usage import main, parse_session


def _write_transcript(path: Path, *entries: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8"
    )
    return path


def _assistant(usage: dict[str, int], timestamp: str = "2026-07-30T10:00:00Z") -> dict:
    return {
        "type": "assistant",
        "sessionId": "sess-aaaaaaaa-1111",
        "timestamp": timestamp,
        "message": {
            "role": "assistant",
            "model": "claude-opus-5",
            "content": [{"type": "text", "text": "ok"}],
            "usage": usage,
        },
    }


def test_parse_session_sums_all_four_usage_buckets(tmp_path):
    transcript = _write_transcript(
        tmp_path / "-home-user-kitty" / "sess-aaaaaaaa-1111.jsonl",
        _assistant(
            {
                "input_tokens": 10,
                "output_tokens": 200,
                "cache_creation_input_tokens": 3_000,
                "cache_read_input_tokens": 40_000,
            },
            timestamp="2026-07-30T10:00:00Z",
        ),
        _assistant(
            {
                "input_tokens": 5,
                "output_tokens": 100,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 45_000,
            },
            timestamp="2026-07-30T10:05:00Z",
        ),
    )

    session = parse_session(transcript)

    assert session.session_id == "sess-aaaaaaaa-1111"
    assert session.project == "-home-user-kitty"
    assert session.assistant_turns == 2
    assert session.input_tokens == 15
    assert session.output_tokens == 300
    assert session.cache_creation_tokens == 3_000
    assert session.cache_read_tokens == 85_000
    assert session.total_tokens == 88_315
    assert session.full_price_tokens == 3_315
    assert session.models == {"claude-opus-5"}
    assert session.first_ts == "2026-07-30T10:00:00Z"
    assert session.last_ts == "2026-07-30T10:05:00Z"


def test_startup_tokens_come_from_the_first_billed_turn_only(tmp_path):
    transcript = _write_transcript(
        tmp_path / "proj" / "sess-startup.jsonl",
        _assistant(
            {
                "input_tokens": 300,
                "cache_creation_input_tokens": 21_700,
                "output_tokens": 40,
            },
            timestamp="2026-07-30T10:00:00Z",
        ),
        _assistant(
            {
                "input_tokens": 12,
                "cache_creation_input_tokens": 5_000,
                "output_tokens": 60,
                "cache_read_input_tokens": 22_000,
            },
            timestamp="2026-07-30T10:01:00Z",
        ),
    )

    session = parse_session(transcript)

    assert session.startup_tokens == 22_000
    # full_price = 312 in + 100 out + 26_700 cache_w
    assert session.full_price_tokens == 27_112
    assert round(session.startup_share, 4) == round(22_000 / 27_112, 4)


def test_startup_share_is_zero_when_nothing_was_billed(tmp_path):
    transcript = _write_transcript(
        tmp_path / "proj" / "sess-empty.jsonl",
        {"type": "user", "sessionId": "sess-empty", "message": {"role": "user"}},
    )

    session = parse_session(transcript)

    assert session.startup_tokens == 0
    assert session.startup_share == 0.0


def test_main_reports_startup_overhead_and_sorts_by_it(tmp_path, capsys):
    _write_transcript(
        tmp_path / "proj" / "lean.jsonl",
        _assistant({"input_tokens": 5, "cache_creation_input_tokens": 1_000}),
    )
    _write_transcript(
        tmp_path / "proj" / "heavy-preamble.jsonl",
        _assistant({"input_tokens": 200, "cache_creation_input_tokens": 40_000}),
    )

    assert main(["--root", str(tmp_path), "--sort", "startup", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["startup_tokens"] == 41_205
    assert payload["sessions"][0]["startup_tokens"] == 40_200
    assert payload["sessions"][0]["startup_share"] == 1.0


def test_table_names_startup_overhead(tmp_path, capsys):
    _write_transcript(
        tmp_path / "proj" / "sess-e.jsonl",
        _assistant({"input_tokens": 100, "cache_creation_input_tokens": 22_000}),
    )

    assert main(["--root", str(tmp_path)]) == 0

    out = capsys.readouterr().out
    assert "startup: 22,100 tokens" in out
    assert "CLAUDE.md" in out
    assert "Startup overhead:" in out


def test_parse_session_flags_biggest_tool_result_and_compaction(tmp_path):
    transcript = _write_transcript(
        tmp_path / "proj" / "sess-b.jsonl",
        {
            "type": "user",
            "sessionId": "sess-b",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "name": "Read",
                        "input": {"file_path": "/repo/package-lock.json"},
                        "content": "x" * 400_000,
                    },
                    {
                        "type": "tool_result",
                        "name": "Grep",
                        "input": {"pattern": "def main"},
                        "content": "small",
                    },
                ],
            },
        },
        {"type": "summary", "summary": "compacted", "leafUuid": "u1"},
        _assistant({"input_tokens": 1, "output_tokens": 1}),
    )

    session = parse_session(transcript)

    assert session.compactions == 1
    biggest = session.biggest_payload
    assert biggest is not None
    assert "package-lock.json" in biggest.label
    assert biggest.chars == 400_000
    assert biggest.estimated_tokens == 100_000


def test_payload_label_joins_tool_result_back_to_its_tool_use(tmp_path):
    """A tool_result carries only a tool_use_id; the name/args live on the
    assistant's tool_use. Without the join the label degrades to `toolu_…`."""
    transcript = _write_transcript(
        tmp_path / "proj" / "sess-join.jsonl",
        {
            "type": "assistant",
            "sessionId": "sess-join",
            "message": {
                "role": "assistant",
                "model": "claude-opus-5",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_01Ak2jFu4fLCgw6AcvMnaB7X",
                        "name": "Read",
                        "input": {"file_path": "/repo/pnpm-lock.yaml"},
                    }
                ],
                "usage": {"input_tokens": 5, "output_tokens": 5},
            },
        },
        {
            "type": "user",
            "sessionId": "sess-join",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_01Ak2jFu4fLCgw6AcvMnaB7X",
                        "content": [{"type": "text", "text": "q" * 60_000}],
                    }
                ],
            },
        },
    )

    biggest = parse_session(transcript).biggest_payload

    assert biggest is not None
    assert biggest.label == "Read: /repo/pnpm-lock.yaml"
    assert "toolu_" not in biggest.label
    assert biggest.chars == 60_000


def test_payload_label_falls_back_when_tool_use_is_absent(tmp_path):
    transcript = _write_transcript(
        tmp_path / "proj" / "sess-orphan.jsonl",
        {
            "type": "user",
            "sessionId": "sess-orphan",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_missing",
                        "content": "r" * 100,
                    }
                ],
            },
        },
    )

    biggest = parse_session(transcript).biggest_payload

    assert biggest is not None
    assert biggest.label == "tool_result"


def test_avg_context_per_turn_exposes_the_long_session(tmp_path, capsys):
    _write_transcript(
        tmp_path / "proj" / "marathon.jsonl",
        *[
            _assistant(
                {"output_tokens": 100, "cache_read_input_tokens": 300_000},
                timestamp=f"2026-07-30T10:{minute:02d}:00Z",
            )
            for minute in range(4)
        ],
    )
    _write_transcript(
        tmp_path / "proj" / "sprint.jsonl",
        _assistant({"output_tokens": 100, "cache_read_input_tokens": 8_000}),
    )

    assert main(["--root", str(tmp_path), "--sort", "avg_context", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["sessions"][0]["avg_context_per_turn"] == 300_000
    assert payload["sessions"][0]["assistant_turns"] == 4
    assert payload["sessions"][1]["avg_context_per_turn"] == 8_000


def test_avg_context_per_turn_is_zero_without_turns(tmp_path):
    transcript = _write_transcript(
        tmp_path / "proj" / "sess-noturns.jsonl",
        {"type": "user", "sessionId": "x", "message": {"role": "user"}},
    )

    assert parse_session(transcript).avg_context_per_turn == 0


def test_parse_session_skips_malformed_lines_and_warns(tmp_path, capsys):
    transcript = tmp_path / "proj" / "sess-c.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps(_assistant({"input_tokens": 7, "output_tokens": 2}))
        + "\n{ not json\n[]\n",
        encoding="utf-8",
    )

    session = parse_session(transcript)

    assert session.input_tokens == 7
    assert "skipped 2 unparseable line(s)" in capsys.readouterr().err


def test_main_ranks_sessions_and_reports_share(tmp_path, capsys):
    _write_transcript(
        tmp_path / "proj" / "cheap.jsonl",
        _assistant({"input_tokens": 1, "output_tokens": 1}),
    )
    _write_transcript(
        tmp_path / "proj" / "expensive.jsonl",
        _assistant({"input_tokens": 10, "cache_read_input_tokens": 500_000}),
    )

    assert main(["--root", str(tmp_path), "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["session_count"] == 2
    assert payload["total_tokens"] == 500_012
    assert payload["sessions"][0]["cache_read_tokens"] == 500_000


def test_main_sort_by_output_reorders(tmp_path, capsys):
    _write_transcript(
        tmp_path / "proj" / "chatty.jsonl",
        _assistant({"output_tokens": 90_000}),
    )
    _write_transcript(
        tmp_path / "proj" / "cache-heavy.jsonl",
        _assistant({"cache_read_input_tokens": 900_000}),
    )

    assert main(["--root", str(tmp_path), "--sort", "output", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["sessions"][0]["output_tokens"] == 90_000


def test_main_fails_loud_when_root_missing(tmp_path, capsys):
    assert main(["--root", str(tmp_path / "nope")]) == 2
    assert "No transcript root" in capsys.readouterr().err


def test_main_fails_loud_when_root_has_no_transcripts(tmp_path, capsys):
    assert main(["--root", str(tmp_path)]) == 2
    assert "No *.jsonl transcripts" in capsys.readouterr().err


def test_table_output_names_the_leak(tmp_path, capsys):
    _write_transcript(
        tmp_path / "-home-user-kitty" / "sess-d.jsonl",
        {
            "type": "user",
            "sessionId": "sess-d",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "name": "Read",
                        "input": {"file_path": "/repo/pnpm-lock.yaml"},
                        "content": "y" * 200_000,
                    }
                ],
            },
        },
        _assistant({"input_tokens": 50, "output_tokens": 50}),
    )

    assert main(["--root", str(tmp_path)]) == 0

    out = capsys.readouterr().out
    assert "pnpm-lock.yaml" in out
    assert "biggest read" in out
    assert "1 session(s)" in out
