from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def monitor_env(tmp_path, monkeypatch):
    import gateway.automation_actions as actions
    import gateway.web_monitor as wm
    from gateway import action_grants, automation_runs, signal_store

    kitty_db = tmp_path / "kitty.db"
    monkeypatch.setattr(automation_runs, "DB_FILE", kitty_db)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", kitty_db)
    monkeypatch.setattr(signal_store, "SIGNALS_DB_FILE", kitty_db)
    monkeypatch.setattr(wm, "MONITOR_DB", tmp_path / "web_monitors.db")
    actions.clear_registry()
    yield kitty_db
    actions.clear_registry()


@pytest.mark.asyncio
async def test_first_check_of_an_already_matching_watch_does_not_notify(monitor_env):
    """RC-09: the first-ever check has no baseline to transition from,
    so it must never notify — same guard non-keyword watches already had via
    `old_hash != ""`. keyword_matches still reports the match for visibility."""
    import gateway.web_monitor as wm

    wid = wm.add_watch("https://example.com/item", keywords=["sansui"])
    response = AsyncMock()
    response.status_code = 200
    response.text = "Sansui AU-7900 available"

    with patch("httpx.AsyncClient.get", return_value=response):
        first = await wm._check_watch(next(w for w in wm.list_watches() if w["id"] == wid))
        second = await wm._check_watch(next(w for w in wm.list_watches() if w["id"] == wid))

    assert first["changed"] is False
    assert first["keyword_matches"] == ["sansui"]
    assert second["changed"] is False
    assert second["keyword_matches"] == ["sansui"]


@pytest.mark.asyncio
async def test_keyword_match_notifies_once_per_transition_not_on_every_poll(monitor_env):
    """RC-09: _check_watch used bare hash-difference to decide
    `changed` even for keyword watches, so a page whose surrounding content
    keeps churning (ads, timestamps) while the keyword stays matched fired a
    fresh notification on every single poll instead of once per transition."""
    import gateway.web_monitor as wm

    wid = wm.add_watch("https://example.com/item", keywords=["sansui"])

    def watch():
        return next(w for w in wm.list_watches() if w["id"] == wid)

    response = AsyncMock()
    response.status_code = 200

    response.text = "nothing interesting here"
    with patch("httpx.AsyncClient.get", return_value=response):
        baseline = await wm._check_watch(watch())
    assert baseline["changed"] is False
    assert "keyword_matches" not in baseline

    response.text = "Sansui AU-7900 available (v1)"
    with patch("httpx.AsyncClient.get", return_value=response):
        transition = await wm._check_watch(watch())
    assert transition["changed"] is True
    assert transition["keyword_matches"] == ["sansui"]

    # Content keeps changing (a timestamp, an ad slot) but the keyword is
    # still present — this must not re-fire.
    for revision in ("Sansui AU-7900 available (v2)", "Sansui AU-7900 available (v3)"):
        response.text = revision
        with patch("httpx.AsyncClient.get", return_value=response):
            still_matched = await wm._check_watch(watch())
        assert still_matched["changed"] is False
        assert still_matched["keyword_matches"] == ["sansui"]

    # Losing the match and then regaining it is a genuine new transition.
    response.text = "sold out"
    with patch("httpx.AsyncClient.get", return_value=response):
        unmatched = await wm._check_watch(watch())
    assert unmatched["changed"] is False
    assert "keyword_matches" not in unmatched

    response.text = "Sansui AU-7900 available again"
    with patch("httpx.AsyncClient.get", return_value=response):
        re_matched = await wm._check_watch(watch())
    assert re_matched["changed"] is True
    assert re_matched["keyword_matches"] == ["sansui"]


@pytest.mark.asyncio
async def test_source_failure_records_watch_evidence(monitor_env):
    import gateway.web_monitor as wm
    from gateway import automation_runs

    watch = {"id": "watch-1", "label": "item", "url": "https://bad", "keywords": []}
    result = {"status": "error", "error": "dns unavailable", "changed": False}

    await wm._handle_watch_result(watch, result)

    runs = automation_runs.list_runs(automation_id="web_monitor:watch-1")
    assert len(runs) == 1
    assert runs[0]["status"] == "source_unavailable"
    assert "dns unavailable" in runs[0]["error"]


@pytest.mark.asyncio
async def test_match_emits_signal_then_uses_shared_signal_action(monitor_env, monkeypatch):
    import gateway.automation_actions as actions
    import gateway.web_monitor as wm

    calls: list[dict] = []

    async def fake_run_action(name, **kwargs):
        calls.append({"name": name, **kwargs})
        return {"status": "completed"}

    monkeypatch.setattr(actions, "run_action", fake_run_action)
    watch = {
        "id": "watch-2",
        "label": "Sansui",
        "url": "https://example.com/item",
        "keywords": ["sansui"],
    }
    result = {"changed": True, "keyword_matches": ["sansui"], "hash": "abc123"}

    await wm._handle_watch_result(watch, result)

    assert len(calls) == 1
    call = calls[0]
    assert call["name"] == "web_monitor.notify"
    assert call["trigger_kind"] == "signal"
    assert call["automation_id"] == "web_monitor:watch-2"
    assert call["trigger_ref"].isdigit()
    assert call["payload"]["watch_id"] == "watch-2"


@pytest.mark.asyncio
async def test_no_match_records_condition_false_without_notification(monitor_env, monkeypatch):
    import gateway.automation_actions as actions
    import gateway.web_monitor as wm
    from gateway import automation_runs

    calls: list[str] = []
    monkeypatch.setattr(actions, "run_action", lambda *args, **kwargs: calls.append("run"))
    watch = {"id": "watch-3", "label": "item", "url": "https://example.com", "keywords": ["x"]}
    await wm._handle_watch_result(watch, {"changed": False, "keyword_matches": []})

    assert calls == []
    runs = automation_runs.list_runs(automation_id="web_monitor:watch-3")
    assert runs[0]["status"] == "condition_false"


def test_disabling_watch_stops_future_checks_without_deleting_run_history(monitor_env, monkeypatch):
    import gateway.web_monitor as wm
    from gateway import automation_runs

    watch_id = wm.add_watch("https://example.com/item", label="item", interval_minutes=1)
    run = automation_runs.begin_run(
        automation_id=f"web_monitor:{watch_id}",
        action="web_monitor.notify",
        trigger_kind="monitor",
        trigger_ref=watch_id,
    )
    automation_runs.finish_run(run["id"], status="condition_false")

    assert wm.set_watch_enabled(watch_id, False) is False
    stored = next(w for w in wm.list_watches() if w["id"] == watch_id)
    assert stored["enabled"] is False

    checked: list[str] = []

    async def should_not_check(watch):
        checked.append(watch["id"])
        return {"changed": False}

    monkeypatch.setattr(wm, "_check_watch", should_not_check)
    result = __import__("asyncio").run(wm.check_due())

    assert result == {"checked": 0, "changed": 0, "failed": 0}
    assert checked == []
    history = automation_runs.list_runs(automation_id=f"web_monitor:{watch_id}")
    assert [item["id"] for item in history] == [run["id"]]

    assert wm.set_watch_enabled(watch_id, True) is True
    assert wm.set_watch_enabled("missing", False) is None
