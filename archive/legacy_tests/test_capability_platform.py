from collections import Counter

from src.core.capabilities import (
    all_command_capabilities,
    command_palette_suggestions,
    find_command_capability,
    invocation_stats,
    reset_invocation_stats,
    record_invocation,
)


def test_command_capability_snapshot_supports_lookup_metadata():
    commands = all_command_capabilities()

    assert commands
    assert all(hasattr(command, "status") for command in commands)
    assert all(hasattr(command, "routing_tags") for command in commands)
    assert any(command.command.startswith("/prep") and command.visible_in_help is False for command in commands)


def test_find_command_capability_resolves_leading_token():
    capability = find_command_capability("/brief extra words")

    assert capability is not None
    assert capability.command == "/brief"


def test_find_command_capability_returns_none_for_unknown():
    assert find_command_capability("/definitely-not-real") is None


def test_record_invocation_tracks_valid_outcomes():
    reset_invocation_stats()

    record_invocation("/brief", outcome="suggested")
    record_invocation("/brief", outcome="succeeded")

    assert invocation_stats("/brief") == {"suggested": 1, "succeeded": 1}


def test_record_invocation_rejects_invalid_outcome():
    reset_invocation_stats()

    try:
        record_invocation("/brief", outcome="banana")
    except ValueError as exc:
        assert "outcome must be one of" in str(exc)
    else:
        raise AssertionError("record_invocation should reject invalid outcomes")


def test_reset_invocation_stats_clears_state():
    record_invocation("/brief", outcome="suggested")
    reset_invocation_stats()

    assert invocation_stats() == {}


def test_command_palette_search_records_suggested_counts(monkeypatch):
    import web as web_module

    class DummyOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

    reset_invocation_stats()
    monkeypatch.setattr("src.space_kitty.core_orchestrator.CoreOrchestrator", DummyOrchestrator)

    app, socketio = web_module.create_app()
    client = socketio.test_client(app)

    client.emit("command_palette_search", {"query": "stuck focus"})
    received = client.get_received()

    suggestions = next(event["args"][0] for event in received if event["name"] == "command_suggestions")
    assert any(item["command"].startswith("/stuck") for item in suggestions)

    suggested = Counter()
    for item in suggestions:
        stats = invocation_stats(item["command"])
        if stats:
            suggested[item["command"]] = stats.get("suggested", 0)

    assert suggested
    assert all(count >= 1 for count in suggested.values())


def test_capabilities_endpoint_returns_full_command_inventory(monkeypatch):
    import web as web_module

    class DummyOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("src.space_kitty.core_orchestrator.CoreOrchestrator", DummyOrchestrator)

    app, _ = web_module.create_app()
    client = app.test_client()

    response = client.get("/api/capabilities")

    assert response.status_code == 200
    payload = response.get_json()
    assert "visible" in payload["commands"]
    assert "all" in payload["commands"]
    assert any(item["command"] == "/prep" for item in payload["commands"]["all"])
    assert all(item["visible_in_help"] is True for item in payload["commands"]["visible"])


def test_explain_route_returns_routing_decision(monkeypatch):
    import web as web_module

    class DummyOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

    reset_invocation_stats()
    monkeypatch.setattr("src.space_kitty.core_orchestrator.CoreOrchestrator", DummyOrchestrator)

    app, _ = web_module.create_app()
    client = app.test_client()

    response = client.post("/api/capabilities/explain", json={"message": "I'm stuck on a bug"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["suggested_command"] is not None
    assert payload["tier"] is not None
    assert payload["status"] is not None
    assert "reason" in payload
    assert invocation_stats(payload["suggested_command"])["suggested"] >= 1


def test_explain_route_returns_null_when_no_match(monkeypatch):
    import web as web_module

    class DummyOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("src.space_kitty.core_orchestrator.CoreOrchestrator", DummyOrchestrator)

    app, _ = web_module.create_app()
    client = app.test_client()

    response = client.post("/api/capabilities/explain", json={"message": "zzzz qqqq vvvv"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["suggested_command"] is None
    assert payload["all_suggestions"] == []


def test_command_palette_template_uses_dynamic_search():
    template = open("src/templates/index.html", encoding="utf-8").read()

    assert "socket.emit('command_palette_search'" in template or 'socket.emit("command_palette_search"' in template
    assert "const COMMANDS = [" not in template
