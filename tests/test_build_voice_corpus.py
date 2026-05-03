"""Tests for scripts/build_voice_corpus.py exporter parsing."""

from __future__ import annotations

from pathlib import Path

from scripts.build_voice_corpus import (
    _extract_me_bodies_from_exporter_text,
    _iter_imessage_exporter_me,
)


def test_extract_me_single_line_body() -> None:
    raw = (
        "Aug 10, 2024  5:23:16 PM\n"
        "Me\n"
        "Hi\n"
        "\n"
        "Aug 10, 2024  5:26:04 PM\n"
        "+12016492002\n"
        "Their reply\n"
    )
    bodies = _extract_me_bodies_from_exporter_text(raw)
    assert bodies == ["Hi"]


def test_extract_me_multiline_body() -> None:
    raw = (
        "Apr 01, 2023  2:14:32 AM\n"
        "Me\n"
        "Line one\n"
        "Line two\n"
        "\n"
        "Apr 01, 2023  2:17:29 AM\n"
        "Me\n"
        "Only me here\n"
    )
    bodies = _extract_me_bodies_from_exporter_text(raw)
    assert bodies == ["Line one\nLine two", "Only me here"]


def test_extract_me_skips_empty_body() -> None:
    raw = "Jan 01, 2024 12:00:00 PM\nMe\n\n\nFeb 01, 2024 12:00:00 PM\nOther\nHi\n"
    assert _extract_me_bodies_from_exporter_text(raw) == []


def test_iter_imessage_exporter_me_reads_txt_files(tmp_path: Path) -> None:
    d = tmp_path / "ex"
    d.mkdir()
    (d / "a.txt").write_text(
        "Jan 1, 2024 12:00:00 PM\nMe\nHello from a\n\n", encoding="utf-8"
    )
    (d / "b.txt").write_text(
        "Jan 2, 2024 12:00:00 PM\n+15551212\nNope\n\nJan 2, 2024 12:01:00 PM\nMe\nFrom b\n",
        encoding="utf-8",
    )
    (d / "skip.md").write_text("x", encoding="utf-8")
    lines, n_me, n_txt = _iter_imessage_exporter_me(d)
    assert n_txt == 2
    assert n_me == 2
    assert lines == ["Hello from a", "From b"]
