from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import kitty_reliability_gate as gate


def test_gate_uses_fixed_fault_scenarios_only(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def run(command, **kwargs):
        seen.append(list(command))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(gate.subprocess, "run", run)
    monkeypatch.setattr(gate, "_git_head", lambda: "c" * 40)

    receipt = gate.run_gate(2)

    assert receipt["all_passed"] is True
    assert receipt["repetitions"] == 2
    assert tuple(receipt["scenario_ids"]) == gate.FIXED_SCENARIOS
    assert len(seen) == 2
    for command in seen:
        assert command[:3] == [gate.sys.executable, "-m", "pytest"]
        assert command[3 : 3 + len(gate.FIXED_SCENARIOS)] == list(gate.FIXED_SCENARIOS)


def test_gate_returns_failure_when_any_repetition_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    outcomes = iter([0, 1, 0])
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=next(outcomes)),
    )
    monkeypatch.setattr(gate, "_git_head", lambda: "d" * 40)

    receipt = gate.run_gate(3)

    assert receipt["all_passed"] is False
    assert receipt["passed_repetitions"] == 2


def test_repetition_count_is_bounded() -> None:
    assert gate._bounded_repetitions("1") == 1
    assert gate._bounded_repetitions("20") == 20
    with pytest.raises(Exception, match="between 1 and 20"):
        gate._bounded_repetitions("0")
    with pytest.raises(Exception, match="between 1 and 20"):
        gate._bounded_repetitions("21")


def test_json_receipt_is_written_atomically(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "receipt.json"
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(gate, "_git_head", lambda: "e" * 40)

    receipt = gate.run_gate(2, json_out=target)

    assert json.loads(target.read_text(encoding="utf-8")) == receipt
    assert list(tmp_path.glob("*.tmp")) == []


def test_cli_has_no_arbitrary_command_or_scenario_option() -> None:
    parser = gate.build_parser()
    options = {
        option
        for action in parser._actions  # noqa: SLF001 - parser contract inspection
        for option in action.option_strings
    }
    assert "--command" not in options
    assert "--scenario" not in options


def test_timed_out_repetition_becomes_failed_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(*args, **kwargs):
        raise gate.subprocess.TimeoutExpired(cmd=args[0], timeout=gate.RUN_TIMEOUT_SECONDS)

    monkeypatch.setattr(gate.subprocess, "run", timeout)
    monkeypatch.setattr(gate, "_git_head", lambda: "f" * 40)

    receipt = gate.run_gate(1)

    assert receipt["all_passed"] is False
    assert receipt["runs"][0]["exit_code"] == 124
    assert "timed out" in receipt["runs"][0]["stderr_tail"]


def test_head_movement_during_gate_invalidates_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    heads = iter(["a" * 40, "b" * 40])
    monkeypatch.setattr(gate, "_git_head", lambda: next(heads))
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    receipt = gate.run_gate(1)

    assert receipt["head_sha"] == "a" * 40
    assert receipt["end_head_sha"] == "b" * 40
    assert receipt["head_unchanged"] is False
    assert receipt["all_passed"] is False
