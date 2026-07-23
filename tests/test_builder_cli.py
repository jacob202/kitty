"""Tests for the KittyBuilder control-plane CLI."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gateway.builder_cli import build_parser, main

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _fake_task(task_id: str = "kb_test0000_abcd", **overrides) -> dict:
    base = {
        "id": task_id,
        "title": "test task",
        "description": None,
        "state": "queued",
        "priority": 0,
        "lease_owner": None,
        "lease_token": None,
        "lease_expires_at": None,
        "claim_version": 0,
        "acceptance_criteria": None,
        "acceptance_criteria_json": None,
        "allowed_paths": None,
        "allowed_paths_json": None,
        "bridge_source": None,
        "bridge_issue": None,
        "bridge_external_id": None,
        "bridge_comment_url": None,
        "workflow_ref": None,
        "workflow_sha": None,
        "repo_path": None,
        "blocked_reason": None,
        "last_error": None,
        "final_report_json": None,
        "archived_at": None,
        "created_at": "2026-07-09 12:00:00.000",
        "updated_at": "2026-07-09 12:00:00.000",
    }
    base.update(overrides)
    return base


_QUEUE_PATCH = "gateway.builder_queue"
_CLI_PATCH = "gateway.builder_cli"  # noqa
_INITIATIVE_PATCH = "gateway.builder_initiative"


# ---------------------------------------------------------------------------
# Existing parser tests
# ---------------------------------------------------------------------------


class TestParser:
    def test_help_is_stable(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])

    def test_help_describes_current_execution_capabilities(self):
        help_text = build_parser().format_help()

        assert "execution control plane" in help_text
        assert "coordination only" not in help_text
        assert "NOT ENABLED" not in help_text

    def test_contract_validate_requires_path(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["contract", "validate"])

    def test_queue_add_requires_title(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["queue", "add"])

    def test_queue_show_requires_id(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["queue", "show"])

    def test_queue_list_accepts_state_filter(self):
        parser = build_parser()
        args = parser.parse_args(["queue", "list", "--state", "queued"])
        assert args.queue_command == "list"
        assert args.state == "queued"

    def test_queue_claim_requires_worker(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["queue", "claim", "some-id"])

    def test_queue_claim_next_requires_worker(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["queue", "claim-next"])

    def test_queue_release_requires_fencing(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["queue", "release", "some-id", "--worker", "w"])


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


class TestExistingCommands:
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


# ---------------------------------------------------------------------------
# Queue — add
# ---------------------------------------------------------------------------


class TestQueueAdd:
    def test_add_basic_task(self):
        with patch(f"{_QUEUE_PATCH}.init_db") as mock_init:
            with patch(f"{_QUEUE_PATCH}.create_task", return_value=_fake_task("kb_1")) as mock_create:
                rc = main(["queue", "add", "my task"])
        assert rc == 0
        mock_init.assert_called_once()
        mock_create.assert_called_once_with(
            "my task",
            description=None,
            acceptance_criteria=None,
            priority=0,
            allowed_paths=None,
        )

    def test_add_with_all_options(self):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.create_task", return_value=_fake_task("kb_2")) as mock_create:
                rc = main([
                    "queue", "add", "full task",
                    "--description", "desc text",
                    "--acceptance", '["c1", "c2"]',
                    "--priority", "5",
                    "--allowed-paths", '["src/", "tests/"]',
                ])
        assert rc == 0
        mock_create.assert_called_once_with(
            "full task",
            description="desc text",
            acceptance_criteria=["c1", "c2"],
            priority=5,
            allowed_paths=["src/", "tests/"],
        )

    def test_add_json_output(self, capsys):
        task = _fake_task("kb_3", title="json task", priority=3)
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.create_task", return_value=task):
                rc = main(["queue", "add", "json task", "--priority", "3", "--json"])
        assert rc == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["id"] == "kb_3"
        assert parsed["title"] == "json task"
        assert parsed["priority"] == 3

    def test_add_invalid_acceptance_returns_error(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            rc = main(["queue", "add", "bad", "--acceptance", "not-json"])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()

    def test_add_invalid_allowed_paths_returns_error(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            rc = main(["queue", "add", "bad", "--allowed-paths", '"string-not-array"'])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()

    def test_add_empty_title_returns_error(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.create_task", side_effect=ValueError("title is required")):
                rc = main(["queue", "add", ""])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()


# ---------------------------------------------------------------------------
# Queue — edit
# ---------------------------------------------------------------------------


class TestQueueEdit:
    def test_edit_title(self):
        task = _fake_task("kb_e1", state="queued")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.edit_task", return_value=task) as mock_edit:
                rc = main(["queue", "edit", "kb_e1", "--title", "new title"])
        assert rc == 0
        mock_edit.assert_called_once_with("kb_e1", title="new title")

    def test_edit_multiple_fields(self):
        task = _fake_task("kb_e2", state="queued")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.edit_task", return_value=task) as mock_edit:
                rc = main([
                    "queue", "edit", "kb_e2",
                    "--title", "t",
                    "--description", "d",
                    "--priority", "42",
                    "--acceptance", '["a","b"]',
                    "--allowed-paths", '["p1"]',
                ])
        assert rc == 0
        mock_edit.assert_called_once_with(
            "kb_e2",
            title="t",
            description="d",
            priority=42,
            acceptance_criteria=["a", "b"],
            allowed_paths=["p1"],
        )

    def test_edit_json_output(self, capsys):
        task = _fake_task("kb_e3", title="edited")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.edit_task", return_value=task):
                rc = main(["queue", "edit", "kb_e3", "--title", "edited", "--json"])
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["title"] == "edited"

    def test_edit_not_queued_returns_error(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.edit_task",
                side_effect=ValueError("only queued tasks can be edited"),
            ):
                rc = main(["queue", "edit", "kb_e4", "--title", "x"])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()

    def test_edit_no_fields_returns_error(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.edit_task",
                side_effect=ValueError("at least one editable field must be provided"),
            ):
                rc = main(["queue", "edit", "kb_e5"])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()

    def test_edit_invalid_acceptance_returns_error(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            rc = main(["queue", "edit", "kb_e6", "--acceptance", "not-json"])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()

    def test_edit_unknown_task_returns_error(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.edit_task",
                side_effect=ValueError("task not found"),
            ):
                rc = main(["queue", "edit", "kb_none", "--title", "x"])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()


# ---------------------------------------------------------------------------
# Queue — list
# ---------------------------------------------------------------------------


class TestQueueList:
    def test_list_empty(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.list_tasks", return_value=[]):
                rc = main(["queue", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "No tasks found" in out

    def test_list_with_state_filter(self):
        fake_tasks = [_fake_task("kb_l1", state="claimed")]
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.list_tasks", return_value=fake_tasks) as mock_list:
                rc = main(["queue", "list", "--state", "claimed"])
        assert rc == 0
        mock_list.assert_called_once_with(state="claimed", include_archived=False)

    def test_list_includes_archived(self):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.list_tasks", return_value=[]) as mock_list:
                rc = main(["queue", "list", "--include-archived"])
        assert rc == 0
        mock_list.assert_called_once_with(state=None, include_archived=True)

    def test_list_json_output(self, capsys):
        tasks = [_fake_task("kb_l2", title="t1"), _fake_task("kb_l3", title="t2")]
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.list_tasks", return_value=tasks):
                rc = main(["queue", "list", "--json"])
        assert rc == 0
        parsed = json.loads(capsys.readouterr().out)
        assert len(parsed) == 2
        assert parsed[0]["id"] == "kb_l2"

    def test_list_human_output(self, capsys):
        tasks = [_fake_task("kb_l4", title="my task", state="queued", priority=5)]
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.list_tasks", return_value=tasks):
                rc = main(["queue", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "kb_l4" in out
        assert "my task" in out


# ---------------------------------------------------------------------------
# Queue — show
# ---------------------------------------------------------------------------


class TestQueueShow:
    def test_show_returns_task(self, capsys):
        task = _fake_task("kb_s1", title="show me", state="queued")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.get_task", return_value=task):
                rc = main(["queue", "show", "kb_s1"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "kb_s1" in out
        assert "show me" in out

    def test_show_json(self, capsys):
        task = _fake_task("kb_s2", title="json show")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.get_task", return_value=task):
                rc = main(["queue", "show", "kb_s2", "--json"])
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["title"] == "json show"

    def test_show_unknown(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.get_task", return_value=None):
                rc = main(["queue", "show", "kb_none"])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "task not found" in err.lower()


# ---------------------------------------------------------------------------
# Queue — claim
# ---------------------------------------------------------------------------


class TestQueueClaim:
    def test_claim_basic(self):
        task = _fake_task("kb_c1", state="claimed", lease_owner="bot", claim_version=1)
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.claim_task", return_value=task) as mock_claim:
                rc = main(["queue", "claim", "kb_c1", "--worker", "bot"])
        assert rc == 0
        mock_claim.assert_called_once_with("kb_c1", "bot", lease_seconds=1800)

    def test_claim_with_lease_seconds(self):
        task = _fake_task("kb_c2", state="claimed")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.claim_task", return_value=task) as mock_claim:
                rc = main(["queue", "claim", "kb_c2", "--worker", "w", "--lease-seconds", "3600"])
        assert rc == 0
        mock_claim.assert_called_once_with("kb_c2", "w", lease_seconds=3600)

    def test_claim_json(self, capsys):
        task = _fake_task("kb_c3", state="claimed", lease_token="tok123")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.claim_task", return_value=task):
                rc = main(["queue", "claim", "kb_c3", "--worker", "w", "--json"])
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["lease_token"] == "tok123"

    def test_claim_conflict(self, capsys):
        from gateway.builder_queue import LeaseConflictError

        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.claim_task",
                side_effect=LeaseConflictError("already claimed"),
            ):
                rc = main(["queue", "claim", "kb_c4", "--worker", "w"])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()


# ---------------------------------------------------------------------------
# Queue — claim-next
# ---------------------------------------------------------------------------


class TestQueueClaimNext:
    def test_claim_next_found(self):
        task = _fake_task("kb_n1", state="claimed", lease_owner="bot")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.claim_next", return_value=task) as mock_cn:
                rc = main(["queue", "claim-next", "--worker", "bot"])
        assert rc == 0
        mock_cn.assert_called_once_with("bot", lease_seconds=1800)

    def test_claim_next_json(self, capsys):
        task = _fake_task("kb_n2", state="claimed")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.claim_next", return_value=task):
                rc = main(["queue", "claim-next", "--worker", "w", "--json"])
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["id"] == "kb_n2"

    def test_claim_next_empty(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.claim_next", return_value=None):
                rc = main(["queue", "claim-next", "--worker", "w"])
        assert rc == 1
        out = capsys.readouterr().out
        assert "No eligible queued tasks" in out

    def test_claim_next_empty_json(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.claim_next", return_value=None):
                rc = main(["queue", "claim-next", "--worker", "w", "--json"])
        assert rc == 1
        out = json.loads(capsys.readouterr().out)
        assert out["task"] is None
        assert "No eligible" in out["message"]


# ---------------------------------------------------------------------------
# Queue — release (worker)
# ---------------------------------------------------------------------------


class TestQueueRelease:
    def test_release_basic(self):
        task = _fake_task("kb_r1", state="queued")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.worker_release_task", return_value=task) as mock_rel:
                rc = main([
                    "queue", "release", "kb_r1",
                    "--worker", "w",
                    "--lease-token", "tok",
                    "--claim-version", "1",
                ])
        assert rc == 0
        mock_rel.assert_called_once_with("kb_r1", "tok", 1)

    def test_release_json(self, capsys):
        task = _fake_task("kb_r2", state="queued")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.worker_release_task", return_value=task):
                rc = main([
                    "queue", "release", "kb_r2",
                    "--worker", "w",
                    "--lease-token", "tok",
                    "--claim-version", "1",
                    "--json",
                ])
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["id"] == "kb_r2"

    def test_release_conflict(self, capsys):
        from gateway.builder_queue import LeaseConflictError

        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.worker_release_task",
                side_effect=LeaseConflictError("stale"),
            ):
                rc = main([
                    "queue", "release", "kb_r3",
                    "--worker", "w",
                    "--lease-token", "bad",
                    "--claim-version", "1",
                ])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()


# ---------------------------------------------------------------------------
# Queue — operator-release
# ---------------------------------------------------------------------------


class TestQueueOperatorRelease:
    def test_operator_release_basic(self):
        task = _fake_task("kb_o1", state="queued")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.operator_release_task", return_value=task) as mock_rel:
                rc = main(["queue", "operator-release", "kb_o1", "--reason", "cleanup"])
        assert rc == 0
        mock_rel.assert_called_once_with("kb_o1", reason="cleanup")

    def test_operator_release_no_reason(self):
        task = _fake_task("kb_o2", state="queued")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.operator_release_task", return_value=task) as mock_rel:
                rc = main(["queue", "operator-release", "kb_o2"])
        assert rc == 0
        mock_rel.assert_called_once_with("kb_o2", reason=None)

    def test_operator_release_json(self, capsys):
        task = _fake_task("kb_o3", state="queued")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.operator_release_task", return_value=task):
                rc = main(["queue", "operator-release", "kb_o3", "--json"])
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["id"] == "kb_o3"

    def test_operator_release_error(self, capsys):
        from gateway.builder_queue import IllegalTransitionError

        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.operator_release_task",
                side_effect=IllegalTransitionError("running tasks must be blocked"),
            ):
                rc = main(["queue", "operator-release", "kb_o4"])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()


# ---------------------------------------------------------------------------
# Queue — transition
# ---------------------------------------------------------------------------


class TestQueueTransition:
    def test_transition_basic(self):
        task = _fake_task("kb_t1", state="running", lease_token="tok")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.worker_transition_task", return_value=task) as mock_tr:
                rc = main([
                    "queue", "transition", "kb_t1", "running",
                    "--lease-token", "tok",
                    "--claim-version", "1",
                ])
        assert rc == 0
        mock_tr.assert_called_once_with("kb_t1", "running", "tok", 1, payload=None)

    def test_transition_with_payload(self):
        task = _fake_task("kb_t2", state="blocked")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.worker_transition_task", return_value=task) as mock_tr:
                rc = main([
                    "queue", "transition", "kb_t2", "blocked",
                    "--lease-token", "tok",
                    "--claim-version", "1",
                    "--payload-json", '{"reason": "test"}',
                ])
        assert rc == 0
        mock_tr.assert_called_once_with(
            "kb_t2", "blocked", "tok", 1, payload={"reason": "test"}
        )

    def test_transition_json(self, capsys):
        task = _fake_task("kb_t3", state="running")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.worker_transition_task", return_value=task):
                rc = main([
                    "queue", "transition", "kb_t3", "running",
                    "--lease-token", "tok",
                    "--claim-version", "1",
                    "--json",
                ])
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["id"] == "kb_t3"

    def test_transition_conflict(self, capsys):
        from gateway.builder_queue import LeaseConflictError

        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.worker_transition_task",
                side_effect=LeaseConflictError("stale"),
            ):
                rc = main([
                    "queue", "transition", "kb_t4", "running",
                    "--lease-token", "bad",
                    "--claim-version", "1",
                ])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()

    def test_transition_invalid_payload_json(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            rc = main([
                "queue", "transition", "kb_t5", "running",
                "--lease-token", "tok",
                "--claim-version", "1",
                "--payload-json", '"not-an-object"',
            ])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()


# ---------------------------------------------------------------------------
# Queue — events
# ---------------------------------------------------------------------------


class TestQueueEvents:
    def test_events_empty(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.list_events", return_value=[]):
                rc = main(["queue", "events", "kb_e1"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "No events" in out

    def test_events_human(self, capsys):
        events = [
            {"id": 1, "task_id": "kb_e2", "type": "created", "payload": None, "created_at": "2026-07-09 12:00:00", "payload_json": None},
            {"id": 2, "task_id": "kb_e2", "type": "claimed", "payload": {"worker": "bot"}, "created_at": "2026-07-09 12:01:00", "payload_json": '{"worker": "bot"}'},
        ]
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.list_events", return_value=events):
                rc = main(["queue", "events", "kb_e2"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "created" in out
        assert "claimed" in out
        assert "worker" in out

    def test_events_json(self, capsys):
        events = [
            {"id": 1, "task_id": "kb_e3", "type": "created", "payload": None, "created_at": "2026-07-09 12:00:00", "payload_json": None},
        ]
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.list_events", return_value=events):
                rc = main(["queue", "events", "kb_e3", "--json"])
        assert rc == 0
        parsed = json.loads(capsys.readouterr().out)
        assert len(parsed) == 1
        assert parsed[0]["type"] == "created"

    def test_events_unknown_task(self, capsys):
        from gateway.builder_queue import TaskNotFoundError

        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.list_events",
                side_effect=TaskNotFoundError("task not found"),
            ):
                rc = main(["queue", "events", "kb_none"])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()


# ---------------------------------------------------------------------------
# Queue — status
# ---------------------------------------------------------------------------


class TestQueueStatus:
    def test_status_human(self, capsys):
        status_data = {
            "per_state": {"queued": 3, "claimed": 1, "running": 2},
            "total": 6,
            "queued": 3,
            "claimed": 1,
            "running": 2,
            "blocked": 0,
            "pr_opened": 0,
            "awaiting_review": 0,
            "done": 0,
            "failed": 0,
            "cancelled": 0,
        }
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.queue_status", return_value=status_data):
                rc = main(["queue", "status"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "queued: 3" in out
        assert "claimed: 1" in out
        assert "running: 2" in out

    def test_status_json(self, capsys):
        status_data = {"per_state": {"queued": 1}, "total": 1, "queued": 1,
                       "claimed": 0, "running": 0, "blocked": 0, "pr_opened": 0,
                       "awaiting_review": 0, "done": 0, "failed": 0, "cancelled": 0}
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.queue_status", return_value=status_data):
                rc = main(["queue", "status", "--json"])
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["total"] == 1


# ---------------------------------------------------------------------------
# Queue — archive
# ---------------------------------------------------------------------------


class TestQueueArchive:
    def test_archive_basic(self):
        result = {"tasks_archived": 2, "task_ids": ["kb_a1", "kb_a2"]}
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.archive_tasks", return_value=result) as mock_arch:
                rc = main(["queue", "archive", "--state", "done", "--older-than", "7"])
        assert rc == 0
        mock_arch.assert_called_once_with("done", older_than_days=7)

    def test_archive_json(self, capsys):
        result = {"tasks_archived": 1, "task_ids": ["kb_a3"]}
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.archive_tasks", return_value=result):
                rc = main(["queue", "archive", "--state", "failed", "--older-than", "1", "--json"])
        assert rc == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["tasks_archived"] == 1
        assert parsed["task_ids"] == ["kb_a3"]

    def test_archive_invalid_state(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.archive_tasks",
                side_effect=ValueError("archive only supports terminal states"),
            ):
                rc = main(["queue", "archive", "--state", "queued", "--older-than", "1"])
        assert rc == 1
        _, err = capsys.readouterr()
        assert "error" in err.lower()


# ---------------------------------------------------------------------------
# Kill switch (KITTY_BUILDER_QUEUE_ENABLED=0)
# ---------------------------------------------------------------------------


class TestKillSwitch:
    _MUTATING_INVOCATIONS = [
        ["queue", "add", "t"],
        ["queue", "edit", "kb_x", "--title", "t"],
        ["queue", "claim", "kb_x", "--worker", "w"],
        ["queue", "claim-next", "--worker", "w"],
        ["queue", "release", "kb_x", "--worker", "w",
         "--lease-token", "tok", "--claim-version", "1"],
        ["queue", "operator-release", "kb_x"],
        ["queue", "transition", "kb_x", "running",
         "--lease-token", "tok", "--claim-version", "1"],
        ["queue", "archive", "--state", "done", "--older-than", "7"],
        ["queue", "attach-report", "kb_x", "--report-json", '{"s": 1}',
         "--operator-reason", "r"],
        ["queue", "attach-pr", "kb_x", "--pr", "5"],
        ["queue", "recover"],
        ["queue", "operator-cancel", "kb_x"],
    ]

    def test_mutating_commands_refused_when_disabled(self, monkeypatch, capsys):
        monkeypatch.setenv("KITTY_BUILDER_QUEUE_ENABLED", "0")
        for argv in self._MUTATING_INVOCATIONS:
            with patch(f"{_QUEUE_PATCH}.init_db") as mock_init:
                rc = main(argv)
            assert rc == 1, f"expected refusal for {argv}"
            err = capsys.readouterr().err
            assert "disabled" in err, f"expected disabled message for {argv}"
            mock_init.assert_not_called()

    def test_read_commands_still_work_when_disabled(self, monkeypatch, capsys):
        monkeypatch.setenv("KITTY_BUILDER_QUEUE_ENABLED", "0")
        with patch(f"{_QUEUE_PATCH}.init_db") as mock_init:
            with patch(f"{_QUEUE_PATCH}.list_tasks", return_value=[]):
                rc = main(["queue", "list"])
        assert rc == 0
        mock_init.assert_called_once()

    def test_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv("KITTY_BUILDER_QUEUE_ENABLED", raising=False)
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.create_task", return_value=_fake_task("kb_ks1")
            ) as mock_create:
                rc = main(["queue", "add", "works"])
        assert rc == 0
        mock_create.assert_called_once()

    def test_explicit_enable(self, monkeypatch):
        monkeypatch.setenv("KITTY_BUILDER_QUEUE_ENABLED", "1")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.create_task", return_value=_fake_task("kb_ks2")
            ):
                rc = main(["queue", "add", "works"])
        assert rc == 0


# ---------------------------------------------------------------------------
# Backup-age warning on queue status
# ---------------------------------------------------------------------------


def _status_data(total: int) -> dict:
    return {
        "per_state": {"queued": total},
        "total": total,
        "queued": total,
        "claimed": 0,
        "running": 0,
        "blocked": 0,
        "pr_opened": 0,
        "awaiting_review": 0,
        "done": 0,
        "failed": 0,
        "cancelled": 0,
    }


class TestBackupAgeWarning:
    def _run_status(self, tmp_path, monkeypatch, total):
        monkeypatch.setattr(
            "gateway.paths.BUILDER_QUEUE_DB", tmp_path / "builder_queue.db"
        )
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.queue_status", return_value=_status_data(total)
            ):
                return main(["queue", "status"])

    def test_no_warning_for_empty_queue(self, tmp_path, monkeypatch, capsys):
        rc = self._run_status(tmp_path, monkeypatch, total=0)
        assert rc == 0
        assert "WARNING" not in capsys.readouterr().err

    def test_warns_when_no_backups_exist(self, tmp_path, monkeypatch, capsys):
        rc = self._run_status(tmp_path, monkeypatch, total=2)
        assert rc == 0
        err = capsys.readouterr().err
        assert "no queue backups" in err
        assert "VACUUM INTO" in err

    def test_warns_when_newest_backup_is_stale(self, tmp_path, monkeypatch, capsys):
        import os as _os
        import time as _time

        backups = tmp_path / "backups"
        backups.mkdir()
        old = backups / "builder_queue_20260101.db"
        old.write_bytes(b"")
        three_days_ago = _time.time() - 3 * 24 * 3600
        _os.utime(old, (three_days_ago, three_days_ago))

        rc = self._run_status(tmp_path, monkeypatch, total=2)
        assert rc == 0
        err = capsys.readouterr().err
        assert "days old" in err

    def test_no_warning_when_backup_is_fresh(self, tmp_path, monkeypatch, capsys):
        backups = tmp_path / "backups"
        backups.mkdir()
        (backups / "builder_queue_20260710.db").write_bytes(b"")

        rc = self._run_status(tmp_path, monkeypatch, total=2)
        assert rc == 0
        assert "WARNING" not in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Phase 1B commands — brief, attach-report, attach-pr, recover, operator-cancel
# ---------------------------------------------------------------------------


class TestQueueBrief:
    def test_brief_renders_for_existing_task(self, capsys):
        task = _fake_task(
            "kb_brief001_aaaa",
            title="brief me",
            acceptance_criteria=["c1"],
            allowed_paths=["gateway/x.py"],
        )
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.get_task", return_value=task):
                with patch(f"{_QUEUE_PATCH}.list_events", return_value=[]):
                    with patch(f"{_QUEUE_PATCH}.get_pr_links", return_value=[]):
                        rc = main(["queue", "brief", "kb_brief001_aaaa"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "brief me" in out
        assert "kittybuilder/kb_brief001_aaaa" in out
        assert "Stop conditions" in out

    def test_brief_json_mode(self, capsys):
        task = _fake_task("kb_brief002_bbbb")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.get_task", return_value=task):
                with patch(f"{_QUEUE_PATCH}.list_events", return_value=[]):
                    with patch(f"{_QUEUE_PATCH}.get_pr_links", return_value=[]):
                        rc = main(["queue", "brief", "kb_brief002_bbbb", "--json"])
        assert rc == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["task_id"] == "kb_brief002_bbbb"
        assert "KittyBuilder task brief" in parsed["brief"]

    def test_brief_unknown_task(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.get_task", return_value=None):
                rc = main(["queue", "brief", "kb_nope"])
        assert rc == 1
        assert "not found" in capsys.readouterr().err


class TestQueueAttachReport:
    def test_worker_mode_dispatch(self):
        task = _fake_task("kb_rep1_aaaa")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.attach_final_report", return_value=task
            ) as mock_attach:
                rc = main([
                    "queue", "attach-report", "kb_rep1_aaaa",
                    "--report-json", '{"summary": "done"}',
                    "--lease-token", "tok", "--claim-version", "1",
                ])
        assert rc == 0
        mock_attach.assert_called_once_with(
            "kb_rep1_aaaa",
            {"summary": "done"},
            lease_token="tok",
            claim_version=1,
            operator_reason=None,
        )

    def test_report_file_mode(self, tmp_path):
        p = tmp_path / "report.json"
        p.write_text('{"summary": "from file"}')
        task = _fake_task("kb_rep2_bbbb")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.attach_final_report", return_value=task
            ) as mock_attach:
                rc = main([
                    "queue", "attach-report", "kb_rep2_bbbb",
                    "--report-file", str(p),
                    "--operator-reason", "post-mortem",
                ])
        assert rc == 0
        assert mock_attach.call_args.args[1] == {"summary": "from file"}

    def test_both_sources_rejected(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            rc = main([
                "queue", "attach-report", "kb_x",
                "--report-json", "{}", "--report-file", "x.json",
            ])
        assert rc == 1
        assert "exactly one" in capsys.readouterr().err

    def test_invalid_json_rejected(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            rc = main([
                "queue", "attach-report", "kb_x", "--report-json", "[1,2]",
            ])
        assert rc == 1
        assert "error" in capsys.readouterr().err


class TestQueueAttachPr:
    def test_dispatch(self):
        link = {"pr_number": 141, "task_id": "kb_pr1_aaaa"}
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.attach_pr", return_value=link) as mock_pr:
                rc = main([
                    "queue", "attach-pr", "kb_pr1_aaaa", "--pr", "141",
                    "--url", "https://x/141", "--head-sha", "abc",
                ])
        assert rc == 0
        mock_pr.assert_called_once_with(
            "kb_pr1_aaaa",
            141,
            pr_url="https://x/141",
            head_sha="abc",
            checks_state=None,
            review_state=None,
        )

    def test_pr_required(self):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with pytest.raises(SystemExit):
                main(["queue", "attach-pr", "kb_x"])


class TestQueueRecover:
    def test_dispatch(self, capsys):
        result = {"claimed_requeued": 2, "running_blocked": 1, "total": 3}
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.recover_expired_leases", return_value=result
            ):
                with patch(
                    f"{_QUEUE_PATCH}.recover_interrupted_runs",
                    return_value={"runs_interrupted": 0, "run_ids": []},
                ):
                    rc = main(["queue", "recover"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Recovered 3" in out
        assert "2 claimed" in out

    def test_json(self, capsys):
        result = {"claimed_requeued": 0, "running_blocked": 0, "total": 0}
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.recover_expired_leases", return_value=result
            ):
                with patch(
                    f"{_QUEUE_PATCH}.recover_interrupted_runs",
                    return_value={"runs_interrupted": 0, "run_ids": []},
                ):
                    rc = main(["queue", "recover", "--json"])
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["total"] == 0

    def test_human_output_surfaces_unverified_live_runs(self, capsys):
        tasks = {"claimed_requeued": 0, "running_blocked": 0, "total": 0}
        runs = {
            "runs_interrupted": 0,
            "run_ids": [],
            "starting_runs_deferred": 0,
            "starting_run_ids": [],
            "runs_unverified": 1,
            "unverified_runs": [
                {"run_id": "run_123", "reason": "process_identity_missing"}
            ],
        }
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.recover_expired_leases", return_value=tasks
            ):
                with patch(
                    f"{_QUEUE_PATCH}.recover_interrupted_runs", return_value=runs
                ):
                    rc = main(["queue", "recover"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "run_123" in out
        assert "process_identity_missing" in out


class TestQueueOperatorCancel:
    def test_dispatch(self):
        task = _fake_task("kb_oc1_aaaa", state="cancelled")
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.transition_task", return_value=task
            ) as mock_tr:
                rc = main([
                    "queue", "operator-cancel", "kb_oc1_aaaa",
                    "--reason", "stale demo",
                ])
        assert rc == 0
        mock_tr.assert_called_once_with(
            "kb_oc1_aaaa",
            "cancelled",
            payload={"operator": True, "reason": "stale demo"},
        )

    def test_illegal_state_reports_error(self, capsys):
        from gateway.builder_queue import IllegalTransitionError

        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                f"{_QUEUE_PATCH}.transition_task",
                side_effect=IllegalTransitionError("no"),
            ):
                rc = main(["queue", "operator-cancel", "kb_oc2_bbbb"])
        assert rc == 1
        assert "error" in capsys.readouterr().err


class TestQueueRunnerCommands:
    def test_run_requires_worker_command(self, capsys):
        with patch(f"{_QUEUE_PATCH}.init_db"):
            rc = main(["queue", "run", "kb_123"])

        assert rc == 1
        assert "provide the worker command after --" in capsys.readouterr().err

    def test_run_dispatches_worker_command_and_metadata(self, capsys):
        run = {
            "id": "run_123",
            "task_id": "kb_123",
            "state": "exited",
            "command": ["true"],
        }
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                "gateway.builder_runner.run_worker", return_value=run
            ) as mock_run:
                rc = main(
                    [
                        "queue",
                        "run",
                        "kb_123",
                        "--worker",
                        "captain",
                        "--model",
                        "model-x",
                        "--provider",
                        "provider-y",
                        "--timeout",
                        "90",
                        "--lease-seconds",
                        "20",
                        "--heartbeat-seconds",
                        "5",
                        "--json",
                        "--",
                        "true",
                    ]
                )

        assert rc == 0
        assert json.loads(capsys.readouterr().out)["id"] == "run_123"
        mock_run.assert_called_once_with(
            "kb_123",
            ["true"],
            worker="captain",
            model="model-x",
            provider="provider-y",
            timeout_seconds=90,
            lease_seconds=20,
            heartbeat_seconds=5,
        )

    def test_runs_dispatches_filters(self, capsys):
        runs = [{"id": "run_123", "task_id": "kb_123", "state": "exited"}]
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.list_runs", return_value=runs) as mock_list:
                rc = main(
                    [
                        "queue",
                        "runs",
                        "--task",
                        "kb_123",
                        "--state",
                        "exited",
                        "--json",
                    ]
                )

        assert rc == 0
        assert json.loads(capsys.readouterr().out) == runs
        mock_list.assert_called_once_with(task_id="kb_123", state="exited")

    def test_show_run_prints_log_tail(self, tmp_path: Path, capsys):
        log_path = tmp_path / "combined.log"
        log_path.write_text("one\ntwo\nthree\n")
        run = {
            "id": "run_with_log",
            "task_id": "kb_123",
            "state": "exited",
            "log_path": str(log_path),
        }
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.get_run", return_value=run):
                rc = main(["queue", "show-run", "run_with_log", "--log-tail", "2"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "two\nthree" in out
        assert "one\n" not in out.split("--- log tail", 1)[-1]

    def test_show_run_missing_log_fails_loud(self, tmp_path: Path, capsys):
        run = {
            "id": "run_missing_log",
            "task_id": "kb_123",
            "state": "failed",
            "log_path": str(tmp_path / "missing.log"),
        }
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(f"{_QUEUE_PATCH}.get_run", return_value=run):
                rc = main(
                    ["queue", "show-run", "run_missing_log", "--log-tail", "10"]
                )

        assert rc == 1
        assert "log file missing" in capsys.readouterr().err

    def test_cancel_run_signal_error_is_operator_readable(self, capsys):
        from gateway.builder_runner import RunnerError

        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                "gateway.builder_runner.request_cancel",
                side_effect=RunnerError("signaling process group 42 failed"),
            ):
                rc = main(["queue", "cancel-run", "run_123"])

        assert rc == 1
        assert "signaling process group 42 failed" in capsys.readouterr().err

    def test_cancel_run_reports_when_signal_was_refused(self, capsys):
        run = {
            "id": "run_123",
            "task_id": "kb_123",
            "state": "cancel_requested",
            "pid": 4242,
            "signal_sent": False,
            "signal_status": "process_identity_mismatch",
        }
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch("gateway.builder_runner.request_cancel", return_value=run):
                rc = main(["queue", "cancel-run", "run_123"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "signal not sent" in out
        assert "process_identity_mismatch" in out

    def test_clean_worktree_dispatch(self, capsys, tmp_path: Path):
        removed = tmp_path / ".worktrees" / "kittybuilder" / "kb_123"
        with patch(f"{_QUEUE_PATCH}.init_db"):
            with patch(
                "gateway.builder_runner.remove_worktree", return_value=removed
            ) as mock_remove:
                rc = main(["queue", "clean-worktree", "kb_123"])

        assert rc == 0
        assert str(removed) in capsys.readouterr().out
        mock_remove.assert_called_once_with("kb_123")


class TestInitiativeFreePreset:
    _RESULT = {
        "outcome": "succeeded",
        "initiative_id": "init-1",
        "packet_id": "p1",
        "task_id": "kb_123",
        "attempts": [],
    }
    _SUMMARY = {
        "outcome": "idle",
        "reason": None,
        "processed": [],
        "succeeded": 0,
        "exhausted": 0,
    }

    def test_run_packet_free_dispatches_adapter_scripts(self):
        with patch(
            "gateway.builder_loop.run_packet", return_value=self._RESULT
        ) as mock_rp:
            rc = main(["initiative", "run-packet", "init-1", "p1", "--free", "--json"])

        assert rc == 0
        kwargs = mock_rp.call_args.kwargs
        assert kwargs["worker_command"][0] == "bash"
        assert kwargs["worker_command"][1].endswith(
            "scripts/kittybuilder_opencode_worker.sh"
        )
        assert kwargs["review_command"][0] == "bash"
        assert kwargs["review_command"][1].endswith(
            "scripts/kittybuilder_opencode_reviewer.sh"
        )
        assert kwargs["worker"] == "opencode-free"

    def test_run_packet_rejects_free_plus_explicit_worker_command(self, capsys):
        rc = main([
            "initiative", "run-packet", "init-1", "p1",
            "--free", "--worker-command", '["true"]',
        ])

        assert rc == 1
        assert "--free" in capsys.readouterr().err

    def test_run_packet_requires_free_or_worker_command(self, capsys):
        rc = main(["initiative", "run-packet", "init-1", "p1"])

        assert rc == 1
        assert "provide --free" in capsys.readouterr().err

    def test_run_packet_free_model_forces_single_ladder_model(self, monkeypatch):
        import os

        monkeypatch.setenv("KITTYBUILDER_MODEL", "sentinel")
        with patch("gateway.builder_loop.run_packet", return_value=self._RESULT):
            rc = main([
                "initiative", "run-packet", "init-1", "p1",
                "--free", "--model", "opencode/mimo-v2.5-free", "--json",
            ])

        assert rc == 0
        assert os.environ["KITTYBUILDER_MODEL"] == "opencode/mimo-v2.5-free"

    def test_initiative_run_free_dispatches_adapter_scripts(self):
        with patch(
            "gateway.builder_run.run_initiative", return_value=self._SUMMARY
        ) as mock_run:
            rc = main(["initiative", "run", "init-1", "--free", "--json"])

        assert rc == 0
        kwargs = mock_run.call_args.kwargs
        assert kwargs["worker_command"][1].endswith(
            "scripts/kittybuilder_opencode_worker.sh"
        )
        assert kwargs["review_command"][1].endswith(
            "scripts/kittybuilder_opencode_reviewer.sh"
        )
        assert kwargs["worker"] == "opencode-free"


# ---------------------------------------------------------------------------
# Initiative — list --needs-attention
# ---------------------------------------------------------------------------


class TestInitiativeListNeedsAttention:
    """Tests for initiative list --needs-attention (CP-08 campaign, packet cp08b-filter)."""

    _FAKE_INITIATIVES = [
        {"id": "init-paused", "title": "paused campaign", "state": "paused",
         "packet_count": 2, "manifest_version": 1, "manifest_sha256": "a",
         "created_at": "2026-07-01", "updated_at": "2026-07-01"},
        {"id": "init-needs-dec", "title": "needs decision", "state": "active",
         "packet_count": 1, "manifest_version": 1, "manifest_sha256": "b",
         "created_at": "2026-07-02", "updated_at": "2026-07-02"},
        {"id": "init-active", "title": "normal active", "state": "active",
         "packet_count": 3, "manifest_version": 1, "manifest_sha256": "c",
         "created_at": "2026-07-03", "updated_at": "2026-07-03"},
        {"id": "init-done", "title": "completed", "state": "completed",
         "packet_count": 0, "manifest_version": 1, "manifest_sha256": "d",
         "created_at": "2026-07-04", "updated_at": "2026-07-04"},
        {"id": "init-failed", "title": "failed", "state": "failed",
         "packet_count": 0, "manifest_version": 1, "manifest_sha256": "e",
         "created_at": "2026-07-05", "updated_at": "2026-07-05"},
    ]

    @staticmethod
    def _status_for(init_id: str, db_path=None) -> dict:
        statuses = {
            "init-paused": {"state": "paused", "stop_class": None},
            "init-needs-dec": {"state": "active", "stop_class": "needs_decision"},
            "init-active": {"state": "active", "stop_class": None},
            "init-done": {"state": "completed", "stop_class": None},
            "init-failed": {"state": "failed", "stop_class": None},
        }
        return statuses[init_id]

    # -- parser-level tests ---------------------------------------------------

    def test_flag_parses(self):
        """The --needs-attention flag is accepted by the parser."""
        parser = build_parser()
        args = parser.parse_args(["initiative", "list", "--needs-attention"])
        assert args.initiative_command == "list"
        assert args.needs_attention is True

    def test_flag_with_json_parses(self):
        """--needs-attention combined with --json is accepted."""
        parser = build_parser()
        args = parser.parse_args(["initiative", "list", "--needs-attention", "--json"])
        assert args.needs_attention is True
        assert args.json is True

    # -- no-filter behaviour unchanged ----------------------------------------

    def test_list_empty_no_flag(self, capsys):
        with patch(f"{_INITIATIVE_PATCH}.init_db"):
            with patch(f"{_INITIATIVE_PATCH}.list_initiatives", return_value=[]):
                rc = main(["initiative", "list"])
        assert rc == 0
        assert "No initiatives found" in capsys.readouterr().out

    def test_list_human_no_flag(self, capsys):
        with patch(f"{_INITIATIVE_PATCH}.init_db"):
            with patch(
                f"{_INITIATIVE_PATCH}.list_initiatives",
                return_value=self._FAKE_INITIATIVES,
            ):
                rc = main(["initiative", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        for item in self._FAKE_INITIATIVES:
            assert item["id"] in out

    # -- needs-attention human mode -------------------------------------------

    def test_filters_to_paused_and_needs_decision(self, capsys):
        with patch(f"{_INITIATIVE_PATCH}.init_db"):
            with patch(
                f"{_INITIATIVE_PATCH}.list_initiatives",
                return_value=self._FAKE_INITIATIVES,
            ):
                with patch(
                    f"{_INITIATIVE_PATCH}.initiative_status",
                    side_effect=self._status_for,
                ):
                    rc = main(["initiative", "list", "--needs-attention"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "init-paused" in out
        assert "init-needs-dec" in out
        assert "init-active" not in out
        assert "init-done" not in out
        assert "init-failed" not in out

    def test_nothing_needs_attention(self, capsys):
        """When --needs-attention is active but no initiative matches."""
        initiatives = self._FAKE_INITIATIVES
        # All initiatives are active or completed — none needs attention.
        all_boring = {
            "init-paused": {"state": "active", "stop_class": None},
            "init-needs-dec": {"state": "completed", "stop_class": None},
            "init-active": {"state": "active", "stop_class": None},
            "init-done": {"state": "completed", "stop_class": None},
            "init-failed": {"state": "active", "stop_class": None},
        }
        with patch(f"{_INITIATIVE_PATCH}.init_db"):
            with patch(
                f"{_INITIATIVE_PATCH}.list_initiatives", return_value=initiatives
            ):
                with patch(
                    f"{_INITIATIVE_PATCH}.initiative_status",
                    side_effect=lambda i, **kw: all_boring[i],
                ):
                    rc = main(["initiative", "list", "--needs-attention"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "nothing needs attention" in out.lower()

    def test_empty_initiative_list(self, capsys):
        """--needs-attention with no initiatives at all."""
        with patch(f"{_INITIATIVE_PATCH}.init_db"):
            with patch(
                f"{_INITIATIVE_PATCH}.list_initiatives", return_value=[]
            ):
                rc = main(["initiative", "list", "--needs-attention"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "nothing needs attention" in out.lower()

    # -- needs-attention json mode --------------------------------------------

    def test_json_filtered(self, capsys):
        with patch(f"{_INITIATIVE_PATCH}.init_db"):
            with patch(
                f"{_INITIATIVE_PATCH}.list_initiatives",
                return_value=self._FAKE_INITIATIVES,
            ):
                with patch(
                    f"{_INITIATIVE_PATCH}.initiative_status",
                    side_effect=self._status_for,
                ):
                    rc = main([
                        "initiative", "list", "--needs-attention", "--json",
                    ])
        assert rc == 0
        parsed = json.loads(capsys.readouterr().out)
        assert len(parsed) == 2
        ids = {p["id"] for p in parsed}
        assert "init-paused" in ids
        assert "init-needs-dec" in ids

    def test_json_empty(self, capsys):
        """--needs-attention --json with no matches returns []."""
        initiatives = [self._FAKE_INITIATIVES[2]]  # only init-active
        boring_status = {
            "init-active": {"state": "active", "stop_class": None},
        }
        with patch(f"{_INITIATIVE_PATCH}.init_db"):
            with patch(
                f"{_INITIATIVE_PATCH}.list_initiatives", return_value=initiatives
            ):
                with patch(
                    f"{_INITIATIVE_PATCH}.initiative_status",
                    side_effect=lambda i, **kw: boring_status[i],
                ):
                    rc = main([
                        "initiative", "list", "--needs-attention", "--json",
                    ])
        assert rc == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed == []

    def test_json_empty_no_initiatives(self, capsys):
        """--needs-attention --json with zero initiatives returns []."""
        with patch(f"{_INITIATIVE_PATCH}.init_db"):
            with patch(
                f"{_INITIATIVE_PATCH}.list_initiatives", return_value=[]
            ):
                rc = main([
                    "initiative", "list", "--needs-attention", "--json",
                ])
        assert rc == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed == []
