"""Unit tests for gateway/builder_scope.py — pre-execution scope validation."""

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


def test_forbidden_changes_requires_a_list_of_paths():
    findings = validate_scope(_packet(forbidden_changes="gateway/secrets.py"))
    assert any(
        f.category == "incomplete_contract" and f.field == "forbidden_changes"
        for f in findings
    )


def test_forbidden_changes_rejects_unsafe_paths():
    findings = validate_scope(_packet(forbidden_changes=["../secrets", "./"]))
    assert any(
        f.category == "incomplete_contract" and f.field == "forbidden_changes"
        for f in findings
    )


def test_forbidden_changes_rejects_overlapping_allowed_scope():
    findings = validate_scope(
        _packet(
            allowed_paths=["gateway/"],
            forbidden_changes=["gateway/secrets.py"],
        )
    )
    assert any(
        f.category == "forbidden_change" and f.field == "forbidden_changes"
        for f in findings
    )


def test_forbidden_changes_rejects_allowed_path_inside_forbidden_directory():
    findings = validate_scope(
        _packet(
            allowed_paths=["gateway/secrets.py"],
            forbidden_changes=["gateway/"],
        )
    )
    assert any(f.category == "forbidden_change" for f in findings)


def test_forbidden_changes_detects_normalized_path_overlap():
    findings = validate_scope(
        _packet(
            allowed_paths=["gateway/./secrets.py"],
            forbidden_changes=["gateway/secrets.py"],
        )
    )
    assert any(f.category == "forbidden_change" for f in findings)


def test_forbidden_changes_allows_disjoint_scope():
    findings = validate_scope(
        _packet(
            allowed_paths=["gateway/worker.py"],
            forbidden_changes=["gateway/secrets.py"],
        )
    )
    assert not any(f.category == "forbidden_change" for f in findings)


def test_absolute_path_is_unbounded():
    findings = validate_scope(_packet(allowed_paths=["/etc/passwd"]))
    assert any(f.category == "unbounded_scope" for f in findings)


def test_parent_escape_is_unbounded():
    findings = validate_scope(_packet(allowed_paths=["../secrets"]))
    assert any(f.category == "unbounded_scope" for f in findings)


def test_protected_zone_requires_architectural_judgment():
    """Generic code packet touching a protected architecture path → escalates."""
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


def test_explicit_doc_packet_proceeds():
    """Explicit documentation-alignment packet naming the protected document → proceeds."""
    findings = validate_scope(
        _packet(
            objective="Update frontmatter in docs/adr/0001-db-scope.md",
            acceptance_criteria=[
                "0001-db-scope.md has valid YAML frontmatter",
                "docs lint passes",
            ],
            allowed_paths=["docs/adr/0001-db-scope.md"],
        )
    )
    assert not any(f.category == "architectural_judgment_required" for f in findings)


def test_implicit_adr_reference_proceeds():
    """Packet referencing a governing ADR in objective → proceeds."""
    findings = validate_scope(
        _packet(
            objective="Implement ADR-0019: add Knowledge Model to repository index",
            acceptance_criteria=[
                "KNOWLEDGE_MODEL.md registered in INDEX.md",
                "docs lint passes",
            ],
            allowed_paths=["docs/INDEX.md", "docs/knowledge/KNOWLEDGE_MODEL.md"],
        )
    )
    assert not any(f.category == "architectural_judgment_required" for f in findings)


def test_constitutional_change_without_authority_escalates():
    """Packet touching constitutional docs without ADR reference → escalates."""
    findings = validate_scope(
        _packet(
            objective="Improve the constitution",
            acceptance_criteria=["make it better"],
            allowed_paths=["docs/CONSTITUTION.md"],
        )
    )
    assert any(f.category == "architectural_judgment_required" for f in findings)


def test_protected_prefix_with_explicit_directory_authority_proceeds():
    """Packet naming the protected directory in criteria → proceeds."""
    findings = validate_scope(
        _packet(
            objective="Reconcile all docs/knowledge/ files with runtime reality",
            acceptance_criteria=[
                "Every file in docs/knowledge/ reflects current runtime",
            ],
            allowed_paths=["docs/knowledge/KNOWLEDGE_MODEL.md"],
        )
    )
    assert not any(f.category == "architectural_judgment_required" for f in findings)


def test_generic_objective_with_protected_path_escalates():
    """Generic 'improve documentation' touching protected path → escalates."""
    findings = validate_scope(
        _packet(
            objective="Improve documentation",
            acceptance_criteria=["docs are better"],
            allowed_paths=["docs/architecture/REFERENCE_ARCHITECTURE.md"],
        )
    )
    assert any(f.category == "architectural_judgment_required" for f in findings)


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
