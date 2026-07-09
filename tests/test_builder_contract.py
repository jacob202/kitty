"""Tests for gateway/builder/contract.py."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gateway.builder_contract import (
    ContractError,
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
