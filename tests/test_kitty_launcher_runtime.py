from pathlib import Path

SCRIPT = Path("kitty").read_text()


def test_logs_only_tails_all_service_logs() -> None:
    block = SCRIPT.split("cmd_logs() {", 1)[1].split("}\n", 1)[0]
    assert "tail -F" in block
    assert '"$LOG_DIR/ui.log"' in block
    assert "cmd_up" not in block
    assert "cmd_start" not in block


def test_down_handles_launchd_ui_and_owned_listeners() -> None:
    block = SCRIPT.split("cmd_down() {", 1)[1].split("\n}\n\ncmd_status", 1)[0]
    assert "launchctl bootout" in block
    assert 'for svc in ui gateway litellm' in block
    assert 'stop_owned_listener "UI" "$UI_PORT"' in block
    assert 'stop_owned_listener "Gateway" "$GATEWAY_PORT"' in block
    assert 'stop_owned_listener "LiteLLM" "$LITELLM_PORT"' in block


def test_start_tracks_ui_pid_and_refuses_occupied_ports() -> None:
    assert '"$RUN_DIR/ui.pid"' in SCRIPT
    assert 'assert_port_available "UI" "$UI_PORT"' in SCRIPT
    assert 'assert_port_available "Gateway" "$GATEWAY_PORT"' in SCRIPT
    assert 'assert_port_available "LiteLLM" "$LITELLM_PORT"' in SCRIPT
