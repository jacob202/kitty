"""KittyBench: ISC (Ideal State Criteria) pipeline regression.

Exercises the full ISC lifecycle: derive → format → check → all_passed.
The unit tests in test_success_criteria.py test each function in isolation;
this benchmark tests them as a pipeline, catching regressions in the
composition of these functions.

Packet: ISA-lite (success criteria module)
"""

from unittest.mock import patch

from gateway import builder_isc as isc


SAMPLE_GOAL = "Add a --no-color flag to the CLI that suppresses ANSI output"
SAMPLE_CRITERIA = [
    "no-color flag is accepted without error",
    "Output contains no ANSI escape codes when flag is set",
    "Existing colored output is unchanged when flag is absent",
    "Anti: help text is not altered",
]
SAMPLE_EVIDENCE = (
    "Tests passed: 14/14\n"
    "test_no_color_flag_accepted: PASS\n"
    "test_no_ansi_when_flag_set: PASS\n"
    "test_existing_output_unchanged: PASS\n"
    "test_help_text_unchanged: PASS\n"
)
SAMPLE_LLM_RESPONSE = (
    '[{"criterion": "--no-color flag is accepted without error", "passed": true, "note": "test passes"}, '
    '{"criterion": "Output contains no ANSI escape codes when flag is set", "passed": true, "note": "verified"}, '
    '{"criterion": "Existing colored output is unchanged when flag is absent", "passed": true, "note": "all existing tests pass"}, '
    '{"criterion": "Anti: help text is not altered", "passed": true, "note": "help text test passes"}]'
)


def test_isc_full_pipeline_derives_checks_and_passes():
    """Derive criteria from a goal, then check them against passing evidence."""
    with patch("gateway.builder_isc.llm_client.chat") as mock_chat:
        mock_chat.side_effect = [
            "\n".join(f"- {c}" for c in SAMPLE_CRITERIA),
            SAMPLE_LLM_RESPONSE,
        ]

        criteria = isc.derive_criteria(SAMPLE_GOAL)
        assert len(criteria) > 0

        formatted = isc.format_criteria_block(criteria)
        assert "## Success Criteria (ISC)" in formatted
        for c in SAMPLE_CRITERIA:
            assert f"- [ ] {c}" in formatted

        results = isc.check_criteria(SAMPLE_GOAL, criteria, SAMPLE_EVIDENCE)
        assert len(results) == len(criteria)

        assert isc.all_criteria_passed(results)


def test_isc_pipeline_with_failing_criteria():
    """Derive criteria, then check them against failing evidence."""
    failing_response = (
        '[{"criterion": "--no-color flag is accepted without error", "passed": true, "note": "ok"}, '
        '{"criterion": "Output contains no ANSI escape codes when flag is set", "passed": false, "note": "ANSI still present"}, '
        '{"criterion": "Existing colored output is unchanged when flag is absent", "passed": true, "note": "ok"}, '
        '{"criterion": "Anti: help text is not altered", "passed": true, "note": "ok"}]'
    )

    with patch("gateway.builder_isc.llm_client.chat") as mock_chat:
        mock_chat.side_effect = [
            "\n".join(f"- {c}" for c in SAMPLE_CRITERIA),
            failing_response,
        ]

        criteria = isc.derive_criteria(SAMPLE_GOAL)
        results = isc.check_criteria(SAMPLE_GOAL, criteria, SAMPLE_EVIDENCE)

        assert not isc.all_criteria_passed(results)
        assert sum(1 for r in results if r["passed"]) == 3
        assert sum(1 for r in results if not r["passed"]) == 1


def test_isc_pipeline_llm_failure_is_graceful():
    """When the LLM fails, the pipeline returns empty/neutral results."""
    with patch("gateway.builder_isc.llm_client.chat", side_effect=RuntimeError("down")):
        criteria = isc.derive_criteria(SAMPLE_GOAL)
        assert criteria == []

        results = isc.check_criteria(SAMPLE_GOAL, SAMPLE_CRITERIA, SAMPLE_EVIDENCE)
        assert len(results) == len(SAMPLE_CRITERIA)
        assert all(r["passed"] is False for r in results)
        assert all(r["note"] == "unverified" for r in results)

    assert not isc.all_criteria_passed(results)


def test_isc_format_block_edge_cases():
    """Format handles empty input, strings, dicts with and without notes."""
    assert isc.format_criteria_block([]) == ""

    block = isc.format_criteria_block(["single criterion"])
    assert "single criterion" in block

    block = isc.format_criteria_block([
        {"criterion": "passes", "passed": True, "note": ""},
        {"criterion": "fails", "passed": False, "note": "bad"},
    ])
    assert "- [x] passes" in block
    assert "- [ ] fails — bad" in block


def test_isc_max_criteria_cap():
    """derive_criteria never returns more than MAX_CRITERIA items."""
    raw = "\n".join(f"{i}. criterion {i}" for i in range(1, 20))
    with patch("gateway.builder_isc.llm_client.chat", return_value=raw):
        criteria = isc.derive_criteria("large goal")
    assert len(criteria) <= isc.MAX_CRITERIA
    assert len(criteria) > 0
