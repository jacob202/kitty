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
