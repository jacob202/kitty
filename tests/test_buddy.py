"""Tests for gateway.buddy — persistent mood state."""
import importlib
import sys
from unittest.mock import patch


def _fresh_buddy(tmp_path):
    """Import buddy with a clean state file path."""
    # Remove cached module so _load() runs fresh
    for key in list(sys.modules.keys()):
        if 'gateway.buddy' in key:
            del sys.modules[key]

    state_file = tmp_path / "kitty" / "buddy_state.json"
    with patch('gateway.paths.DATA_DIR', tmp_path):
        import gateway.buddy as b
        # Patch the state file path directly
        b._STATE_FILE = state_file
        b._state.update({
            "mood": "idle", "energy": 100, "session_turns": 0,
            "total_turns": 0, "last_active_ts": 0.0, "drift_count": 0,
        })
    return b


def test_initial_mood_is_idle(tmp_path):
    b = _fresh_buddy(tmp_path)
    assert b.get_state()["mood"] == "idle"


def test_on_request_start_sets_thinking(tmp_path):
    b = _fresh_buddy(tmp_path)
    b.on_request_start()
    assert b.get_state()["mood"] == "thinking"


def test_on_request_success_increments_turns(tmp_path):
    b = _fresh_buddy(tmp_path)
    b.on_request_start()
    b.on_request_success()
    state = b.get_state()
    assert state["mood"] == "success"
    assert state["session_turns"] == 1
    assert state["total_turns"] == 1


def test_on_request_error_sets_confused_and_drains_energy(tmp_path):
    b = _fresh_buddy(tmp_path)
    b.on_request_error()
    state = b.get_state()
    assert state["mood"] == "confused"
    assert state["energy"] == 95
    assert state["drift_count"] == 1


def test_on_context_fetch_sets_searching(tmp_path):
    b = _fresh_buddy(tmp_path)
    b.on_context_fetch()
    assert b.get_state()["mood"] == "searching"


def test_energy_does_not_go_below_zero(tmp_path):
    b = _fresh_buddy(tmp_path)
    for _ in range(25):
        b.on_request_error()
    assert b.get_state()["energy"] == 0


def test_state_persists_to_file(tmp_path):
    import json
    b = _fresh_buddy(tmp_path)
    b.on_request_success()
    assert b._STATE_FILE.exists()
    saved = json.loads(b._STATE_FILE.read_text())
    assert saved["mood"] == "success"
