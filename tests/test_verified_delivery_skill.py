"""Deterministic required-content contracts for the verified-delivery skill.

Unlike a prose review, these tests fail when the skill's load/registry/
format invariants regress: frontmatter stays discoverable, the outcome
contract keeps its required sections, the four completion states stay the
exact vocabulary, and the shared context-engineering doc keeps the
compaction/handoff contract. No gateway imports — pytest only.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / ".agents" / "skills" / "verified-delivery"
SKILL_MD = SKILL_DIR / "SKILL.md"
OUTCOME_CONTRACT = SKILL_DIR / "outcome-contract.md"
PRESSURE_TESTS = SKILL_DIR / "pressure-tests.md"
CONTEXT_ENGINEERING = ROOT / "docs" / "reference" / "CONTEXT_ENGINEERING.md"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _frontmatter(path: Path) -> dict[str, str]:
    m = _FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if not m:
        return {}
    result: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        result[key.strip()] = value.strip()
    return result


class TestSkillLoadAndRegistry:
    def test_skill_file_exists(self):
        assert SKILL_MD.is_file()
        assert OUTCOME_CONTRACT.is_file()
        assert PRESSURE_TESTS.is_file()

    def test_frontmatter_is_discoverable(self):
        meta = _frontmatter(SKILL_MD)
        assert meta.get("name").strip() == "verified-delivery"
        assert meta.get("description", "").strip()

    def test_registry_lists_the_skill(self):
        registry = (ROOT / "SKILL_REGISTRY.md").read_text(encoding="utf-8")
        assert "verified-delivery" in registry


class TestOutcomeContractContent:
    def test_required_sections_present(self):
        text = OUTCOME_CONTRACT.read_text(encoding="utf-8")
        for heading in (
            "## Identity",
            "## User-visible outcome",
            "## Acceptance criteria",
            "## Non-goals",
            "## Prohibited shortcuts",
            "## Context that must survive compaction or handoff",
            "## Verifier report",
            "## Final state",
        ):
            assert heading in text, f"missing heading {heading!r}"

    def test_exact_completion_states(self):
        text = OUTCOME_CONTRACT.read_text(encoding="utf-8")
        for state in (
            "`verified`",
            "`implemented, awaiting verification`",
            "`blocked`",
            "`failed`",
        ):
            assert state in text, f"missing completion state {state}"


class TestSkillContent:
    def test_four_state_vocabulary(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        for state in (
            "verified",
            "implemented, awaiting verification",
            "blocked",
            "failed",
        ):
            assert state in text

    def test_references_outcome_contract(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        assert "outcome-contract.md" in text

    def test_self_check_is_not_independent(self):
        # Constitution VI.4: the executor is never the reviewer. A same-context
        # review is a self-check; only a separate trust boundary can accept.
        text = SKILL_MD.read_text(encoding="utf-8")
        assert "self-check" in text
        assert "separate trust boundary" in text
        assert "implemented, awaiting verification" in text

    def test_repair_cap_is_bounded(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        assert "repair" in text.lower()
        assert "do not keep polishing indefinitely" in text


class TestPressureScenarios:
    def test_all_five_pressure_scenarios_present(self):
        text = PRESSURE_TESTS.read_text(encoding="utf-8")
        for title in (
            "## 1. The plausible fix",
            "## 2. The user wants certainty",
            "## 3. The long-context handoff",
            "## 4. The verifier shortcut",
            "## 5. The endless repair loop",
            "## Failure signatures",
        ):
            assert title in text, f"missing pressure scenario {title!r}"


class TestContextEngineeringContract:
    def test_doc_references_skill(self):
        text = CONTEXT_ENGINEERING.read_text(encoding="utf-8")
        assert "verified-delivery" in text

    def test_compaction_handoff_preserves_authority_and_next_action(self):
        text = CONTEXT_ENGINEERING.read_text(encoding="utf-8")
        for required in (
            "outcome contract and non-goals",
            "accepted decisions and their authority",
            "branch/worktree, and SHA",
            "exact verification commands and results",
            "unresolved failures and blockers",
            "one concrete next action",
        ):
            assert required in text, f"compaction contract missing {required!r}"

    def test_doc_ends_with_newline(self):
        text = CONTEXT_ENGINEERING.read_text(encoding="utf-8")
        assert text.endswith("\n"), "docs/reference/CONTEXT_ENGINEERING.md must end with a newline"
