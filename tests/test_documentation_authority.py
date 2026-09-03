"""Regression coverage for Kitty's documentation authority boundary."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_dated_catalogs_are_not_current_authorities() -> None:
    authority = _read("docs/AUTHORITY_MAP.md")

    assert "| `knowledge_graph` |" not in authority
    assert "| `disposition_ledger` |" not in authority
    assert "Non-authoritative catalogs and snapshots" in authority


def test_historical_catalogs_point_to_archived_snapshots() -> None:
    ledger = _read("docs/DISPOSITION_LEDGER.md")
    graph = _read("docs/KNOWLEDGE_GRAPH.md")

    assert "Historical compatibility pointer" in ledger
    assert "archive/DISPOSITION_LEDGER_2026-08-08.md" in ledger
    assert "Historical compatibility pointer" in graph
    assert "archive/KNOWLEDGE_GRAPH_2026-08-05.md" in graph
    assert (ROOT / "docs/archive/DISPOSITION_LEDGER_2026-08-08.md").is_file()
    assert (ROOT / "docs/archive/KNOWLEDGE_GRAPH_2026-08-05.md").is_file()


def test_planning_activation_is_fail_closed_without_ledger_membership() -> None:
    prevention = _read("docs/reference/PREVENTION_MECHANISMS.md")

    assert "A new plan, packet, or initiative is inert by default" in prevention
    assert "must appear in `docs/DISPOSITION_LEDGER.md`" not in prevention
    assert "ledger-coverage-check.yml" not in prevention


def test_packet_claim_guidance_uses_live_coordination() -> None:
    packets = _read("docs/packets/README.md")

    assert "`.claude/STATE.md`" not in packets
    assert "workspace_global" in packets
    assert "issue #490" in packets


def test_architecture_skill_uses_current_context_and_adrs() -> None:
    skill = _read(".agents/skills/engineering/improve-codebase-architecture/SKILL.md")

    assert "docs/reference/CONTEXT_ENGINEERING.md" in skill
    assert "Kitty has no formal ADR directory yet" not in skill
    assert "docs/adr/" in skill
    assert "context_builder" not in skill
    assert "context_assembler" in skill

    context_format = _read(".agents/skills/engineering/improve-codebase-architecture/CONTEXT-FORMAT.md")
    assert "context_builder" not in context_format
    assert "context_assembler" in context_format


def test_docs_index_labels_dated_material_as_non_authoritative() -> None:
    index = _read("docs/README.md")

    assert "Current GitHub truth pass" not in index
    assert "Historical and derived catalogs" in index
    assert "DISPOSITION_LEDGER.md" in index
    assert "KNOWLEDGE_GRAPH.md" in index


def test_root_readme_defers_cold_start_to_start_here() -> None:
    readme = _read("README.md")

    assert "START_HERE.md" in readme
    assert "GITHUB_OPERATING_PICTURE_2026-08-04" not in readme
    assert "./kitty down" in readme
    assert "make test" in readme
    assert "make ui-test && make ui-build" in readme


def test_retired_remote_shortcut_does_not_expose_gateway() -> None:
    siri = _read("docs/SIRI_SHORTCUT.md")

    assert "Retired 2026-09-03" in siri
    assert "KH-REMOTE-01" in siri
    assert "http://<mac-tailscale-hostname>:8000" not in siri
    assert "loopback-only" in siri


def test_legacy_front_doors_are_pointers_not_current_authorities() -> None:
    tasks = _read("TASKS.md")
    orca = _read("docs/KITTYBUILDER_ORCA_SETUP.md")

    assert "Historical Compatibility Pointer" in tasks
    assert "TASKS_2026-06-18.md" in tasks
    assert "Historical Compatibility Pointer" in orca
    assert "FREE_WORKERS.md" in orca
    assert "not the current default worker/reviewer path" in orca


def test_openwebui_onboarding_artifacts_are_explicitly_historical() -> None:
    runbook = _read("docs/runbooks/OPENWEBUI_TOMORROW.md")
    handoff = _read("docs/plans/openwebui-agent-handoff-2026-08-02.md")

    assert "Historical compatibility runbook" in runbook
    assert "Do not use this as current startup or architecture guidance" in runbook
    assert "Native Kitty is the canonical frontend" in runbook
    assert "Status: historical handoff, not current operating guidance" in handoff
    assert "All “current” and “verified” claims below are scoped to the 2026-08-02 session" in handoff

def test_shared_doctrine_challenges_premises_and_closes_substantial_work_automatically() -> None:
    agents = " ".join(_read("AGENTS.md").lower().split())
    preferences = " ".join(_read("config/PREFERENCES.md").lower().split())
    session_end = " ".join(_read(".agents/skills/session-end/SKILL.md").lower().split())

    assert "challenge unsupported premises" in agents
    assert "never claim understanding when material ambiguity remains" in agents
    assert "clarifying question" in agents
    assert "substantial interactive assignment" in agents
    assert "session-end" in agents
    assert "never poll ci" in agents
    assert "gh pr checks <n> --watch" in agents
    assert "config/preferences.md" in agents
    assert "once per session" in agents

    assert "do not agree with jacob merely because he said something" in preferences
    assert "never invent facts or certainty" in preferences
    assert "meaningful clarification" in preferences

    assert "substantial assigned work is genuinely complete" in session_end
    assert "does not need to ask" in session_end
    assert "ordinary turn" in session_end


def test_completion_templates_treat_implementation_as_evidence_only() -> None:
    pr = " ".join(_read(".github/pull_request_template.md").lower().split())
    packet = " ".join(_read("docs/packets/TEMPLATE.md").lower().split())

    assert "user outcome advanced" in pr
    assert "implementation evidence" in pr
    assert "exact running candidate" in pr
    assert "isolated data root" in pr

    assert "packet completion cannot close" in packet
    assert "subagent `done`" in packet
    assert "implementation evidence" in packet
    assert "isolated data root" in packet


def test_stale_session_plans_are_not_left_on_current_execution_surface() -> None:
    archived = ROOT / "docs/archive/legacy-snapshots"
    retired_plans = (
        "image-studio-runpod-vertical-slice-2026-07-30.md",
        "image-studio-next-four-2026-08-02.md",
        "openwebui-onboarding-progress.md",
        "qol-06-safe-retry-2026-08-23.md",
        "feat-kittybuilder-follow-on-roadmap.md",
        "james-workflow-2026-08-02.md",
        "kitty-ui-enhancement-plan.html",
        "openwebui-onboarding-checklist.json",
    )
    for name in retired_plans:
        assert not (ROOT / "docs/plans" / name).exists(), name
        target = archived / name
        assert target.is_file(), name
        if target.suffix == ".md":
            assert "historical snapshot archived 2026-09-03" in target.read_text(encoding="utf-8").lower(), name
        elif target.suffix == ".html":
            assert "historical snapshot — not current instruction" in target.read_text(encoding="utf-8").lower(), name
        elif target.suffix == ".json":
            assert "historical_snapshot_not_current_instruction" in target.read_text(encoding="utf-8"), name

    assert not (ROOT / "docs/phases/DESKTOP_SLICE_1_RUNBOOK.md").exists()
    assert (archived / "DESKTOP_SLICE_1_RUNBOOK.md").is_file()

    migration = " ".join(_read("docs/plans/migration-health.md").lower().split())
    assert "generated compatibility report" in migration
    assert "not a plan or authority" in migration
    assert "scripts/migration-audit.sh" in migration


def test_retained_design_plans_warn_that_old_authority_language_is_historical() -> None:
    for relative in (
        "docs/plans/KITTYBUILDER_DAILY_DRIVER_PLAN.md",
        "docs/plans/KITTY_PRODUCT_EXPERIENCE_V1.md",
    ):
        text = " ".join(_read(relative).lower().split())
        assert "historical/supporting design evidence" in text
        assert "not current execution authority" in text
        assert "roadmap.md" in text


def test_docs_index_names_current_support_surfaces_without_becoming_a_ledger() -> None:
    index = _read("docs/README.md")
    for name in (
        "WORKFLOW.md",
        "PRODUCT_ACCEPTANCE.md",
        "UX_RULES.md",
        "FREE_WORKERS.md",
        "KITTYBUILDER_MCP.md",
        "CAMPAIGN_PLAYBOOK.md",
        "CAPABILITY_MANIFEST.md",
        "PLANS.md",
    ):
        assert name in index
