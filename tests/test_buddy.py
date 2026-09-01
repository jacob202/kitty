"""Tests for gateway.buddy — persistent mood state."""
import sys
from unittest.mock import patch


def _fresh_buddy(tmp_path):
    """Import buddy with a clean in-memory state (buddy_store I/O patched out).

    The fresh import temporarily replaces `gateway.buddy` in sys.modules; the
    original module object is restored before returning. Otherwise the freshly
    imported module leaks into the registry and breaks modules that bound
    gateway.buddy at import time (e.g. routes.completions), whose monkeypatch
    (e.g. test_library_chat_001 `buddy.on_request_error`) then misses.
    """
    saved = {}
    for key in list(sys.modules.keys()):
        if key == 'gateway.buddy' or key.startswith('gateway.buddy.'):
            saved[key] = sys.modules.pop(key)

    with patch('gateway.paths.DATA_DIR', tmp_path), \
         patch('gateway.buddy_store.get_state', return_value={
             "mood": "idle", "energy": 100, "session_turns": 0,
             "total_turns": 0, "last_active_ts": 0.0, "drift_count": 0,
         }), \
         patch('gateway.buddy_store.save_state'):
        import gateway.buddy as b
        b._state.update({
            "mood": "idle", "energy": 100, "session_turns": 0,
            "total_turns": 0, "last_active_ts": 0.0, "drift_count": 0,
        })

    sys.modules.update(saved)

    import gateway as _gateway
    for key, mod in saved.items():
        if key.startswith("gateway.buddy"):
            attr = key.rsplit(".", 1)[-1]
            if getattr(_gateway, attr, None) is not mod:
                setattr(_gateway, attr, mod)

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


def test_state_persists_via_store():
    import gateway.buddy as b
    import gateway.buddy_store as store
    b._state.update({
        "mood": "idle", "energy": 100, "session_turns": 0,
        "total_turns": 0, "last_active_ts": 0.0, "drift_count": 0,
    })
    with patch.object(store, 'save_state') as mock_save:
        b.on_request_success()
    mock_save.assert_called_once()
    saved_state = mock_save.call_args[0][0]
    assert saved_state["mood"] == "success"
