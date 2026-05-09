"""Tests for scripts/backup.py — restic backup orchestration."""
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

import scripts.backup as backup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cp(returncode=0, stdout="", stderr=""):
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


# ---------------------------------------------------------------------------
# check_filevault
# ---------------------------------------------------------------------------

def test_check_filevault_returns_true_when_on():
    with patch("subprocess.run", return_value=_cp(stdout="FileVault is On.")):
        assert backup.check_filevault() is True


def test_check_filevault_returns_false_when_off():
    with patch("subprocess.run", return_value=_cp(stdout="FileVault is Off.")):
        assert backup.check_filevault() is False


def test_check_filevault_returns_false_on_subprocess_error():
    with patch("subprocess.run", side_effect=FileNotFoundError("fdesetup missing")):
        assert backup.check_filevault() is False


def test_check_filevault_returns_false_on_os_error():
    with patch("subprocess.run", side_effect=OSError("permission denied")):
        assert backup.check_filevault() is False


# ---------------------------------------------------------------------------
# check_local_drive
# ---------------------------------------------------------------------------

def test_check_local_drive_returns_true_when_mounted(tmp_path):
    assert backup.check_local_drive(mount_path=str(tmp_path)) is True


def test_check_local_drive_returns_false_when_not_mounted():
    assert backup.check_local_drive(mount_path="/Volumes/DoesNotExist_KITTY") is False


def test_check_local_drive_uses_env_var_default(tmp_path):
    with patch.dict(os.environ, {"BACKUP_LOCAL_PATH": str(tmp_path)}):
        assert backup.check_local_drive() is True


def test_check_local_drive_uses_hardcoded_default_when_no_env():
    env = {k: v for k, v in os.environ.items() if k != "BACKUP_LOCAL_PATH"}
    with patch.dict(os.environ, env, clear=True):
        result = backup.check_local_drive()
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# build_restic_env
# ---------------------------------------------------------------------------

def test_build_restic_env_includes_required_keys():
    with patch.dict(os.environ, {
        "RESTIC_PASSWORD": "hunter2",
        "B2_ACCOUNT_ID": "acct123",
        "B2_ACCOUNT_KEY": "key456",
    }):
        env = backup.build_restic_env("b2:kitty-bucket")
    assert env["RESTIC_REPOSITORY"] == "b2:kitty-bucket"
    assert env["RESTIC_PASSWORD"] == "hunter2"
    assert env["B2_ACCOUNT_ID"] == "acct123"
    assert env["B2_ACCOUNT_KEY"] == "key456"


def test_build_restic_env_raises_when_password_missing():
    env = {k: v for k, v in os.environ.items() if k != "RESTIC_PASSWORD"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(EnvironmentError, match="RESTIC_PASSWORD"):
            backup.build_restic_env("/Volumes/KittyBackup/restic-repo")


def test_build_restic_env_does_not_mutate_os_environ():
    original = os.environ.get("RESTIC_REPOSITORY", "__MISSING__")
    with patch.dict(os.environ, {"RESTIC_PASSWORD": "pw"}):
        backup.build_restic_env("test-repo")
    assert os.environ.get("RESTIC_REPOSITORY", "__MISSING__") == original


def test_build_restic_env_omits_b2_keys_when_not_set():
    env = {k: v for k, v in os.environ.items()
           if k not in ("B2_ACCOUNT_ID", "B2_ACCOUNT_KEY")}
    with patch.dict(os.environ, env, clear=True):
        os.environ["RESTIC_PASSWORD"] = "pw"
        result = backup.build_restic_env("some-repo")
    assert "B2_ACCOUNT_ID" not in result
    assert "B2_ACCOUNT_KEY" not in result


# ---------------------------------------------------------------------------
# run_restic_backup
# ---------------------------------------------------------------------------

def test_run_restic_backup_calls_correct_command():
    with patch("subprocess.run", return_value=_cp()) as mock_run:
        backup.run_restic_backup(
            repository="/Volumes/KittyBackup/restic-repo",
            source_path="/tmp/data",
            extra_env={"RESTIC_PASSWORD": "pw"},
        )
    args = mock_run.call_args[0][0]
    assert args[0] == backup.RESTIC_BIN
    assert "backup" in args
    assert "/tmp/data" in args


def test_run_restic_backup_dry_run_calls_snapshots():
    with patch("subprocess.run", return_value=_cp()) as mock_run:
        backup.run_restic_backup(
            repository="/Volumes/KittyBackup/restic-repo",
            source_path="/tmp/data",
            extra_env={"RESTIC_PASSWORD": "pw"},
            dry_run=True,
        )
    args = mock_run.call_args[0][0]
    assert "snapshots" in args
    assert "backup" not in args


def test_run_restic_backup_raises_on_nonzero_exit():
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "restic")):
        with pytest.raises(subprocess.CalledProcessError):
            backup.run_restic_backup(
                repository="b2:bucket",
                source_path="/tmp/data",
                extra_env={"RESTIC_PASSWORD": "pw"},
            )


# ---------------------------------------------------------------------------
# backup_local
# ---------------------------------------------------------------------------

def test_backup_local_skips_when_drive_not_mounted():
    with patch.object(backup, "check_local_drive", return_value=False):
        assert backup.backup_local() is False


def test_backup_local_returns_true_on_success(tmp_path):
    with patch.object(backup, "check_local_drive", return_value=True), \
         patch.dict(os.environ, {"RESTIC_PASSWORD": "pw", "BACKUP_LOCAL_PATH": str(tmp_path)}), \
         patch.object(backup, "run_restic_backup", return_value=_cp()):
        assert backup.backup_local() is True


def test_backup_local_returns_false_on_restic_error(tmp_path):
    with patch.object(backup, "check_local_drive", return_value=True), \
         patch.dict(os.environ, {"RESTIC_PASSWORD": "pw", "BACKUP_LOCAL_PATH": str(tmp_path)}), \
         patch.object(backup, "run_restic_backup",
                      side_effect=subprocess.CalledProcessError(1, "restic")):
        assert backup.backup_local() is False


def test_backup_local_returns_false_on_env_error():
    with patch.object(backup, "check_local_drive", return_value=True), \
         patch.object(backup, "build_restic_env",
                      side_effect=EnvironmentError("RESTIC_PASSWORD is not set")):
        assert backup.backup_local() is False


# ---------------------------------------------------------------------------
# backup_b2
# ---------------------------------------------------------------------------

def test_backup_b2_returns_true_on_success():
    with patch.dict(os.environ, {
        "RESTIC_PASSWORD": "pw",
        "B2_ACCOUNT_ID": "id",
        "B2_ACCOUNT_KEY": "key",
        "BACKUP_B2_BUCKET": "my-bucket",
    }), patch.object(backup, "run_restic_backup", return_value=_cp()):
        assert backup.backup_b2() is True


def test_backup_b2_returns_false_when_credentials_missing():
    env = {k: v for k, v in os.environ.items() if k != "RESTIC_PASSWORD"}
    with patch.dict(os.environ, env, clear=True):
        assert backup.backup_b2() is False


def test_backup_b2_repository_uses_b2_prefix():
    captured = {}

    def capture_repo(repository, source_path, extra_env=None, dry_run=False):
        captured["repo"] = repository
        return _cp()

    with patch.dict(os.environ, {
        "RESTIC_PASSWORD": "pw",
        "B2_ACCOUNT_ID": "id",
        "B2_ACCOUNT_KEY": "key",
        "BACKUP_B2_BUCKET": "kitty-backup",
    }), patch.object(backup, "run_restic_backup", side_effect=capture_repo):
        backup.backup_b2()
    assert captured["repo"].startswith("b2:")


def test_backup_b2_returns_false_on_restic_error():
    with patch.dict(os.environ, {
        "RESTIC_PASSWORD": "pw",
        "BACKUP_B2_BUCKET": "kitty-backup",
    }), patch.object(backup, "run_restic_backup",
                     side_effect=subprocess.CalledProcessError(1, "restic")):
        assert backup.backup_b2() is False


# ---------------------------------------------------------------------------
# preflight_checks
# ---------------------------------------------------------------------------

def test_preflight_checks_returns_empty_when_all_clear():
    with patch.object(backup, "check_filevault", return_value=True), \
         patch("os.path.isfile", return_value=True), \
         patch("os.access", return_value=True), \
         patch.dict(os.environ, {"RESTIC_PASSWORD": "pw"}):
        assert backup.preflight_checks() == []


def test_preflight_checks_warns_filevault_off():
    with patch.object(backup, "check_filevault", return_value=False), \
         patch("os.path.isfile", return_value=True), \
         patch("os.access", return_value=True), \
         patch.dict(os.environ, {"RESTIC_PASSWORD": "pw"}):
        warnings = backup.preflight_checks()
    assert any("FileVault" in w for w in warnings)


def test_preflight_checks_warns_restic_missing():
    with patch.object(backup, "check_filevault", return_value=True), \
         patch("os.path.isfile", return_value=False), \
         patch.dict(os.environ, {"RESTIC_PASSWORD": "pw"}):
        warnings = backup.preflight_checks()
    assert any("restic" in w.lower() for w in warnings)


def test_preflight_checks_warns_password_missing():
    env = {k: v for k, v in os.environ.items() if k != "RESTIC_PASSWORD"}
    with patch.object(backup, "check_filevault", return_value=True), \
         patch("os.path.isfile", return_value=True), \
         patch("os.access", return_value=True), \
         patch.dict(os.environ, env, clear=True):
        warnings = backup.preflight_checks()
    assert any("RESTIC_PASSWORD" in w for w in warnings)


def test_preflight_checks_can_return_multiple_warnings():
    env = {k: v for k, v in os.environ.items() if k != "RESTIC_PASSWORD"}
    with patch.object(backup, "check_filevault", return_value=False), \
         patch("os.path.isfile", return_value=False), \
         patch.dict(os.environ, env, clear=True):
        warnings = backup.preflight_checks()
    assert len(warnings) >= 2


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def test_main_returns_0_when_both_succeed():
    with patch.object(backup, "preflight_checks", return_value=[]), \
         patch.object(backup, "backup_local", return_value=True), \
         patch.object(backup, "backup_b2", return_value=True):
        assert backup.main(argv=[]) == 0


def test_main_returns_1_when_b2_fails():
    with patch.object(backup, "preflight_checks", return_value=[]), \
         patch.object(backup, "backup_local", return_value=True), \
         patch.object(backup, "backup_b2", return_value=False):
        assert backup.main(argv=[]) == 1


def test_main_returns_1_when_local_fails():
    with patch.object(backup, "preflight_checks", return_value=[]), \
         patch.object(backup, "backup_local", return_value=False), \
         patch.object(backup, "backup_b2", return_value=True):
        assert backup.main(argv=[]) == 1


def test_main_local_only_skips_b2():
    with patch.object(backup, "preflight_checks", return_value=[]), \
         patch.object(backup, "backup_local", return_value=True) as mock_local, \
         patch.object(backup, "backup_b2") as mock_b2:
        backup.main(argv=["--local-only"])
    mock_local.assert_called_once()
    mock_b2.assert_not_called()


def test_main_b2_only_skips_local():
    with patch.object(backup, "preflight_checks", return_value=[]), \
         patch.object(backup, "backup_b2", return_value=True) as mock_b2, \
         patch.object(backup, "backup_local") as mock_local:
        backup.main(argv=["--b2-only"])
    mock_b2.assert_called_once()
    mock_local.assert_not_called()


def test_main_dry_run_passes_dry_run_true():
    local_calls = []
    b2_calls = []

    def capture_local(dry_run=False):
        local_calls.append(dry_run)
        return True

    def capture_b2(dry_run=False):
        b2_calls.append(dry_run)
        return True

    with patch.object(backup, "preflight_checks", return_value=[]), \
         patch.object(backup, "backup_local", side_effect=capture_local), \
         patch.object(backup, "backup_b2", side_effect=capture_b2):
        backup.main(argv=["--dry-run"])

    assert all(d is True for d in local_calls)
    assert all(d is True for d in b2_calls)


def test_main_returns_0_when_local_only_succeeds():
    with patch.object(backup, "preflight_checks", return_value=[]), \
         patch.object(backup, "backup_local", return_value=True), \
         patch.object(backup, "backup_b2") as mock_b2:
        code = backup.main(argv=["--local-only"])
    assert code == 0
    mock_b2.assert_not_called()
