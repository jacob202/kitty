import os
import subprocess
from pathlib import Path

SCRIPT = Path("kitty").read_text()
GATEWAY_START = Path("gateway/start_gateway.sh").read_text()
UI_START = Path("scripts/desktop/start_ui.sh").read_text()


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


def test_start_fails_when_the_ui_bootstrap_fails() -> None:
    block = SCRIPT.split("cmd_start() {", 1)[1].split("\n}\n\ncmd_down", 1)[0]
    assert "if ! cmd_ui; then" in block
    assert "return 1" in block
    assert block.index("if ! cmd_ui; then") < block.index('open "http://127.0.0.1:$UI_PORT"')


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


def test_status_uses_the_serving_listener_before_pidfile_metadata() -> None:
    block = SCRIPT.split("cmd_status() {", 1)[1].split("\n}\n\ncmd_", 1)[0]
    listener_lookup = 'found_pid="$(listener_pids "$port" | head -1)"'
    pidfile_lookup = 'if pid_alive "$pidfile"; then'
    assert listener_lookup in block
    assert pidfile_lookup in block
    assert block.index(listener_lookup) < block.index(pidfile_lookup)


def _run_pidfile_controls_listener(tmp_path: Path, controller_command: str) -> subprocess.CompletedProcess:
    pidfile = tmp_path / "litellm.pid"
    pidfile.write_text("123\n", encoding="utf-8")
    helper = _extract_function("pidfile_controls_listener")
    shell = (
        'KITTY_ROOT=/repo\n'
        'pid_owned_by_current_checkout() { [[ "$1" == "123" ]]; }\n'
        'pid_parent() { printf "123\n"; }\n'
        f'pid_command() {{ printf "%s\n" {controller_command!r}; }}\n'
        + helper
        + '\npidfile_controls_listener litellm "$1" 456\n'
    )
    return subprocess.run(
        ["bash", "-c", shell, "bash", str(pidfile)],
        capture_output=True,
        text=True,
    )


def test_pidfile_controls_listener_accepts_expected_litellm_controller(tmp_path) -> None:
    result = _run_pidfile_controls_listener(tmp_path, "bash /repo/gateway/start_litellm.sh")
    assert result.returncode == 0, result.stderr


def test_pidfile_controls_listener_rejects_reused_pid_with_wrong_command(tmp_path) -> None:
    result = _run_pidfile_controls_listener(tmp_path, "bash /repo/scripts/unrelated.sh")
    assert result.returncode != 0


def test_status_uses_service_aware_role_for_both_listener_sections() -> None:
    block = SCRIPT.split("cmd_status() {", 1)[1].split("\n}\n\ncmd_", 1)[0]
    assert 'listener_role_for_service "$svc" "$pidfile" "$found_pid"' in block
    assert 'listener_role_for_service "$svc" "$RUN_DIR/$svc.pid" "$pid"' in block
    assert 'pidfile_controls_listener "$svc" "$pidfile" "$found_pid"' in block


def test_primary_stack_classifier_distinguishes_coherent_split_partial_and_stopped() -> None:
    marker = "classify_primary_stack() {"
    assert marker in SCRIPT
    body = SCRIPT.split(marker, 1)[1].split("\n}\n", 1)[0]
    function = marker + body + "\n}\n"

    def classify(ui_identity: str, gateway_identity: str) -> str:
        result = subprocess.run(
            ["bash", "-c", function + '\nclassify_primary_stack "$1" "$2"', "bash", ui_identity, gateway_identity],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    assert classify("/tmp/wt@abc", "/tmp/wt@abc") == "coherent"
    assert classify("/tmp/ui@abc", "/tmp/gw@def") == "split"
    assert classify("/tmp/wt@abc", "") == "partial"
    assert classify("", "") == "stopped"


def test_status_exposes_other_kitty_listeners_without_calling_them_stale() -> None:
    block = SCRIPT.split("cmd_status() {", 1)[1].split("\n}\n\ncmd_", 1)[0]
    assert "Other Kitty listeners" in block
    assert "all_listener_pid_ports" in SCRIPT
    assert "pid_owned_by_kitty" in block
    assert "stale runtime" not in block.lower()


def test_status_consumes_the_doctor_runtime_provenance_probe() -> None:
    block = SCRIPT.split("cmd_status() {", 1)[1].split("\n}\n\ncmd_", 1)[0]
    assert "runtime_provenance_status_line" in block
    assert "check_ui_freshness" not in block
    assert 'gateway/kitty-chat/.next/BUILD_ID' not in block


def test_status_runtime_probe_falls_back_when_worktree_venv_is_missing() -> None:
    block = SCRIPT.split("cmd_status() {", 1)[1].split("\n}\n\ncmd_", 1)[0]
    assert 'runtime_python="$PYTHON_BIN"' in block
    assert "command -v python3" in block
    assert '"$runtime_python" -c' in block


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
    block = SCRIPT.split("startup_identity() {", 1)[1].split("\n}\n\ncmd_up", 1)[0]
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


def test_room_command_uses_global_agent_room_cli() -> None:
    assert "cmd_room() {" in SCRIPT
    block = SCRIPT.split("cmd_room() {", 1)[1].split("\n}\n", 1)[0]
    assert "-m gateway.agent_room_cli" in block
    assert "ensure_agent_room_data_root" in block
    assert "ensure_runtime_builder_data_dir" not in block
    assert 'room)      shift; cmd_room "$@" ;;' in SCRIPT
    assert "kitty room" in SCRIPT


def test_agent_command_uses_shared_coordination_cli() -> None:
    assert "cmd_agent() {" in SCRIPT
    block = SCRIPT.split("cmd_agent() {", 1)[1].split("\n}\n", 1)[0]
    assert "-m gateway.agent_coordination_cli" in block
    assert "ensure_runtime_builder_data_dir" not in block
    assert 'agent)     shift; cmd_agent "$@" ;;' in SCRIPT
    assert "kitty agent" in SCRIPT


def test_runtime_start_pins_builder_state_to_canonical_checkout() -> None:
    assert "ensure_runtime_builder_data_dir() {" in SCRIPT
    resolver = _extract_function("selected_data_root")
    helper = _extract_function("ensure_runtime_builder_data_dir")
    assert "--git-common-dir" in resolver
    assert 'data_root="$(selected_data_root)"' in helper
    assert "KITTY_BUILDER_DATA_DIR" in helper
    assert "KITTY_DATA_ROOT" in helper

    up_block = SCRIPT.split("cmd_up() {", 1)[1].split("\n}\n\n", 1)[0]
    assert "ensure_runtime_builder_data_dir" in up_block
    assert up_block.index("ensure_runtime_builder_data_dir") < up_block.index("# LiteLLM")

    run_fg_block = SCRIPT.split("cmd_run_fg() {", 1)[1].split("\n}\n\n", 1)[0]
    assert "ensure_runtime_builder_data_dir" in run_fg_block


ROOT = Path(__file__).resolve().parents[1]


def test_workspace_resolution_checked_before_gateway_secret_is_written() -> None:
    # ensure_gateway_secret mutates .env. If workspace resolution ran after it,
    # a conflicting override or a missing personal data root would write a
    # secret into .env before Kitty refuses to start — a partial mutation on
    # the way to a fail-loud error. Both entry points must check first.
    up_block = SCRIPT.split("cmd_up() {", 1)[1].split("\n}\n\n", 1)[0]
    assert up_block.index("ensure_runtime_builder_data_dir") < up_block.index("ensure_gateway_secret")
    assert up_block.index("require_existing_personal_workspace") < up_block.index("ensure_gateway_secret")

    run_fg_block = SCRIPT.split("cmd_run_fg() {", 1)[1].split("\n}\n\n", 1)[0]
    assert run_fg_block.index("ensure_runtime_builder_data_dir") < run_fg_block.index("ensure_gateway_secret")
    assert run_fg_block.index("require_existing_personal_workspace") < run_fg_block.index("ensure_gateway_secret")


def _extract_function(name: str) -> str:
    marker = f"{name}() {{"
    start = SCRIPT.index(marker)
    body = SCRIPT[start:]
    close = body.index("\n}\n")
    return body[: close + 3]


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _run_workspace_resolver(
    tmp_path: Path, env_overrides: dict, git_common_dir: str | None
) -> subprocess.CompletedProcess:
    """Source the two workspace-resolution functions standalone and run them.

    Proves selection/conflict/missing-state behavior without starting any
    real Kitty process (no ports, no .env writes, no servers).
    """
    functions = "\n".join(
        [
            _extract_function("expand_user_path"),
            _extract_function("normalize_user_path"),
            _extract_function("selected_data_root"),
            _extract_function("ensure_runtime_builder_data_dir"),
            _extract_function("require_existing_personal_workspace"),
        ]
    )
    script = tmp_path / "probe.sh"
    script.write_text(
        "#!/usr/bin/env bash\nset -uo pipefail\n"
        + functions
        + "\nensure_runtime_builder_data_dir || exit 1\n"
        + "require_existing_personal_workspace || exit 2\n"
        + 'printf "%s\\n%s\\n%s\\n" "$KITTY_DATA_ROOT" "$KITTY_BUILDER_DATA_DIR" "$KITTY_COMPUTE_GOVERNOR_DB"\n',
        encoding="utf-8",
    )
    script.chmod(0o755)

    env = dict(os.environ)
    for key in ("KITTY_DATA_ROOT", "KITTY_BUILDER_DATA_DIR", "KITTY_COMPUTE_GOVERNOR_DB"):
        env.pop(key, None)
    env.update(env_overrides)
    env["KITTY_ROOT"] = str(tmp_path)

    if git_common_dir is not None:
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir(exist_ok=True)
        _write_executable(
            fake_bin / "git", f"#!/usr/bin/env python3\nprint({git_common_dir!r})\n"
        )
        env["PATH"] = f"{fake_bin}:{env['PATH']}"

    return subprocess.run(
        ["bash", str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        env=env,
    )


def test_workspace_resolver_selects_canonical_root_from_secondary_worktree(tmp_path):
    # Requirement 1: invoking from a secondary worktree still selects the
    # canonical personal root, not the invoking checkout's own root.
    canonical = tmp_path / "canonical-workspace"
    (canonical / "data" / "kitty").mkdir(parents=True)
    (canonical / "data" / "kitty" / "kitty.db").touch()

    result = _run_workspace_resolver(tmp_path, {}, git_common_dir=str(canonical / ".git"))

    assert result.returncode == 0, result.stderr
    data_root, builder_dir, governor_db = result.stdout.splitlines()
    # Requirement 3: app data, Builder, and compute-governor paths are one
    # coherent decision — all three derive from the same selected root.
    assert data_root == str(canonical / "data")
    assert builder_dir == str(canonical / "data" / "kittybuilder")
    assert governor_db == str(canonical / "data" / "compute_governor" / "receipts.db")


def test_workspace_resolver_honors_explicit_data_root_override(tmp_path):
    # Requirement 2: explicit KITTY_DATA_ROOT wins even when canonical
    # derivation would land somewhere else entirely.
    isolated = tmp_path / "isolated-data"
    isolated.mkdir()
    unrelated_canonical = tmp_path / "unrelated-canonical"

    result = _run_workspace_resolver(
        tmp_path,
        {"KITTY_DATA_ROOT": str(isolated)},
        git_common_dir=str(unrelated_canonical / ".git"),
    )

    assert result.returncode == 0, result.stderr
    data_root, builder_dir, governor_db = result.stdout.splitlines()
    assert data_root == str(isolated)
    assert builder_dir == str(isolated / "kittybuilder")
    assert governor_db == str(isolated / "compute_governor" / "receipts.db")


def test_workspace_resolver_normalizes_relative_data_root_before_export(tmp_path):
    selected = tmp_path / "relative-store"
    selected.mkdir()

    result = _run_workspace_resolver(
        tmp_path,
        {
            "KITTY_DATA_ROOT": "relative-store",
            "KITTY_BUILDER_DATA_DIR": "relative-store/kittybuilder",
            "KITTY_COMPUTE_GOVERNOR_DB": "relative-store/compute_governor/receipts.db",
        },
        git_common_dir=None,
    )

    assert result.returncode == 0, result.stderr
    data_root, builder_dir, governor_db = result.stdout.splitlines()
    assert data_root == str(selected)
    assert builder_dir == str(selected / "kittybuilder")
    assert governor_db == str(selected / "compute_governor" / "receipts.db")


def test_workspace_resolver_rejects_conflicting_builder_override(tmp_path):
    # Requirement 4: a Builder root that contradicts the selected data root
    # is refused rather than silently splitting state.
    isolated = tmp_path / "isolated-data"
    isolated.mkdir()
    wrong_builder_dir = tmp_path / "somewhere-else" / "kittybuilder"

    result = _run_workspace_resolver(
        tmp_path,
        {
            "KITTY_DATA_ROOT": str(isolated),
            "KITTY_BUILDER_DATA_DIR": str(wrong_builder_dir),
        },
        git_common_dir=None,
    )

    assert result.returncode == 1
    assert "conflicts with the selected personal data root" in result.stderr
    assert "KITTY_BUILDER_DATA_DIR" in result.stderr


def test_workspace_resolver_rejects_conflicting_governor_override(tmp_path):
    isolated = tmp_path / "isolated-data"
    isolated.mkdir()
    wrong_governor_db = tmp_path / "somewhere-else" / "receipts.db"

    result = _run_workspace_resolver(
        tmp_path,
        {
            "KITTY_DATA_ROOT": str(isolated),
            "KITTY_COMPUTE_GOVERNOR_DB": str(wrong_governor_db),
        },
        git_common_dir=None,
    )

    assert result.returncode == 1
    assert "conflicts with the selected personal data root" in result.stderr
    assert "KITTY_COMPUTE_GOVERNOR_DB" in result.stderr


def test_workspace_resolver_fails_loud_when_personal_data_root_is_missing(tmp_path):
    # Requirement 6: missing expected personal state fails visibly instead of
    # silently initializing a fresh empty workspace.
    missing = tmp_path / "does-not-exist"

    result = _run_workspace_resolver(
        tmp_path, {"KITTY_DATA_ROOT": str(missing)}, git_common_dir=None
    )

    assert result.returncode == 2
    assert "does not exist" in result.stderr
    assert "will not silently start a fresh empty workspace" in result.stderr


def test_kitty_up_refuses_to_start_when_personal_data_root_is_missing(tmp_path):
    # End-to-end proof at the real command entry point: ./kitty up must fail
    # before ever writing GATEWAY_SECRET into .env or touching a port.
    missing_data_root = tmp_path / "missing-personal-data"

    env = dict(os.environ)
    for key in ("KITTY_BUILDER_DATA_DIR", "KITTY_COMPUTE_GOVERNOR_DB"):
        env.pop(key, None)
    env["KITTY_DATA_ROOT"] = str(missing_data_root)
    env["HOME"] = str(tmp_path)

    result = subprocess.run(
        [str(ROOT / "kitty"), "up"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert "does not exist" in result.stderr
    assert "will not silently start a fresh empty workspace" in result.stderr


def test_workspace_resolver_rejects_implicit_empty_tracked_data_dir(tmp_path):
    canonical = tmp_path / "empty-clone"
    (canonical / "data").mkdir(parents=True)
    (canonical / "data" / ".gitkeep").write_text("", encoding="utf-8")

    result = _run_workspace_resolver(tmp_path, {}, git_common_dir=str(canonical / ".git"))

    assert result.returncode == 2
    assert "no established Kitty state" in result.stderr


def test_workspace_resolver_rejects_implicit_ancillary_state_without_personal_db(tmp_path):
    canonical = tmp_path / "ancillary-only"
    queue = canonical / "data" / "kittybuilder" / "builder_queue.db"
    queue.parent.mkdir(parents=True)
    queue.touch()
    governor = canonical / "data" / "compute_governor" / "receipts.db"
    governor.parent.mkdir(parents=True)
    governor.touch()

    result = _run_workspace_resolver(tmp_path, {}, git_common_dir=str(canonical / ".git"))

    assert result.returncode == 2
    assert "kitty/kitty.db is missing" in result.stderr


def test_workspace_resolver_allows_explicit_empty_first_run_and_expands_tilde(tmp_path):
    home = tmp_path / "home"
    data_root = home / "kitty-data"
    data_root.mkdir(parents=True)

    result = _run_workspace_resolver(
        tmp_path,
        {"HOME": str(home), "KITTY_DATA_ROOT": "~/kitty-data"},
        git_common_dir=None,
    )

    assert result.returncode == 0, result.stderr
    data, builder, governor = result.stdout.splitlines()
    assert data == str(data_root)
    assert builder == str(data_root / "kittybuilder")
    assert governor == str(data_root / "compute_governor" / "receipts.db")


def test_runtime_identity_uses_process_worktree_startup_record_not_mutable_head() -> None:
    body = _extract_function("pid_worktree_identity")
    assert 'identity_file="$process_root/logs/.run/$svc.identity"' in body
    assert "rev-parse HEAD" not in body
    assert "gateway.identity" in GATEWAY_START
    assert "ui.identity" in UI_START
    assert '"$$" "${ROOT_DIR}" "${source_sha}"' in GATEWAY_START
    assert '"$$" "${ROOT_DIR}" "${source_sha}"' in UI_START


def test_runtime_identity_reads_only_the_requested_service_record() -> None:
    # A stale identity file from another service must never answer for this PID:
    # after an unclean shutdown a recycled PID would otherwise report provenance
    # for a process that never wrote that record.
    body = _extract_function("pid_worktree_identity")
    assert "for svc in ui gateway litellm" not in body
    assert 'local pid="$1" svc="$2"' in body
    block = SCRIPT.split("cmd_status() {", 1)[1].split("\n}\n\ncmd_", 1)[0]
    assert 'pid_worktree_identity "$ui_pid" ui' in block
    assert 'pid_worktree_identity "$gateway_pid" gateway' in block


def test_status_current_identity_uses_dirty_aware_runtime_source() -> None:
    block = SCRIPT.split("cmd_status() {", 1)[1].split("\n}\n\ncmd_", 1)[0]
    assert 'current_source_sha="$(runtime_source_sha || echo "$sha")"' in block
    assert 'current_identity="$KITTY_ROOT@$current_source_sha"' in block


def test_status_normalizes_workspace_overrides_before_conflict_reporting() -> None:
    block = SCRIPT.split("cmd_status() {", 1)[1].split("\n}\n\ncmd_", 1)[0]
    assert 'ws_builder_override="$(normalize_user_path "$KITTY_BUILDER_DATA_DIR")"' in block
    assert 'ws_governor_override="$(normalize_user_path "$KITTY_COMPUTE_GOVERNOR_DB")"' in block
