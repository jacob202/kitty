import os
import subprocess
from pathlib import Path

SCRIPT = Path("kitty").read_text()


def test_logs_only_tails_all_service_logs() -> None:
    block = SCRIPT.split("cmd_logs() {", 1)[1].split("}\n", 1)[0]
    assert "tail -F" in block
    assert '"$LOG_DIR/ui.log"' in block
    assert "cmd_up" not in block
    assert "cmd_start" not in block


def test_down_disables_launchd_then_stops_only_current_checkout_listeners() -> None:
    block = SCRIPT.split("cmd_down() {", 1)[1].split("\n}\n\ncmd_status", 1)[0]
    assert "launchctl bootout" in block
    assert 'for svc in ui gateway litellm' in block
    assert 'launch_pid="$(launchd_pid "$svc" || true)"' in block
    assert 'pid_owned_by_current_checkout "$launch_pid"' in block
    assert 'for port in "$UI_PORT" "$GATEWAY_PORT" "$LITELLM_PORT"' in block
    assert 'if pid_owned_by_current_checkout "$pid"; then' in block
    assert "leaving unrelated listener" in block
    assert "kill -KILL" in block
    # launchd is disabled first, then only listeners proven to belong to this
    # checkout may be killed. Other worktrees and external processes survive.
    assert block.index("launchctl bootout") < block.index('pid_owned_by_current_checkout "$pid"')
    assert block.index('pid_owned_by_current_checkout "$pid"') < block.index("kill -KILL")


def test_start_tracks_ui_pid_and_refuses_occupied_ports() -> None:
    assert '"$RUN_DIR/ui.pid"' in SCRIPT
    assert 'assert_port_available "UI" "$UI_PORT"' in SCRIPT
    assert 'assert_port_available "Gateway" "$GATEWAY_PORT"' in SCRIPT
    assert 'assert_port_available "LiteLLM" "$LITELLM_PORT"' in SCRIPT


def test_stop_owned_listener_removed() -> None:
    # d9420f3 moved cmd_down to an unconditional port sweep, leaving
    # stop_owned_listener defined but never called. Delete the dead function
    # rather than carry it (project rule: no dead code). Its ownership helpers
    # (pid_owned_by_kitty, listener_pids) are still used by assert_port_available
    # and cmd_status, so those must survive.
    assert SCRIPT.count("stop_owned_listener") == 0
    assert "pid_owned_by_kitty" in SCRIPT
    assert "listener_pids" in SCRIPT
    assert "assert_port_available" in SCRIPT


def test_status_reports_authority_build_and_ownership_truth() -> None:
    block = SCRIPT.split("cmd_status() {", 1)[1].split("\n}\n\ncmd_", 1)[0]
    assert "source sha" in block
    assert "--short HEAD" not in block
    assert "origin/main" in block
    assert "authority" in block
    assert "dirty" in block
    assert "build source" in block
    assert "role=" in block
    assert "owned-current" in SCRIPT
    assert "owned-other-worktree" in SCRIPT
    assert "external" in SCRIPT


def test_status_reports_machine_supervisor_mode() -> None:
    block = SCRIPT.split("cmd_status() {", 1)[1].split("\n}\n\ncmd_", 1)[0]
    assert "supervisor" in block
    assert "com.kitty.desktop" in SCRIPT
    assert "manual" in block
    assert "launchd" in block


def test_ui_paths_share_the_canonical_start_ui_bootstrap() -> None:
    ui_block = SCRIPT.split("cmd_ui() {", 1)[1].split("\n}\n\ncmd_start", 1)[0]
    home_block = SCRIPT.split("cmd_verify_home() {", 1)[1].split("\n}\n\ncmd_help", 1)[0]
    assert 'scripts/desktop/start_ui.sh' in ui_block
    assert "next dev" not in ui_block
    assert "next dev" not in home_block
    assert "cmd_ui" in home_block


def test_startup_identity_uses_exact_source_sha() -> None:
    block = SCRIPT.split("startup_identity() {", 1)[1].split("\n}\n\ncheck_ui_freshness", 1)[0]
    assert "rev-parse HEAD" in block
    assert "--short HEAD" not in block


def test_status_distinguishes_configured_but_stopped_launchd(tmp_path) -> None:
    launch_agents = tmp_path / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True)
    (launch_agents / "com.kitty.desktop.gateway.plist").write_text("plist\n")

    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    result = subprocess.run(
        [str(Path(__file__).resolve().parents[1] / "kitty"), "status"],
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )

    assert result.returncode == 0
    assert "supervisor   launchd-configured-stopped (com.kitty.desktop.*)" in result.stdout


def test_sweep_command_uses_the_same_deadline_orchestration_as_the_route() -> None:
    block = SCRIPT.split("cmd_sweep() {", 1)[1].split("}\n", 1)[0]
    assert "from gateway.routes.deadlines import post_sweep" in block
    assert "report = post_sweep()" in block
    assert "gateway.deadline_sweep" not in block
