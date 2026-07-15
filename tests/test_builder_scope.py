"""Unit tests for gateway/builder_scope.py — pre-execution scope validation.

The rule is authority-based and uniform: a protected path escalates unless the
exact path is explicitly named by the packet contract (objective and/or
acceptance_criteria). No path-specific exceptions.
"""

from __future__ import annotations

from gateway.builder_scope import (
    EscalationError,
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


def test_normal_code_packet_touching_protected_path_escalates():
    # Required scenario 1: a generic implementation packet that unexpectedly
    # includes a protected path (architecture doc) must escalate.
    findings = validate_scope(
        _packet(allowed_paths=["docs/architecture/REF.md"], objective="Add a feature")
    )
    assert any(f.category == "architectural_judgment_required" for f in findings)


def test_unnamed_constitutional_path_escalates():
    # Required scenario 3: an unbounded constitutional change must escalate.
    # The objective references "the constitution" but never names the exact
    # protected path, so bounded authority is absent.
    findings = validate_scope(
        _packet(
            allowed_paths=["docs/constitution.md"],
            objective="Update the constitution to clarify scope",
            acceptance_criteria=["constitution updated"],
        )
    )
    assert any(f.category == "architectural_judgment_required" for f in findings)


def test_unnamed_adr_path_escalates():
    findings = validate_scope(
        _packet(
            allowed_paths=["docs/adr/0020-x.md"],
            objective="Propose a new decision",
            acceptance_criteria=["adr drafted"],
        )
    )
    assert any(f.category == "architectural_judgment_required" for f in findings)


def test_named_protected_architecture_path_proceeds():
    # Required scenario 2: a packet that explicitly names the protected
    # architecture document in its contract may proceed.
    path = "docs/architecture/REFERENCE_ARCHITECTURE.md"
    findings = validate_scope(
        _packet(
            allowed_paths=[path],
            objective=f"Align {path} terminology with the Knowledge Model",
            acceptance_criteria=[f"{path} terminology aligned"],
        )
    )
    assert not any(f.category == "architectural_judgment_required" for f in findings)


def test_named_protected_adr_path_proceeds():
    # The rule is uniform: an ADR path is treated identically to any other
    # protected path — naming it in the contract authorizes it (no hard-zone
    # special case).
    path = "docs/adr/0020-x.md"
    findings = validate_scope(
        _packet(
            allowed_paths=[path],
            objective=f"Ratify {path} for the scoped change",
            acceptance_criteria=[f"{path} ratified"],
        )
    )
    assert not any(f.category == "architectural_judgment_required" for f in findings)


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
