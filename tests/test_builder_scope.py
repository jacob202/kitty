"""Unit tests for gateway/builder_scope.py — pre-execution scope validation."""

from __future__ import annotations

from gateway.builder_scope import (
    EscalationError,
    ScopeFinding,
    build_scope_escalation_artifact,
    validate_scope,
)


def _packet(**overrides) -> dict:
    base = {
        "objective": "Do the thing.",
        "acceptance_criteria": ["thing is done"],
        "allowed_paths": ["thing.py"],
        "validation_commands": ["test -f thing.py"],
    }
    base.update(overrides)
    return base


def test_complete_packet_has_no_findings():
    assert validate_scope(_packet()) == []


def test_empty_objective_is_incomplete_contract():
    findings = validate_scope(_packet(objective="  "))
    assert any(
        f.category == "incomplete_contract" and f.field == "objective" for f in findings
    )


def test_empty_acceptance_is_incomplete_contract():
    findings = validate_scope(_packet(acceptance_criteria=[]))
    assert any(
        f.category == "incomplete_contract" and f.field == "acceptance_criteria"
        for f in findings
    )


def test_empty_allowed_paths_is_unbounded():
    findings = validate_scope(_packet(allowed_paths=[]))
    assert any(f.category == "unbounded_scope" for f in findings)


def test_absolute_path_is_unbounded():
    findings = validate_scope(_packet(allowed_paths=["/etc/passwd"]))
    assert any(f.category == "unbounded_scope" for f in findings)


def test_parent_escape_is_unbounded():
    findings = validate_scope(_packet(allowed_paths=["../secrets"]))
    assert any(f.category == "unbounded_scope" for f in findings)


def test_protected_zone_requires_architectural_judgment():
    for path in [
        "docs/adr/0020-x.md",
        "docs/architecture/REF.md",
        "docs/knowledge/KNOWLEDGE_MODEL.md",
        "docs/GOVERNANCE.md",
    ]:
        findings = validate_scope(_packet(allowed_paths=[path]))
        assert any(
            f.category == "architectural_judgment_required" for f in findings
        ), path


def test_normal_packet_not_flagged_as_protected():
    findings = validate_scope(_packet(allowed_paths=["gateway/foo.py", "tests/test_foo.py"]))
    assert not any(f.category == "architectural_judgment_required" for f in findings)


def test_escalation_error_carries_artifact():
    findings = validate_scope(_packet(allowed_paths=["docs/adr/0020-x.md"]))
    err = EscalationError(
        findings,
        evidence={"initiative_id": "I", "packet_id": "P", "task_id": "T"},
        artifact=build_scope_escalation_artifact("I", "P", "T", findings),
    )
    assert err.findings == findings
    assert err.artifact["type"] == "scope_escalation"
    assert err.artifact["action"] == "stop_escalate_return_control"
    assert err.artifact["findings"]
