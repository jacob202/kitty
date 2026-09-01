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


def test_changed_paths_disables_rename_detection(monkeypatch, tmp_path: Path) -> None:
    calls = []
    monkeypatch.setattr(gate, "_git", lambda _wt, *args: calls.append(args) or "old/path.py\nnew/path.py\n")

    assert gate._changed_paths(tmp_path, "a" * 40) == ["old/path.py", "new/path.py"]
    assert calls == [("diff", "--no-renames", "--name-only", f"{'a' * 40}..HEAD")]
