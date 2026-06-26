# tests/test_desktop_launchd.py
"""Unit coverage for the Kitty Desktop launchd generator.

These tests exercise plist rendering and the label allowlist — the parts that
must be correct before any launchctl command touches the machine. They run on
any platform; the launchctl-executing paths are guarded to macOS and are
asserted to refuse to run elsewhere.
"""
import plistlib
from pathlib import Path

import pytest

from scripts import kitty_desktop_launchd as ld

ALL_NAMES = ["litellm", "gateway", "ui"]
SECRET_HINTS = ("SECRET", "TOKEN", "PASSWORD", "API_KEY", "MASTER_KEY", "BEARER")


def test_exactly_three_services_defined():
    assert sorted(ld.SERVICES) == sorted(ALL_NAMES)
    assert sorted(ld.SERVICE_ORDER) == sorted(ALL_NAMES)


@pytest.mark.parametrize("name", ALL_NAMES)
def test_plist_is_valid_and_round_trips(name):
    data = plistlib.loads(ld.render_plist_bytes(name))
    assert data["Label"] == f"com.kitty.desktop.{name}"


@pytest.mark.parametrize("name", ALL_NAMES)
def test_program_paths_are_absolute(name):
    root = Path("/Users/example/Projects/kitty")
    plist = ld.build_plist(name, repo_root=root)
    program = plist["ProgramArguments"]
    assert program[0] == "/bin/bash"
    assert program[1].startswith("/")
    assert program[1].startswith(str(root))
    assert Path(plist["WorkingDirectory"]).is_absolute()
    assert Path(plist["StandardOutPath"]).is_absolute()


@pytest.mark.parametrize("name", ALL_NAMES)
def test_program_points_at_repo_script(name):
    plist = ld.build_plist(name, repo_root=Path("/repo"))
    assert plist["ProgramArguments"][1] == f"/repo/{ld.SERVICES[name].program}"


@pytest.mark.parametrize("name", ALL_NAMES)
def test_has_runatload_keepalive_and_throttle(name):
    plist = ld.build_plist(name)
    assert plist["RunAtLoad"] is True
    assert plist["KeepAlive"] == {"SuccessfulExit": False}
    assert plist["ThrottleInterval"] == ld.THROTTLE_INTERVAL
    assert ld.THROTTLE_INTERVAL >= 1


def test_each_service_has_distinct_log_paths():
    outs, errs = set(), set()
    for name in ALL_NAMES:
        plist = ld.build_plist(name, repo_root=Path("/repo"))
        outs.add(plist["StandardOutPath"])
        errs.add(plist["StandardErrorPath"])
        assert plist["StandardOutPath"] != plist["StandardErrorPath"]
    assert len(outs) == len(ALL_NAMES)
    assert len(errs) == len(ALL_NAMES)


def test_labels_are_unique_and_namespaced():
    labels = {ld.SERVICES[n].label for n in ALL_NAMES}
    assert len(labels) == len(ALL_NAMES)
    assert all(lbl.startswith("com.kitty.desktop.") for lbl in labels)


@pytest.mark.parametrize("name", ALL_NAMES)
def test_plist_contains_no_secret_values(name):
    plist = ld.build_plist(name)
    env = plist["EnvironmentVariables"]
    for key, value in env.items():
        assert not any(h in key.upper() for h in SECRET_HINTS), key
        assert "key-" not in value.lower()
        assert "bearer" not in value.lower()


@pytest.mark.parametrize("name", ALL_NAMES)
def test_services_pinned_to_loopback(name):
    env = ld.build_plist(name)["EnvironmentVariables"]
    for key, value in env.items():
        if key.endswith("_HOST"):
            assert value == "127.0.0.1", f"{key}={value} is not loopback"
        assert "0.0.0.0" not in value
        if value.startswith("http://") or value.startswith("https://"):
            assert "127.0.0.1" in value


def test_plist_path_lives_in_launchagents():
    path = ld.plist_path("gateway")
    assert path.parent.name == "LaunchAgents"
    assert path.name == "com.kitty.desktop.gateway.plist"


def test_install_root_accepts_canonical_checkout(tmp_path):
    root = tmp_path / "kitty"
    root.mkdir()
    (root / ".git").mkdir()

    ld.validate_install_root(root)


def test_install_root_rejects_linked_worktree_without_override(tmp_path):
    root = tmp_path / "kitty-worktree"
    root.mkdir()
    (root / ".git").write_text("gitdir: /tmp/main/.git/worktrees/kitty-worktree\n")

    with pytest.raises(RuntimeError, match="Refusing to install LaunchAgents"):
        ld.validate_install_root(root)


def test_install_root_accepts_linked_worktree_with_explicit_override(tmp_path):
    root = tmp_path / "kitty-worktree"
    root.mkdir()
    (root / ".git").write_text("gitdir: /tmp/main/.git/worktrees/kitty-worktree\n")

    ld.validate_install_root(root, allow_worktree_install=True)


def test_install_cli_rejects_worktree_without_traceback(tmp_path, monkeypatch, capsys):
    root = tmp_path / "kitty-worktree"
    root.mkdir()
    (root / ".git").write_text("gitdir: /tmp/main/.git/worktrees/kitty-worktree\n")
    monkeypatch.setattr(ld, "repo_root_default", lambda: root)

    assert ld.main(["install"]) == 1

    captured = capsys.readouterr()
    assert "Refusing to install LaunchAgents" in captured.err
    assert "Traceback" not in captured.err


def test_resolve_targets_all_is_ordered():
    assert ld.resolve_targets("all") == ld.SERVICE_ORDER


def test_unknown_service_is_rejected():
    with pytest.raises(ValueError):
        ld.resolve_targets("postgres")
    with pytest.raises(ValueError):
        ld._require("../../etc/passwd")


@pytest.mark.skipif(
    __import__("sys").platform == "darwin",
    reason="guard only raises off-macOS",
)
def test_launchctl_commands_refuse_to_run_off_macos():
    # The lifecycle commands must never attempt launchctl on a non-mac host.
    for fn in (ld.bootstrap, ld.bootout, ld.restart):
        with pytest.raises(RuntimeError, match="macOS-only"):
            fn("gateway")
