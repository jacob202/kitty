"""Tests for scripts/check_agent_coordination.py."""

from datetime import date

import pytest

from scripts.check_agent_coordination import (
    _active_lanes_section,
    stale_in_progress_warnings,
)


def test_active_lanes_section_extracts_until_next_heading():
    md = """# X
## Active Lanes
here
| a | b |
## Other
gone
"""
    assert "here" in _active_lanes_section(md)
    assert "gone" not in _active_lanes_section(md)


def test_stale_in_progress_detects_old_started_date():
    section = """
| Lane ID | Agent | Started | Status | Description |
|---------|-------|---------|--------|-------------|
| `x-001` | codex | 2020-01-01 | in-progress | still open |
"""
    warnings = stale_in_progress_warnings(section, date(2026, 4, 30))
    assert len(warnings) == 1
    assert "x-001" in warnings[0]
    assert "codex" in warnings[0]


def test_fresh_in_progress_no_warning():
    section = """
| `x-001` | codex | 2026-04-29 | in-progress | recent |
"""
    warnings = stale_in_progress_warnings(section, date(2026, 4, 30))
    assert warnings == []


@pytest.mark.parametrize(
    "line",
    [
        "| Lane ID | Agent | Started | Status | Description |",
        "|---------|-------|---------|--------|-------------|",
    ],
)
def test_stale_skips_header_and_separator(line: str):
    assert stale_in_progress_warnings(line, date(2099, 1, 1)) == []
