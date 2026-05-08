import pytest
from scripts.overnight_retry import parse_retry_state, update_tasks_text, RetryState

def test_parse_retry_state_handles_ascii_dash():
    state = parse_retry_state("Task A - BLOCKED (Retries: 2/3 - Error: timeout)")
    assert isinstance(state, RetryState)
    assert state.status == "BLOCKED"
    assert state.count == 2
    assert state.limit == 3
    assert state.error == "timeout"


def test_parse_retry_state_handles_em_dash():
    state = parse_retry_state("Task A — NEEDS_HUMAN (Retries: 3/3 — Error: flaky env)")
    assert state is not None
    assert state.status == "NEEDS_HUMAN"
    assert state.count == 3
    assert state.limit == 3


def test_update_first_blocked_state():
    src = "- [ ] Add retry ceiling logic\n"
    out, state = update_tasks_text(src, "retry ceiling", "network issue", retry_limit=3)
    assert "BLOCKED (Retries: 1/3 - Error: network issue)" in out
    assert state.status == "BLOCKED"


def test_update_increments_blocked_retry_count():
    src = "- [ ] Add retry ceiling logic - BLOCKED (Retries: 1/3 - Error: first fail)\n"
    out, state = update_tasks_text(src, "retry ceiling", "second fail", retry_limit=3)
    assert "BLOCKED (Retries: 2/3 - Error: second fail)" in out
    assert state.count == 2


def test_update_escalates_to_needs_human_at_ceiling():
    src = "- [ ] Add retry ceiling logic - BLOCKED (Retries: 2/3 - Error: second fail)\n"
    out, state = update_tasks_text(src, "retry ceiling", "third fail", retry_limit=3)
    assert "NEEDS_HUMAN (Retries: 3/3 - Error: third fail)" in out
    assert state.status == "NEEDS_HUMAN"


def test_update_task_not_found_raises():
    with pytest.raises(ValueError, match=r"no open \[ \] task matched"):
        update_tasks_text("- [ ] Something else\n", "retry ceiling", "x", retry_limit=3)
