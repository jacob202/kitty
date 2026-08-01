from pathlib import Path

SCRIPT = Path("kitty").read_text()


def test_logs_only_tails_all_service_logs() -> None:
    block = SCRIPT.split("cmd_logs() {", 1)[1].split("}\n", 1)[0]
    assert "tail -F" in block
    assert '"$LOG_DIR/ui.log"' in block
    assert "cmd_up" not in block
    assert "cmd_start" not in block


def test_down_disables_launchd_then_clears_every_port() -> None:
    # d9420f3 replaced per-service stop_owned_listener calls with an
    # unconditional sweep: launchd KeepAlive respawns a killed process before
    # the next start claims the port, so "leave unrelated listeners" left the
    # operator looping forever.
    block = SCRIPT.split("cmd_down() {", 1)[1].split("\n}\n\ncmd_status", 1)[0]
    assert "launchctl bootout" in block
    assert 'for svc in ui gateway litellm' in block
    assert 'for port in "$UI_PORT" "$GATEWAY_PORT" "$LITELLM_PORT"' in block
    assert "kill -KILL" in block
    # launchd must be disabled before the sweep, or KeepAlive refills the port.
    assert block.index("launchctl bootout") < block.index("kill -KILL")


def test_start_tracks_ui_pid_and_refuses_occupied_ports() -> None:
    assert '"$RUN_DIR/ui.pid"' in SCRIPT
    assert 'assert_port_available "UI" "$UI_PORT"' in SCRIPT
    assert 'assert_port_available "Gateway" "$GATEWAY_PORT"' in SCRIPT
    assert 'assert_port_available "LiteLLM" "$LITELLM_PORT"' in SCRIPT
