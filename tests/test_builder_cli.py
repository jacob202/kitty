"""Tests for gateway/builder_cli.py Layer 1A — argparse shape and command dispatch."""

from pathlib import Path
from unittest.mock import patch

import pytest

from gateway.builder_cli import build_parser, main


class TestParser:
    def test_help_is_stable(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])

    def test_contract_validate_requires_path(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["contract", "validate"])


class TestDisabledCommands:
    def test_run_not_enabled(self):
        rc = main(["run", "build a thing"])
        assert rc == 1

    def test_loop_not_enabled(self):
        rc = main(["loop", "build a thing"])
        assert rc == 1

    def test_repl_not_enabled(self):
        rc = main(["repl", "build a thing"])
        assert rc == 1

    def test_delegate_not_enabled(self):
        rc = main(["delegate", "opencode", "say hi"])
        assert rc == 1


class TestCommands:
    def test_brief_command_prints_context(self):
        with patch(
            "gateway.brief.build_worker_brief",
            return_value="worker context",
        ) as mock_brief:
            rc = main(["brief", "implement feature X"])
        assert rc == 0
        mock_brief.assert_called_once_with("implement feature X", {})

    def test_brief_command_with_packet(self, tmp_path: Path):
        p = tmp_path / "packet.json"
        p.write_text('{"objective": "test"}')
        with patch(
            "gateway.brief.build_worker_brief",
            return_value="worker context with packet",
        ) as mock_brief:
            rc = main(["brief", "do thing", "--packet", str(p)])
        assert rc == 0
        mock_brief.assert_called_once_with("do thing", {"objective": "test"})

    def test_contract_validate_command(self, tmp_path: Path):
        p = tmp_path / "contract.json"
        p.write_text('{"goal": "x", "criteria": ["y"]}')
        with patch(
            "gateway.builder_contract.run_contract",
            return_value={"passed": True, "criteria": []},
        ) as mock_run:
            rc = main(["contract", "validate", str(p)])
        assert rc == 0
        mock_run.assert_called_once()
