"""Tests for next_step — the single curated "B" per project (P4, docs/packets/016).

No real network/model calls in this suite — an injected llm_fn stands in
for gateway.llm_client.call_llm, same seam as test_triage.py.
"""
import json
from pathlib import Path

import pytest

from gateway import next_step, project_resume, project_store
from gateway.next_step import NextStepError


@pytest.fixture(autouse=True)
def isolate_stores(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(project_store, "PROJECTS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(next_step, "NEXT_STEP_DB_FILE", db_file, raising=False)
    # No real network calls for the memory/signal sources refresh() touches.
    from gateway.memory_graph import GraphResult

    monkeypatch.setattr(project_resume, "_run_memory_search", lambda q: GraphResult())
    monkeypatch.setattr("gateway.signal_store.list_recent", lambda limit=200: [])


def _stub_llm(response: dict):
    calls = []

    def fn(prompt, privacy_tier, content_class):
        calls.append({"prompt": prompt, "privacy_tier": privacy_tier, "content_class": content_class})
        return json.dumps(response)

    fn.calls = calls
    return fn


class TestGenerate:
    def test_generate_returns_step_from_llm_response(self):
        project = project_store.create("x", "code")
        llm = _stub_llm({"step": "write the migration", "why": "unblocks the rest", "recent_win": "spec authored", "delegable": False})

        result = next_step.generate(project["id"], llm_fn=llm)

        assert result["step"] == "write the migration"
        assert result["why"] == "unblocks the rest"
        assert result["delegable"] is False
        assert result["changed"] is True

    def test_generate_persists_and_get_reads_it_back(self):
        project = project_store.create("x", "code")
        llm = _stub_llm({"step": "s", "why": "w", "recent_win": "r", "delegable": True})

        next_step.generate(project["id"], llm_fn=llm)
        stored = next_step.get(project["id"])

        assert stored["step"] == "s"
        assert stored["delegable"] is True

    def test_second_generate_with_same_step_reports_unchanged(self):
        project = project_store.create("x", "code")
        llm = _stub_llm({"step": "same step", "why": "w", "delegable": False})

        first = next_step.generate(project["id"], llm_fn=llm)
        second = next_step.generate(project["id"], llm_fn=llm)

        assert first["changed"] is True
        assert second["changed"] is False

    def test_generate_with_different_step_reports_changed(self):
        project = project_store.create("x", "code")
        llm_one = _stub_llm({"step": "step one", "why": "w", "delegable": False})
        llm_two = _stub_llm({"step": "step two", "why": "w", "delegable": False})

        next_step.generate(project["id"], llm_fn=llm_one)
        second = next_step.generate(project["id"], llm_fn=llm_two)

        assert second["changed"] is True

    def test_code_project_uses_cloud_ok_privacy_tier(self):
        project = project_store.create("x", "code")
        llm = _stub_llm({"step": "s", "why": "w", "delegable": False})

        next_step.generate(project["id"], llm_fn=llm)

        assert llm.calls[0]["privacy_tier"] == "cloud_ok"
        assert llm.calls[0]["content_class"] is None

    def test_admin_project_uses_local_privacy_tier(self):
        project = project_store.create("benefits", "admin")
        llm = _stub_llm({"step": "s", "why": "w", "delegable": False})

        next_step.generate(project["id"], llm_fn=llm)

        assert llm.calls[0]["privacy_tier"] == "local"
        assert llm.calls[0]["content_class"] == "health_admin"

    def test_missing_project_raises(self):
        llm = _stub_llm({"step": "s", "why": "w"})
        with pytest.raises(project_store.ProjectNotFound):
            next_step.generate(999999, llm_fn=llm)

    def test_non_json_response_raises_next_step_error(self):
        def bad_llm(prompt, privacy_tier, content_class):
            return "not json at all"

        project = project_store.create("x", "code")
        with pytest.raises(next_step.NextStepError):
            next_step.generate(project["id"], llm_fn=bad_llm)

    def test_response_missing_step_raises(self):
        project = project_store.create("x", "code")
        llm = _stub_llm({"why": "no step here"})
        with pytest.raises(next_step.NextStepError):
            next_step.generate(project["id"], llm_fn=llm)


class TestGetAndInvalidate:
    def test_get_returns_none_when_never_generated(self):
        project = project_store.create("x", "code")
        assert next_step.get(project["id"]) is None

    def test_invalidate_clears_the_stored_step(self):
        project = project_store.create("x", "code")
        llm = _stub_llm({"step": "s", "why": "w", "delegable": False})
        next_step.generate(project["id"], llm_fn=llm)

        next_step.invalidate(project["id"])

        assert next_step.get(project["id"]) is None


class TestLoadPreferencesFailLoud:
    def test_missing_file_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(next_step, "CONFIG_DIR", tmp_path / "empty_cfg")
        assert next_step._load_preferences() == ""

    def test_unreadable_file_raises(self, monkeypatch, tmp_path):
        cfg = tmp_path / "cfg"
        cfg.mkdir()
        (cfg / "PREFERENCES.md").write_text("")
        real_read = Path.read_text

        def fake(self, *args, **kwargs):
            if self.name == "PREFERENCES.md":
                raise OSError("disk gone")
            return real_read(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fake)
        with pytest.raises(NextStepError):
            next_step._load_preferences()


class TestSelectSteps:
    """Life-first ordering per ADR 0016 — select_steps()."""

    def _gen(self, name: str, kind: str, step: str) -> dict:
        """Create a project and generate a next step for it."""
        proj = project_store.create(name, kind)
        llm = _stub_llm({"step": step, "why": "test reason", "delegable": False})
        next_step.generate(proj["id"], llm_fn=llm)
        return proj

    def test_life_project_comes_before_code(self):
        """Given code and life projects both with steps, life surfaces first."""
        self._gen("my-app", "code", "refactor auth")
        self._gen("job-search", "education", "update resume")

        steps = next_step.select_steps(limit=5)

        assert len(steps) >= 2
        assert steps[0]["project_name"] == "job-search"
        assert steps[1]["project_name"] == "my-app"

    def test_at_most_one_self_dev_when_life_exists(self):
        """With one life step and multiple kitty-development steps,
        at most one self-development suggestion appears."""
        self._gen("job-search", "education", "update resume")
        self._gen("kitty", "code", "fix the bug")
        self._gen("kittybuilder", "code", "add feature")

        steps = next_step.select_steps(limit=10)

        # Life comes first.
        assert steps[0]["project_name"] == "job-search"
        # At most one kitty/code step after the life step.
        kitty_entries = [s for s in steps if "kitty" in s["project_name"].lower()]
        assert len(kitty_entries) <= 1

    def test_self_dev_never_above_life(self):
        """Self-development suggestion never appears above the life step."""
        self._gen("job-search", "education", "update resume")
        self._gen("kitty", "code", "fix the bug")

        steps = next_step.select_steps(limit=5)

        assert steps[0]["project_name"] == "job-search"

    def test_no_life_all_code_present(self):
        """Behavior with only code projects present is unchanged —
        all steps show, ordered by id (natural insertion order)."""
        self._gen("app1", "code", "step one")
        self._gen("app2", "code", "step two")

        steps = next_step.select_steps(limit=10)

        # Both projects appear since there are no life steps to cause capping.
        names = [s["project_name"] for s in steps]
        assert "app1" in names
        assert "app2" in names
        # The seeded 'kitty' project might also appear if it had a step,
        # but it doesn't — so only our two projects show.
        assert len(steps) >= 2

    def test_self_dev_without_life_all_appear(self):
        """When no life steps exist, all self-development steps surface."""
        self._gen("kitty", "code", "step one")
        self._gen("app", "code", "step two")

        steps = next_step.select_steps(limit=10)

        names = [s["project_name"] for s in steps]
        assert "kitty" in names
        assert "app" in names

    def test_limit_respected(self):
        """select_steps returns at most limit entries."""
        for i in range(5):
            self._gen(f"proj-{i}", "education", f"step {i}")

        steps = next_step.select_steps(limit=3)

        assert len(steps) == 3

    def test_projects_without_steps_are_skipped(self):
        """Projects that have never been generated for are omitted."""
        project_store.create("no-step-project", "education")
        self._gen("job-search", "education", "update resume")

        steps = next_step.select_steps(limit=5)

        assert len(steps) == 1
        assert steps[0]["project_name"] == "job-search"
