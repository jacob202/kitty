"""Tests for next_step — the single curated "B" per project (P4, docs/packets/016).

No real network/model calls in this suite — an injected llm_fn stands in
for gateway.llm_client.call_llm, same seam as test_triage.py.
"""
import json

import pytest

from gateway import next_step, project_resume, project_store


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
