from __future__ import annotations

from pathlib import Path

from gateway import builder_contract_gate as gate


def test_empty_contract_is_true_noop(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        gate,
        "_changed_paths",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("git should not run")),
    )

    result = gate.evaluate_contract_checks(tmp_path, base_sha="0" * 40)

    assert result == {
        "passed": True,
        "changed_paths": [],
        "forbidden_symbols_found": [],
        "required_symbols_missing": [],
        "forbidden_paths_changed": [],
    }


def test_required_symbol_and_forbidden_path_are_mechanical(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(gate, "_changed_paths", lambda *_args, **_kwargs: ["gateway/legacy/x.py"])
    monkeypatch.setattr(gate, "_changed_text", lambda *_args, **_kwargs: "other_marker")

    result = gate.evaluate_contract_checks(
        tmp_path,
        base_sha="0" * 40,
        required_symbols=["SAFE_MARKER"],
        forbidden_paths=["gateway/legacy"],
    )

    assert result["passed"] is False
    assert result["required_symbols_missing"] == ["SAFE_MARKER"]
    assert result["forbidden_paths_changed"] == ["gateway/legacy/x.py"]


def test_changed_text_fails_closed_when_changed_file_cannot_be_read(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "unreadable.py"
    target.write_text("SAFE_MARKER\n", encoding="utf-8")
    monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: (_ for _ in ()).throw(OSError("boom")))

    try:
        gate._changed_text(tmp_path, ["unreadable.py"])
    except gate.ContractGateError as exc:
        assert "unreadable.py" in str(exc)
    else:
        raise AssertionError("unreadable changed file must fail closed")


def test_changed_paths_consumes_shared_snapshot(monkeypatch, tmp_path: Path) -> None:
    class Snapshot:
        changed_paths = ("old/path.py", "new/path.py")

    calls = []
    monkeypatch.setattr(
        gate,
        "snapshot_existing_worktree",
        lambda worktree, *, base_commit, include_ignored: calls.append(
            (worktree, base_commit, include_ignored)
        ) or Snapshot(),
    )

    assert gate._changed_paths(tmp_path, "a" * 40) == ["old/path.py", "new/path.py"]
    assert calls == [(tmp_path, "a" * 40, False)]


def _git(repo: Path, *args: str) -> str:
    import subprocess

    result = subprocess.run(
        ["/usr/bin/git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def test_forbidden_path_detects_untracked_worker_write(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "base.txt").write_text("base\n", encoding="utf-8")
    _git(tmp_path, "add", "base.txt")
    _git(tmp_path, "commit", "-m", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "forbidden.txt").write_text("worker mutation\n", encoding="utf-8")

    result = gate.evaluate_contract_checks(
        tmp_path, base_sha=base, forbidden_paths=["forbidden.txt"]
    )

    assert result["passed"] is False
    assert result["forbidden_paths_changed"] == ["forbidden.txt"]
