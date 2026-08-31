from __future__ import annotations

import json
from pathlib import Path

from gateway import builder_initiative as bi
from scripts import packet_preflight as pp


def _packet(*, packet_id: str = "shared-id", objective: str = "Update the existing module", routing=...):
    policy: dict[str, object] = {"max_attempts": 2, "priority": 10}
    if routing is not ...:
        policy["routing"] = routing
    return {
        "id": packet_id,
        "title": "Focused packet",
        "objective": objective,
        "depends_on": [],
        "acceptance_criteria": ["The existing behavior is corrected"],
        "allowed_paths": ["gateway/existing.py", "tests"],
        "policy": policy,
        "validation_commands": ["python -m pytest -q tests/test_packet_preflight.py"],
    }


def _manifest(initiative_id: str, packets: list[dict]) -> dict:
    return {
        "manifest_version": 1,
        "initiative_id": initiative_id,
        "title": initiative_id,
        "description": "focused test manifest",
        "packets": packets,
    }


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _errors(findings: list[pp.Finding]) -> list[str]:
    return [f.message for f in findings if f.level == "ERROR"]


def test_same_packet_id_is_allowed_in_different_initiatives(tmp_path: Path) -> None:
    tracked = {"gateway/existing.py", "tests/test_packet_preflight.py"}
    seen: dict[str, str] = {}
    first = _write(tmp_path / "first.json", _manifest("initiative-one", [_packet()]))
    second = _write(tmp_path / "second.json", _manifest("initiative-two", [_packet()]))

    first_errors = _errors(pp.check_manifest(first, tracked=tracked, seen_ids=seen))
    second_errors = _errors(pp.check_manifest(second, tracked=tracked, seen_ids=seen))

    assert not any("packet id already used" in error for error in first_errors + second_errors)


def test_duplicate_packet_id_is_rejected_within_one_initiative(tmp_path: Path) -> None:
    payload = _manifest("initiative-one", [_packet(), _packet()])
    path = _write(tmp_path / "duplicate.json", payload)

    assert any("duplicate packet id" in error for error in bi.validate_manifest(payload))
    errors = _errors(
        pp.check_manifest(
            path,
            tracked={"gateway/existing.py", "tests/test_packet_preflight.py"},
            seen_ids={},
        )
    )
    assert any("duplicate packet id" in error for error in errors)


def test_free_routing_shapes_match_builder_validator() -> None:
    for routing in (..., {}, None):
        packet = _packet(routing=routing)
        payload = _manifest("routing-ok", [packet])
        assert bi.validate_manifest(payload) == []
        assert not any("policy.routing" in error for error in _errors(
            pp.check_packet(
                packet,
                tracked={"gateway/existing.py", "tests/test_packet_preflight.py"},
                seen_ids={},
                manifest_name="routing-ok.json",
                initiative_id="routing-ok",
            )
        ))

    invalid = _packet(routing={"model": None, "provider": None})
    assert any("policy.routing.model" in error for error in bi.validate_manifest(_manifest("routing-bad", [invalid])))
    assert any("policy.routing has empty value" in error for error in _errors(
        pp.check_packet(
            invalid,
            tracked={"gateway/existing.py", "tests/test_packet_preflight.py"},
            seen_ids={},
            manifest_name="routing-bad.json",
            initiative_id="routing-bad",
        )
    ))


def test_pinned_python_validation_command_is_rejected() -> None:
    packet = _packet()
    packet["validation_commands"] = ["python3.12 -m pytest -q tests/test_packet_preflight.py"]

    errors = _errors(
        pp.check_packet(
            packet,
            tracked={"gateway/existing.py", "tests/test_packet_preflight.py"},
            seen_ids={},
            manifest_name="python.json",
            initiative_id="python",
        )
    )

    assert any("pins an interpreter version" in error for error in errors)


def test_edit_only_packet_does_not_require_directory_but_creation_packet_does() -> None:
    tracked = {"gateway/existing.py", "tests/test_packet_preflight.py"}
    edit_findings = pp.check_packet(
        _packet(objective="Update the existing module to show clearer status"),
        tracked=tracked,
        seen_ids={},
        manifest_name="edit.json",
        initiative_id="edit",
    )
    assert not any(f.level == "ERROR" and "cannot create any new file" in f.message for f in edit_findings)

    create_findings = pp.check_packet(
        _packet(objective="Add a new helper for clearer status"),
        tracked=tracked,
        seen_ids={},
        manifest_name="create.json",
        initiative_id="create",
    )
    assert any(f.level == "ERROR" and "cannot create any new file" in f.message for f in create_findings)
