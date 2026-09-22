"""Regression coverage for Kitty's documentation authority boundary."""

import re
from pathlib import Path

import pytest
import yaml

from gateway.paths import PROJECT_ROOT
from gateway.skill_registry import SKILL_ROOTS, discover, invoke, suggest

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
    handoff = _read("docs/archive/plans-2026-09-14/plans/openwebui-agent-handoff-2026-08-02.md")

    assert "Historical compatibility runbook" in runbook
    assert "Do not use this as current startup or architecture guidance" in runbook
    assert "Native Kitty is the canonical frontend" in runbook
    assert "Status: historical handoff, not current operating guidance" in handoff
    assert "All “current” and “verified” claims below are scoped to the 2026-08-02 session" in handoff

def test_shared_doctrine_challenges_premises_without_mandatory_closeout() -> None:
    start_here = " ".join(_read("START_HERE.md").lower().split())
    agents = " ".join(_read("AGENTS.md").lower().split())
    preferences = " ".join(_read("config/PREFERENCES.md").lower().split())
    session_end = " ".join(_read(".agents/skills/session-end/SKILL.md").lower().split())

    assert "no mandatory session-end workflow follows" in start_here
    assert "challenge unsupported premises" in agents
    assert "never claim understanding when material ambiguity remains" in agents
    assert "clarifying question" in agents
    assert "never poll ci" in agents
    assert "gh pr checks <n> --watch" in agents
    assert "config/preferences.md" in agents
    assert "once per session" in agents

    assert "do not agree with jacob merely because he said something" in preferences
    assert "never invent facts or certainty" in preferences
    assert "meaningful clarification" in preferences

    assert "suspended compatibility skill" in session_end
    assert "do not invoke this skill automatically" in session_end
    assert "do not post gar handoffs" in session_end


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

    migration = " ".join(_read("docs/archive/plans-2026-09-14/plans/migration-health.md").lower().split())
    assert "generated compatibility report" in migration
    assert "not a plan or authority" in migration
    assert "scripts/migration-audit.sh" in migration


def test_retained_design_plans_warn_that_old_authority_language_is_historical() -> None:
    for relative in (
        "docs/archive/plans-2026-09-14/plans/KITTYBUILDER_DAILY_DRIVER_PLAN.md",
        "docs/archive/plans-2026-09-14/plans/KITTY_PRODUCT_EXPERIENCE_V1.md",
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
        "ACTIVE_MISSION.md",
    ):
        assert name in index

def test_verified_delivery_preserves_formal_completion_review() -> None:
    skill = " ".join(_read(".agents/skills/verified-delivery/SKILL.md").lower().split())

    for required in (
        "formal completion review",
        "original user request",
        "every explicit requirement",
        "unsupported assumptions",
        "reasoning or process flaws",
        "actionable finding reopens the task",
        "fix it",
        "rerun affected verification",
        "repeat this review",
    ):
        assert required in skill

    assert "green suite" in skill
    assert "cannot substitute for outcome-level review" in skill


def test_documentation_consolidation_plan_records_task7_completion() -> None:
    plan = _read(
        "docs/archive/plans-2026-09-14/superpowers-plans/2026-09-03-repository-documentation-consolidation.md"
    )
    task7 = plan.split("### Task 7:", 1)[1]

    assert "- [ ]" not in task7
    assert task7.count("- [x]") == 6
    assert "f423dcbc8692e573682ed51514bc53f9daa51fdc" in task7
    assert "150 passed, 56 deselected" in task7
    assert "573 current markdown files" in task7.lower()
    assert "0 broken local links" in task7.lower()


def test_default_doctrine_uses_tiny_local_claims_not_agent_room_assignment() -> None:
    start_here = " ".join(_read("START_HERE.md").lower().split())
    agents = " ".join(_read("AGENTS.md").lower().split())
    next_skill = " ".join(_read(".agents/skills/next/SKILL.md").lower().split())

    for text in (start_here, agents, next_skill):
        assert "scripts/work_claim.py" in text
    assert "room briefing" not in start_here
    assert "room briefing" not in next_skill
    assert "gar is not mandatory recall" in agents
    assert "overlapping active scopes" in start_here


def test_cross_client_startup_uses_live_state_without_mandatory_gar() -> None:
    start_here = " ".join(_read("START_HERE.md").lower().split())
    agents = " ".join(_read("AGENTS.md").lower().split())

    for text in (start_here, agents):
        assert "git/github" in text
        assert "builder" in text
        assert "gar" in text

    assert "do not use builder or gar during ordinary startup" in start_here
    assert "room briefing" not in start_here
    assert "builder is not the default executor" in agents
    assert "ordinary completion must not create gar traffic" in agents


def test_catchup_allows_its_local_claim_status_command() -> None:
    for path in (
        ".agents/skills/catchup/SKILL.md",
        ".claude/skills/catchup/SKILL.md",
    ):
        text = _read(path)
        assert "python3 scripts/work_claim.py status" in text
        assert "Bash(python3 scripts/work_claim.py *)" in text


def test_adr_0043_aligns_suspension_authorities() -> None:
    adr = " ".join(_read("docs/adr/0043-suspend-builder-gar-defaults.md").lower().split())
    decisions = " ".join(_read("docs/DECISIONS.md").lower().split())
    authority = " ".join(_read("docs/AUTHORITY_MAP.md").lower().split())

    assert "accepted — operational suspension experiment" in adr
    assert "builder is suspended as kitty's default executor" in adr
    assert "gar is suspended as mandatory lifecycle and recall infrastructure" in adr
    assert "adr 0021's proactive/default builder execution is suspended" in adr
    assert "adr 0023's automatic session-end carry-forward behavior is suspended" in adr
    assert "does **not**" in adr
    assert "amend the constitution" in adr

    assert "d41" in decisions
    assert "0043-suspend-builder-gar-defaults.md" in decisions
    assert "default/proactive activation suspended by d41" in decisions

    assert "current assignment plus live git/github/runtime evidence under adr 0043" in authority
    assert "historical compatibility snapshot preserved for rollback/archaeology during adr 0043" in authority
    assert "adr 0043 is the later accepted decision" in authority


# --- Skill-health contracts (skill registry authority, 2026-09-16) ---
# Strict frontmatter, spec limits, registry sync, glossary includes, and
# natural-request trigger routing. A skill that stops satisfying these
# silently leaves discovery for some consumer; the contracts make it loud.


ENGINEERING_FAMILY = (
    "improve-codebase",
    "improve-codebase-architecture",
    "harden-codebase",
    "improve-daily-ux",
    "verify-by-mutation",
    "maintain-repo",
    "audit-docs",
    "audit-workflow",
    "audit-architecture",
)

# Natural request -> the skill that must be suggested for it. These are literal
# phrase contracts: Kitty matches on trigger phrases from when_to_use and the
# USE WHEN clause, so a rephrasing that stops matching is a regression.
TRIGGER_CASES = (
    ("improve the codebase", "improve-codebase"),
    ("make this better", "improve-codebase"),
    ("what should I fix", "improve-codebase"),
    ("harden this", "improve-codebase"),
    ("are the docs stale", "audit-docs"),
    ("docs out of date", "audit-docs"),
    ("audit the ci workflows", "audit-workflow"),
    ("are the gates real", "audit-workflow"),
    ("harden the error handling", "harden-codebase"),
    ("check the dependencies for anything sketchy", "harden-codebase"),
    ("refactor this module", "improve-codebase-architecture"),
    ("is this test real", "verify-by-mutation"),
    ("polish the ui", "improve-daily-ux"),
    ("audit the architecture", "audit-architecture"),
    ("audit the repo, what is stale", "maintain-repo"),
)


def _active_skill_files() -> list[Path]:
    files: list[Path] = []
    for root in SKILL_ROOTS:
        if not root.exists():
            continue
        for skill_file in sorted(root.rglob("SKILL.md")):
            parts = skill_file.relative_to(root).parts
            if parts and parts[0] == "_archive":
                continue
            files.append(skill_file)
    return files


def _strict_frontmatter(path: Path) -> dict:
    text = path.read_text()
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    assert match, f"{path}: no frontmatter block"
    result = yaml.safe_load(match.group(1))  # raises on anything strict YAML rejects
    assert isinstance(result, dict), f"{path}: frontmatter is not a mapping"
    return result


def test_active_skill_frontmatter_is_strict_yaml():
    """An unquoted colon-space is invalid YAML: Kitty's parser falls back to a
    tolerant line parse, Command Code drops the skill. Every active skill must
    parse strictly so both consumers see the same set."""
    for path in _active_skill_files():
        _strict_frontmatter(path)


def test_active_skill_descriptions_fit_spec_limits():
    for path in _active_skill_files():
        meta = _strict_frontmatter(path)
        description = meta.get("description", "")
        name = meta.get("name", "")
        assert isinstance(description, str) and description, path
        assert len(description) <= 1024, f"{path}: description is {len(description)} chars"
        assert isinstance(name, str) and re.fullmatch(r"[a-z0-9-]{1,64}", name), path
        assert path.parent.name == name, f"{path}: directory name must match skill name"


def test_engineering_family_is_discoverable():
    names = {skill["name"] for skill in discover(force_refresh=True)}
    for name in ENGINEERING_FAMILY:
        assert name in names, name


def test_engineering_family_glossary_includes_are_expanded():
    """Each specialist's LANGUAGE.md include must resolve through invoke(); an
    inert shell token reaching the prompt is a silent skill failure."""
    skills = {skill["name"]: skill for skill in discover(force_refresh=True)}
    for name in ENGINEERING_FAMILY:
        skill = skills.get(name)
        assert skill, name
        if not (Path(skill["path"]).parent / "LANGUAGE.md").exists():
            continue
        result = invoke(name)
        assert "error" not in result, name
        assert "COMMANDCODE_SKILL_DIR" not in result["prompt"], name
        assert "Shared vocabulary" in result["prompt"], name


def test_registry_document_lists_every_active_skill():
    """SKILL_REGISTRY.md is the single source of truth for bundled skills; its own
    freshness clause requires a re-walk when a skill is added or removed."""
    registry_text = (PROJECT_ROOT / "SKILL_REGISTRY.md").read_text()
    names = {skill["name"] for skill in discover(force_refresh=True)}
    missing = sorted(name for name in names if name not in registry_text)
    assert not missing, f"active skills missing from SKILL_REGISTRY.md: {missing}"


@pytest.mark.parametrize(("phrase", "expected"), TRIGGER_CASES)
def test_natural_request_suggests_expected_skill(phrase: str, expected: str):
    # Production (gateway/context_assembler.py) consumes only the first
    # suggestion; membership among five would let a competing route win silently.
    names = [skill["name"] for skill in suggest(phrase, limit=1)]
    assert names == [expected], f"{phrase!r} suggested {names}, expected {expected}"
