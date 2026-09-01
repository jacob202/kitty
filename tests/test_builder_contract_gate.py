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
