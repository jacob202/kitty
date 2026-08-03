from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway.session_end_audit import SessionEndAuditError, audit_session_end


def _write_receipt(path: Path, **overrides) -> None:
    receipt = {
        "schema_version": 1,
        "session_id": "builder-run-20260803",
        "recorded_at": "2026-08-03T08:00:00-06:00",
        "execution_owner": "builder",
        "tool": "opencode",
        "task_class": "code_change",
        "outcome": "accepted",
        "kb_entries_consulted": [],
        "kb_entries_used": [],
        "kb_entries_stale_or_wrong": [],
        "promoted_to_canonical": [],
        "kb_tokens_loaded": 100,
        "total_tokens": 1800000,
        "estimated_cost_usd": 12.0,
        "elapsed_seconds": 86400,
        "attempts": 14,
        "repair_commits": 8,
        "regressions": 3,
        "first_pass_approved": False,
        "duplicate_work_avoided": False,
        "correction_prevented": False,
        "result_id": "builder-result-7-packets",
        "task_id": "task-7",
        "initiative_id": "initiative-builder-dogfood",
        "packet_id": "packet-7",
        "branch": "builder/dogfood",
        "head_sha": "a" * 40,
        "notes": "DeepSeek V4 Pro supervised DeepSeek V4 Flash via OpenRouter; slow metadata-heavy run",
    }
    receipt.update(overrides)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"receipt": receipt}) + "\n", encoding="utf-8")


def _write_signal(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "slow-builder.json").write_text(
        json.dumps(
            {
                "id": "wfs_slow_builder",
                "recorded_at": "2026-08-03T08:05:00-06:00",
                "stable_key": "builder-throughput-collapse",
                "category": "paid_waste",
                "severity": "high",
                "summary": "Builder took 24 hours for seven packets",
                "evidence": "Most elapsed time was metadata, resets, and recovery",
                "impact": "Low throughput and high token cost",
                "suggested_change": "Pause on low accepted-packet throughput",
            }
        ),
        encoding="utf-8",
    )


def _paths(tmp_path: Path):
    canonical = tmp_path / "repo/.agents/skills/session-end/SKILL.md"
    installed = tmp_path / "home/.config/opencode/skills/session-end/SKILL.md"
    log = tmp_path / "home/.local/share/opencode/log/opencode.log"
    receipts = tmp_path / "home/kb/metrics/kb-effectiveness.jsonl"
    signals = tmp_path / "home/kb/workflow-signals"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# session-end\nrequired receipt\n", encoding="utf-8")
    installed.parent.mkdir(parents=True)
    installed.write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")
    log.parent.mkdir(parents=True)
    log.write_text("loaded skill session-end from repository\n", encoding="utf-8")
    return canonical, installed, log, receipts, signals


def test_full_execution_evidence_verifies_opencode_session_end(tmp_path):
    canonical, installed, log, receipts, signals = _paths(tmp_path)
    _write_receipt(receipts)
    _write_signal(signals)

    result = audit_session_end(
        canonical_skill=canonical,
        skill_candidates=[installed],
        log_candidates=[log],
        receipt_store=receipts,
        signal_root=signals,
    )

    assert result.status == "verified"
    assert all(
        finding.status != "fail"
        for finding in result.findings
        if finding.check
        in {
            "canonical_skill",
            "opencode_skill_log",
            "builder_opencode_receipt",
            "receipt_completeness",
            "workflow_signal",
        }
    )


def test_skill_file_alone_is_not_execution_proof(tmp_path):
    canonical, installed, log, receipts, signals = _paths(tmp_path)
    log.unlink()

    result = audit_session_end(
        canonical_skill=canonical,
        skill_candidates=[installed],
        log_candidates=[log],
        receipt_store=receipts,
        signal_root=signals,
    )

    assert result.status == "unverified"
    failed = {finding.check for finding in result.findings if finding.status == "fail"}
    assert "opencode_skill_log" in failed
    assert "builder_opencode_receipt" in failed
    assert "workflow_signal" in failed


def test_generic_receipt_without_campaign_measurements_fails(tmp_path):
    canonical, installed, log, receipts, signals = _paths(tmp_path)
    _write_receipt(
        receipts,
        elapsed_seconds=None,
        attempts=None,
        repair_commits=None,
        regressions=None,
        total_tokens=None,
        estimated_cost_usd=None,
        notes="finished",
    )
    _write_signal(signals)

    result = audit_session_end(
        canonical_skill=canonical,
        skill_candidates=[installed],
        log_candidates=[log],
        receipt_store=receipts,
        signal_root=signals,
    )

    assert result.status == "unverified"
    finding = next(item for item in result.findings if item.check == "receipt_completeness")
    assert finding.status == "fail"
    assert "elapsed_seconds" in finding.detail
    assert "model/provider" in finding.detail


def test_interactive_opencode_receipt_does_not_prove_builder_session_end(tmp_path):
    canonical, installed, log, receipts, signals = _paths(tmp_path)
    _write_receipt(receipts, execution_owner="interactive")
    _write_signal(signals)

    result = audit_session_end(
        canonical_skill=canonical,
        skill_candidates=[installed],
        log_candidates=[log],
        receipt_store=receipts,
        signal_root=signals,
    )

    assert result.status == "unverified"
    finding = next(item for item in result.findings if item.check == "builder_opencode_receipt")
    assert finding.status == "fail"


def test_corrupt_receipt_store_fails_loudly(tmp_path):
    canonical, installed, log, receipts, signals = _paths(tmp_path)
    receipts.parent.mkdir(parents=True)
    receipts.write_text("not json\n", encoding="utf-8")

    with pytest.raises(SessionEndAuditError, match="invalid receipt JSON"):
        audit_session_end(
            canonical_skill=canonical,
            skill_candidates=[installed],
            log_candidates=[log],
            receipt_store=receipts,
            signal_root=signals,
        )
