"""Tests for gateway/builder/contract.py."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gateway.builder_contract import (
    ContractError,
    compile_workflow,
    load_contract,
    run_contract,
    validate_contract,
)


class TestValidateContract:
    def test_valid_contract(self):
        errors = validate_contract(
            {
                "goal": "add --no-color flag",
                "criteria": ["output has no color", "exit code is 0"],
                "validation_commands": ["pytest tests/test_cli.py -q"],
            }
        )
        assert errors == []

    def test_missing_goal(self):
        errors = validate_contract({"criteria": ["x"]})
        assert any("goal" in e for e in errors)

    def test_empty_goal(self):
        errors = validate_contract({"goal": "   "})
        assert any("goal" in e for e in errors)

    def test_invalid_criteria_type(self):
        errors = validate_contract({"goal": "x", "criteria": [1, 2]})
        assert any("criteria" in e for e in errors)

    def test_invalid_commands_type(self):
        errors = validate_contract({"goal": "x", "validation_commands": [1]})
        assert any("validation_commands" in e for e in errors)


class TestLoadContract:
    def test_load_json(self, tmp_path: Path):
        p = tmp_path / "contract.json"
        p.write_text(json.dumps({"goal": "x", "criteria": ["y"]}))
        assert load_contract(p)["goal"] == "x"

    def test_load_markdown_block(self, tmp_path: Path):
        p = tmp_path / "contract.md"
        p.write_text(
            "# Plan\n\n## Contract\n```json\n"
            '{"goal": "x", "criteria": ["y"]}\n'
            "```\n"
        )
        assert load_contract(p)["goal"] == "x"

    def test_load_invalid_raises(self, tmp_path: Path):
        p = tmp_path / "bad.md"
        p.write_text("no contract here")
        with pytest.raises(ContractError):
            load_contract(p)


class TestRunContract:
    def test_run_passes_when_criteria_pass(self, tmp_path: Path):
        with patch(
            "gateway.builder_contract.builder_core.check_criteria",
            return_value=[
                {"criterion": "exit 0", "passed": True, "note": "ok"}
            ],
        ):
            result = run_contract(
                {
                    "goal": "x",
                    "criteria": ["exit 0"],
                    "validation_commands": [],
                }
            )
        assert result["valid"] is True
        assert result["passed"] is True
        assert result["workflow"]["entry_step"] == "execute"

    def test_run_fails_when_command_fails(self, tmp_path: Path):
        with patch(
            "gateway.builder_contract.builder_core.check_criteria",
            return_value=[
                {"criterion": "exit 0", "passed": True, "note": "ok"}
            ],
        ):
            result = run_contract(
                {
                    "goal": "x",
                    "criteria": ["exit 0"],
                    "validation_commands": ["false"],
                }
            )
        assert result["passed"] is False
        assert result["command_results"][0]["passed"] is False

    def test_run_executes_step_local_validation_commands(self):
        with patch(
            "gateway.builder_contract.builder_core.check_criteria",
            return_value=[{"criterion": "checks pass", "passed": True, "note": "ok"}],
        ):
            result = run_contract(
                {
                    "goal": "implement then verify",
                    "criteria": ["checks pass"],
                    "steps": [
                        {"id": "implement", "instruction": "implement"},
                        {
                            "id": "verify",
                            "instruction": "verify",
                            "validation_commands": ["false"],
                        },
                    ],
                }
            )

        assert result["passed"] is False
        assert [entry["command"] for entry in result["command_results"]] == ["false"]
        assert result["command_results"][0]["passed"] is False

    def test_run_fails_when_criteria_fail(self, tmp_path: Path):
        with patch(
            "gateway.builder_contract.builder_core.check_criteria",
            return_value=[
                {"criterion": "exit 0", "passed": False, "note": "rc=1"}
            ],
        ):
            result = run_contract(
                {
                    "goal": "x",
                    "criteria": ["exit 0"],
                    "validation_commands": [],
                }
            )
        assert result["passed"] is False


class TestCompileWorkflow:
    def test_legacy_contract_compiles_to_one_explicit_step(self):
        compiled = compile_workflow(
            {"goal": "ship the change", "validation_commands": ["pytest -q"]}
        )

        assert compiled == {
            "entry_step": "execute",
            "inputs": [],
            "steps": [
                {
                    "id": "execute",
                    "instruction": "ship the change",
                    "requires": [],
                    "produces": ["result"],
                    "validation_commands": ["pytest -q"],
                    "on_success": None,
                }
            ],
        }

    def test_multistep_workflow_makes_artifacts_and_control_transfer_explicit(self):
        compiled = compile_workflow(
            {
                "goal": "implement then verify",
                "inputs": ["task_bundle"],
                "steps": [
                    {
                        "id": "implement",
                        "instruction": "make the bounded change",
                        "requires": ["task_bundle"],
                        "produces": ["patch"],
                    },
                    {
                        "id": "verify",
                        "instruction": "validate the patch",
                        "requires": ["patch"],
                        "produces": ["evidence"],
                        "validation_commands": ["pytest tests/test_target.py -q"],
                    },
                ],
            }
        )

        assert compiled["entry_step"] == "implement"
        assert compiled["steps"][0]["on_success"] == "verify"
        assert compiled["steps"][1]["on_success"] is None
        assert compiled["steps"][1]["requires"] == ["patch"]
        assert compiled["steps"][1]["produces"] == ["evidence"]

    def test_unknown_control_transfer_fails_closed(self):
        with pytest.raises(ContractError, match="unknown on_success"):
            compile_workflow(
                {
                    "goal": "x",
                    "steps": [
                        {"id": "one", "instruction": "one", "on_success": "missing"}
                    ],
                }
            )

    def test_duplicate_step_ids_fail_closed(self):
        with pytest.raises(ContractError, match="duplicate step id"):
            compile_workflow(
                {
                    "goal": "x",
                    "steps": [
                        {"id": "same", "instruction": "one"},
                        {"id": "same", "instruction": "two"},
                    ],
                }
            )

    def test_required_artifact_must_exist_before_step_runs(self):
        with pytest.raises(ContractError, match="requires unavailable artifact"):
            compile_workflow(
                {
                    "goal": "x",
                    "steps": [
                        {
                            "id": "one",
                            "instruction": "one",
                            "requires": ["missing"],
                            "produces": ["result"],
                        }
                    ],
                }
            )

    def test_cycles_and_unreachable_steps_fail_closed(self):
        with pytest.raises(ContractError, match="cycle"):
            compile_workflow(
                {
                    "goal": "x",
                    "steps": [
                        {"id": "one", "instruction": "one", "on_success": "two"},
                        {"id": "two", "instruction": "two", "on_success": "one"},
                    ],
                }
            )

        with pytest.raises(ContractError, match="unreachable"):
            compile_workflow(
                {
                    "goal": "x",
                    "steps": [
                        {"id": "one", "instruction": "one", "on_success": None},
                        {"id": "two", "instruction": "two"},
                    ],
                }
            )
