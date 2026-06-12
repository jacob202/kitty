"""Tests for gateway.success_criteria (ISA-lite criteria derive/check)."""
from unittest.mock import patch

from gateway import success_criteria as sc


def test_derive_parses_and_strips_numbering():
    raw = "1. Output has no color\n- Anti: no new warnings\n* Exit code is 0\n"
    with patch("gateway.success_criteria.llm_client.chat", return_value=raw):
        out = sc.derive("add --no-color flag")
    assert out == ["Output has no color", "Anti: no new warnings", "Exit code is 0"]


def test_derive_caps_at_max():
    raw = "\n".join(f"criterion {i}" for i in range(20))
    with patch("gateway.success_criteria.llm_client.chat", return_value=raw):
        out = sc.derive("big goal")
    assert len(out) == sc.MAX_CRITERIA


def test_derive_empty_goal_returns_empty():
    assert sc.derive("   ") == []


def test_derive_llm_failure_returns_empty():
    with patch("gateway.success_criteria.llm_client.chat", side_effect=RuntimeError("boom")):
        assert sc.derive("goal") == []


def test_check_parses_json_array():
    resp = (
        'Here you go: [{"criterion": "no color", "passed": true, "note": "ok"}, '
        '{"criterion": "exit 0", "passed": false, "note": "rc=1"}]'
    )
    with patch("gateway.success_criteria.llm_client.chat", return_value=resp):
        out = sc.check("goal", ["no color", "exit 0"], "evidence")
    assert out[0] == {"criterion": "no color", "passed": True, "note": "ok"}
    assert out[1]["passed"] is False


def test_check_no_criteria_returns_empty():
    assert sc.check("goal", [], "evidence") == []


def test_check_llm_failure_is_neutral():
    with patch("gateway.success_criteria.llm_client.chat", side_effect=RuntimeError("x")):
        out = sc.check("goal", ["a", "b"], "evidence")
    assert [r["passed"] for r in out] == [False, False]
    assert all(r["note"] == "unverified" for r in out)


def test_format_block_for_strings_and_results():
    assert sc.format_block([]) == ""
    assert "- [ ] do thing" in sc.format_block(["do thing"])
    block = sc.format_block([{"criterion": "x", "passed": True, "note": "good"}])
    assert "- [x] x — good" in block


def test_all_passed():
    assert sc.all_passed([]) is False
    assert sc.all_passed([{"passed": True}, {"passed": True}]) is True
    assert sc.all_passed([{"passed": True}, {"passed": False}]) is False
