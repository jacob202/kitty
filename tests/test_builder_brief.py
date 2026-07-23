"""Phase 1B tests for gateway/builder_brief.py — worker brief rendering."""

from __future__ import annotations

import json

from gateway.builder_brief import (
    default_branch_name,
    render_worker_brief,
    resources_for_paths,
)


def _task(**overrides) -> dict:
    base = {
        "id": "kb_test0000_abcd",
        "title": "Fix the flux capacitor",
        "state": "queued",
        "priority": 5,
        "description": "It fluxes when it should capacitate.",
        "acceptance_criteria": ["tests pass", "no new deps"],
        "allowed_paths": ["gateway/flux.py", "tests/test_flux.py"],
        "lease_owner": None,
        "final_report_json": None,
    }
    base.update(overrides)
    return base


class TestDefaultBranchName:
    def test_uses_task_id(self):
        assert default_branch_name(_task()) == "kittybuilder/kb_test0000_abcd"


class TestRenderWorkerBrief:
    def test_full_brief_contains_all_sections(self):
        brief = render_worker_brief(_task(), [], [])
        assert "kb_test0000_abcd" in brief
        assert "Fix the flux capacitor" in brief
        assert "1. tests pass" in brief
        assert "2. no new deps" in brief
        assert "`gateway/flux.py`" in brief
        assert "FORBIDDEN" in brief
        assert "kittybuilder/kb_test0000_abcd" in brief
        assert "lease_token" in brief
        assert "Stop conditions" in brief
        assert "Never merge" in brief

    def test_branch_override(self):
        brief = render_worker_brief(_task(), [], [], branch="feat/custom")
        assert "`feat/custom`" in brief
        assert "kittybuilder/kb_test0000_abcd" not in brief.split("\n")[5]

    def test_missing_criteria_says_stop(self):
        brief = render_worker_brief(_task(acceptance_criteria=None), [], [])
        assert "STOP: ask the operator to add acceptance criteria" in brief

    def test_missing_allowed_paths_falls_back(self):
        brief = render_worker_brief(_task(allowed_paths=None), [], [])
        assert "No path allowlist recorded" in brief

    def test_claimed_task_shows_owner(self):
        brief = render_worker_brief(
            _task(state="claimed", lease_owner="worker-9"), [], []
        )
        assert "worker-9" in brief
        assert "taking over" in brief

    def test_previous_report_included_for_takeover(self):
        report = {"summary": "got halfway", "tests": "3/5"}
        brief = render_worker_brief(
            _task(final_report_json=json.dumps(report)), [], []
        )
        assert "Previous final report" in brief
        assert "got halfway" in brief

    def test_pr_links_rendered(self):
        links = [
            {
                "pr_number": 141,
                "pr_url": "https://x/141",
                "head_sha": "abcdef12345",
                "checks_state": "success",
                "review_state": None,
            }
        ]
        brief = render_worker_brief(_task(), [], links)
        assert "PR #141" in brief
        assert "checks: success" in brief

    def test_events_tail_limited_to_ten(self):
        events = [
            {"created_at": f"t{i}", "type": f"ev{i}", "payload": None}
            for i in range(15)
        ]
        brief = render_worker_brief(_task(), events, [])
        assert "ev14" in brief
        assert "ev4" not in brief
        assert "last 10" in brief

    def test_no_events_no_section(self):
        brief = render_worker_brief(_task(), [], [])
        assert "Recent events" not in brief


class TestCp07ResourcesForPaths:
    def test_mapped_prefix_returns_scripts_and_skills(self):
        result = resources_for_paths(["gateway/builder_loop.py"])
        assert "scripts/kittybuilder_opencode_worker.sh" in result["scripts"]
        assert "catchup" in result["skills"]

    def test_unmapped_path_returns_empty_never_a_guess(self):
        result = resources_for_paths(["gateway/some_brand_new_module.py"])
        assert result == {"scripts": [], "skills": []}

    def test_completely_unrelated_prefix_stays_empty(self):
        result = resources_for_paths(["random_top_level_file.txt"])
        assert result == {"scripts": [], "skills": []}

    def test_dedupes_across_multiple_paths(self):
        result = resources_for_paths(
            ["gateway/builder_run.py", "gateway/builder_loop.py"]
        )
        assert result["scripts"].count("scripts/kittybuilder_opencode_worker.sh") == 1

    def test_multiple_matching_prefixes_union(self):
        result = resources_for_paths(["gateway/builder_x.py", "tests/test_x.py"])
        assert "debug-fix" in result["skills"]
        assert "catchup" in result["skills"]


class TestCp07ResourcesInBrief:
    def test_brief_lists_mapped_resources_for_builder_paths(self):
        task = _task(allowed_paths=["gateway/builder_loop.py"])
        brief = render_worker_brief(task, [], [])
        assert "Resources (CP-07)" in brief
        assert "scripts/kittybuilder_opencode_worker.sh" in brief
        assert "catchup" in brief
        assert "cite which you used" in brief

    def test_brief_omits_resources_section_for_unmapped_paths(self):
        task = _task(allowed_paths=["gateway/some_brand_new_module.py"])
        brief = render_worker_brief(task, [], [])
        assert "Resources (CP-07)" not in brief

    def test_brief_omits_resources_section_when_no_allowed_paths(self):
        task = _task(allowed_paths=None)
        brief = render_worker_brief(task, [], [])
        assert "Resources (CP-07)" not in brief
