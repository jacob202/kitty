from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from mcp.builder import proof

MISSION = "mission-proof"
TASK = "kb_proof_1"
PACKET = "retry-work"
ATTEMPT = 7
RUNTIME_COMMAND = (
    "KITTY_KPROOF_RUNTIME=1 cd gateway/kitty-chat && "
    "npx playwright test tests/smoke/retry-work.spec.ts"
)
UNIT_COMMAND = "cd gateway/kitty-chat && ./node_modules/.bin/vitest run tests/BuilderSurface.test.tsx"


def _initiative(commands: list[str] | None = None) -> dict:
    return {
        "id": MISSION,
        "manifest_sha256": "m" * 64,
        "manifest": {
            "manifest_version": 1,
            "initiative_id": MISSION,
            "title": "Retry work proof",
            "description": "approved retry work",
            "packets": [
                {
                    "id": PACKET,
                    "title": "Retry this work",
                    "objective": "Make retry truthful",
                    "validation_commands": commands if commands is not None else [UNIT_COMMAND, RUNTIME_COMMAND],
                }
            ],
        },
    }


def _resume(*, state: str = "done", pr: dict | None = None) -> dict:
    return {
        "ok": True,
        "operation": "resume_context",
        "state": state,
        "mission": {"id": MISSION, "manifest_sha256": "m" * 64},
        "artifacts": {
            "design": {"path": "docs/superpowers/specs/design.md", "sha": "d" * 40},
            "plan": {"path": "docs/superpowers/plans/plan.md", "sha": "p" * 40},
        },
        "repository": {"base_sha": "b" * 40, "current_sha": "c" * 40, "branch": "main"},
        "current_work": {
            "packet_id": PACKET,
            "task_id": TASK,
            "attempt_id": ATTEMPT if state == "done" else None,
            "state": state,
        },
        "pr": pr,
        "blocker": None,
        "unknowns": [],
        "next_action": "Inspect the verified result.",
    }


def _status(state: str) -> dict:
    return {
        "ok": True,
        "operation": "work_status",
        "state": state,
        "work": {
            "initiative_id": MISSION,
            "packet_id": PACKET,
            "task_id": TASK,
            "task_state": state,
            "projection": {"next_action": "continue"},
        },
    }


def _work_result(*, review: str | None = "approve", publication: dict | None = None) -> dict:
    review_payload = None if review is None else {"verdict": review, "summary": "reviewed"}
    return {
        "ok": True,
        "operation": "work_result",
        "state": "done",
        "result": {
            "mission_id": MISSION,
            "packet_id": PACKET,
            "task_id": TASK,
            "task_state": "done",
            "complete": True,
            "attempt": {"id": ATTEMPT, "review": review_payload},
            "publication": publication,
            "blocker": None,
        },
    }


def _validation(*, runtime_passed: bool = True, status: str = "passed") -> dict:
    return {
        "attempt_id": ATTEMPT,
        "validation_status": status,
        "commands": [
            {
                "index": 0,
                "command_sha256": hashlib.sha256(UNIT_COMMAND.encode()).hexdigest(),
                "passed": True,
                "exit_code": 0,
                "duration_s": 0.1,
            },
            {
                "index": 1,
                "command_sha256": hashlib.sha256(RUNTIME_COMMAND.encode()).hexdigest(),
                "passed": runtime_passed,
                "exit_code": 0 if runtime_passed else 1,
                "duration_s": 0.2,
            },
        ],
    }


def _install_completed_fakes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    initiative: dict | None = None,
    result: dict | None = None,
    validation: dict | None = None,
    status_sequence: list[str] | None = None,
    publication: dict | None = None,
):
    events: list[tuple] = []
    session_counter = 0
    active: set[int] = set()
    states = iter(status_sequence or ["done"])
    latest_state = "done"

    @asynccontextmanager
    async def fake_open_session(_endpoint: str):
        nonlocal session_counter
        session_counter += 1
        sid = session_counter
        assert not active
        active.add(sid)
        events.append(("open", sid))
        try:
            yield sid
        finally:
            active.remove(sid)
            events.append(("close", sid))

    async def fake_call(session, name: str, arguments: dict | None = None):
        nonlocal latest_state
        args = arguments or {}
        events.append(("call", session, name, args.copy()))
        if name in {"mission_approve", "publication_prepare", "execution_pause", "execution_cancel"}:
            raise AssertionError(f"proof must never call {name}")
        if name == "resume_context":
            state = latest_state
            pr = publication if state == "done" else None
            return _resume(state=state, pr=pr)
        if name == "work_status":
            try:
                latest_state = next(states)
            except StopIteration:
                pass
            return _status(latest_state)
        if name == "execution_start":
            assert args == {"mission_id": MISSION, "free": True, "spend_authorized": False}
            latest_state = "running"
            return {"ok": True, "operation": "execution_start", "state": "launched"}
        if name == "work_result":
            latest_state = "done"
            return result or _work_result(publication=publication)
        if name == "publication_status":
            return {"ok": True, "operation": "publication_status", "publication": publication}
        raise AssertionError(f"unexpected MCP tool call: {name}")

    async def fake_doctor(_config, *, publication_required: bool = False):
        events.append(("doctor", publication_required))
        return {"ok": True, "state": "healthy", "checks": [], "first_failure": None, "next_action": "continue"}

    monkeypatch.setattr(proof, "open_session", fake_open_session)
    monkeypatch.setattr(proof, "call_tool_json", fake_call)
    monkeypatch.setattr(proof, "doctor_report", fake_doctor)
    monkeypatch.setattr(proof, "get_initiative_readonly", lambda *_a, **_k: initiative or _initiative())
    monkeypatch.setattr(proof, "get_attempt_validation_index_readonly", lambda *_a, **_k: validation or _validation())
    monkeypatch.setattr(proof, "_builder_db_path", lambda: tmp_path / "builder.db")
    monkeypatch.setattr(proof, "_repo_head", lambda _root: "v" * 40)
    return events


def _config(tmp_path: Path, *, publication_required: bool = False) -> proof.ProofConfig:
    return proof.ProofConfig(
        mission_id=MISSION,
        endpoint="http://127.0.0.1:8765/mcp",
        repo_root=tmp_path,
        timeout_seconds=1,
        poll_seconds=0.001,
        publication_required=publication_required,
    )


@pytest.mark.asyncio
async def test_proof_starts_only_free_approved_execution_and_never_authorizes(monkeypatch, tmp_path):
    events = _install_completed_fakes(monkeypatch, tmp_path, status_sequence=["queued", "done"])

    receipt = await proof.run_proof(_config(tmp_path))

    assert receipt["verdict"] == "pass"
    starts = [event for event in events if event[:3] == ("call", 1, "execution_start")]
    assert len(starts) == 1
    assert starts[0][3] == {"mission_id": MISSION, "free": True, "spend_authorized": False}
    forbidden = {"mission_approve", "publication_prepare", "execution_pause", "execution_cancel"}
    assert not forbidden & {event[2] for event in events if event[0] == "call"}


@pytest.mark.asyncio
async def test_paused_or_blocked_work_is_incomplete_without_start(monkeypatch, tmp_path):
    events = _install_completed_fakes(monkeypatch, tmp_path, status_sequence=["blocked"])

    receipt = await proof.run_proof(_config(tmp_path))

    assert receipt["verdict"] == "incomplete"
    assert "blocked" in receipt["blocker"].lower()
    assert not any(event[0] == "call" and event[2] == "execution_start" for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("initiative", "result", "validation"),
    [
        (_initiative(commands=[UNIT_COMMAND]), _work_result(), _validation()),
        (_initiative(commands=[RUNTIME_COMMAND, RUNTIME_COMMAND]), _work_result(), _validation()),
        (_initiative(), _work_result(review=None), _validation()),
        (_initiative(), _work_result(review="reject"), _validation()),
        (_initiative(), _work_result(), _validation(runtime_passed=False)),
    ],
)
async def test_missing_rejected_or_failed_required_evidence_never_passes(
    monkeypatch, tmp_path, initiative, result, validation
):
    _install_completed_fakes(
        monkeypatch,
        tmp_path,
        initiative=initiative,
        result=result,
        validation=validation,
    )

    receipt = await proof.run_proof(_config(tmp_path))

    assert receipt["verdict"] != "pass"


@pytest.mark.asyncio
async def test_required_publication_without_pr_is_incomplete_and_never_publishes(monkeypatch, tmp_path):
    events = _install_completed_fakes(monkeypatch, tmp_path, publication=None)

    receipt = await proof.run_proof(_config(tmp_path, publication_required=True))

    assert receipt["verdict"] == "incomplete"
    assert not any(event[0] == "call" and event[2] == "publication_prepare" for event in events)


@pytest.mark.asyncio
async def test_fresh_continuity_uses_distinct_closed_sessions_and_second_calls_only_resume(monkeypatch, tmp_path):
    publication = {"pr_number": 449, "head_sha": "h" * 40}
    events = _install_completed_fakes(monkeypatch, tmp_path, publication=publication)

    receipt = await proof.run_proof(_config(tmp_path))

    assert receipt["verdict"] == "pass"
    assert receipt["continuity"]["session_count"] == 2
    assert receipt["continuity"]["passed"] is True
    assert events.index(("close", 1)) < events.index(("open", 2))
    second_calls = [event for event in events if event[0] == "call" and event[1] == 2]
    assert [(event[2], event[3]) for event in second_calls] == [
        ("resume_context", {"mission_id": MISSION})
    ]


def test_runtime_marker_digest_requires_exactly_one_command():
    command, digest = proof.runtime_marker_identity(_initiative()["manifest"], PACKET)
    assert command == RUNTIME_COMMAND
    assert digest == hashlib.sha256(RUNTIME_COMMAND.encode()).hexdigest()
    with pytest.raises(proof.ProofEvidenceError):
        proof.runtime_marker_identity(_initiative(commands=[UNIT_COMMAND])["manifest"], PACKET)
    with pytest.raises(proof.ProofEvidenceError):
        proof.runtime_marker_identity(
            _initiative(commands=[RUNTIME_COMMAND, RUNTIME_COMMAND])["manifest"], PACKET
        )


def test_proof_cli_forwards_timeout_poll_publication_and_uses_incomplete_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from mcp.builder import operator, operator_cli

    op_config = operator.OperatorConfig(
        root=tmp_path,
        host="127.0.0.1",
        port=8765,
        pid_file=tmp_path / "mcp.pid",
        log_file=tmp_path / "mcp.log",
    )
    monkeypatch.setattr(operator_cli.operator, "load_config", lambda: op_config)
    captured: dict = {}

    async def fake_report(_config, **kwargs):
        captured.update(kwargs)
        return {
            "ok": False,
            "state": "incomplete",
            "verdict": "incomplete",
            "mission_id": MISSION,
            "receipt_path": str(tmp_path / "receipt.json"),
            "next_action": "Resolve the blocker.",
        }

    monkeypatch.setattr(proof, "proof_report", fake_report)

    code = operator_cli.main(
        [
            "proof",
            MISSION,
            "--timeout",
            "12",
            "--poll",
            "0.1",
            "--require-publication",
            "--json",
        ]
    )

    assert code == 2
    assert captured == {
        "mission_id": MISSION,
        "timeout_seconds": 12,
        "poll_seconds": 0.1,
        "publication_required": True,
    }
    assert '"verdict": "incomplete"' in capsys.readouterr().out
