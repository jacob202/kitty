"""Tests for project_resume — refresh()/resume() composer (P6, docs/packets/021).

Git composition is tested against a real fixture repo (tmp_path + git init +
real commits), not a mocked subprocess — proves the actual git invocations
work, not just that they were called.
"""
import subprocess

import pytest

from gateway import project_resume, project_store


@pytest.fixture(autouse=True)
def isolate_project_store(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(project_store, "PROJECTS_DB_FILE", db_file, raising=False)


@pytest.fixture(autouse=True)
def stub_memory_search(monkeypatch):
    """No real embedding/network calls in this suite — stub an empty graph
    result by default; individual tests override with their own stub."""
    monkeypatch.setattr(project_resume, "_run_memory_search", lambda query: _empty_graph_result())


@pytest.fixture
def fixture_repo(tmp_path):
    """A real git repo with two commits, for git composition tests."""
    repo = tmp_path / "fixture-repo"
    repo.mkdir()

    def run(*args):
        return subprocess.run(args, cwd=repo, check=True, capture_output=True, text=True)

    run("git", "init", "-q")
    run("git", "config", "user.email", "kitty@example.com")
    run("git", "config", "user.name", "Kitty Test")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run("git", "add", "README.md")
    run("git", "commit", "-q", "-m", "first commit")
    (repo / "README.md").write_text("hello again\n", encoding="utf-8")
    run("git", "add", "README.md")
    run("git", "commit", "-q", "-m", "second commit")
    return repo


class TestGitSource:
    def test_refresh_reports_real_branch_and_log(self, fixture_repo):
        project = project_store.create("fixture", "code", paths=[str(fixture_repo)])

        refreshed = project_resume.refresh(project["id"])

        git = refreshed["sources"]["git"]
        assert git["ok"] is True
        entry = git["paths"][0]
        assert entry["ok"] is True
        assert entry["dirty"] is False
        assert len(entry["recent_log"]) == 2
        assert "second commit" in entry["recent_log"][0]

    def test_refresh_reports_dirty_when_uncommitted_changes(self, fixture_repo):
        (fixture_repo / "README.md").write_text("dirty now\n", encoding="utf-8")
        project = project_store.create("fixture", "code", paths=[str(fixture_repo)])

        refreshed = project_resume.refresh(project["id"])

        assert refreshed["sources"]["git"]["paths"][0]["dirty"] is True

    def test_bad_git_path_is_a_per_path_error_not_a_crash(self, tmp_path):
        not_a_repo = tmp_path / "not-a-repo"
        not_a_repo.mkdir()
        project = project_store.create("bad", "code", paths=[str(not_a_repo)])

        refreshed = project_resume.refresh(project["id"])

        git = refreshed["sources"]["git"]
        assert git["ok"] is True
        assert git["paths"][0]["ok"] is False
        assert "not a git repository" in git["paths"][0]["error"]

    def test_non_code_project_skips_git_honestly(self):
        project = project_store.create("benefits", "admin")

        refreshed = project_resume.refresh(project["id"])

        git = refreshed["sources"]["git"]
        assert git["ok"] is True
        assert git["paths"] == []
        assert "non-code" in git["note"]

    def test_code_project_with_no_paths_is_honest_not_fabricated(self):
        project = project_store.create("unregistered", "code")

        refreshed = project_resume.refresh(project["id"])

        git = refreshed["sources"]["git"]
        assert git["paths"] == []
        assert "no git paths registered" in git["note"]


class TestMemoryAndSignalsSources:
    def test_memory_source_failure_does_not_kill_refresh(self, monkeypatch, fixture_repo):
        project = project_store.create("fixture", "code", paths=[str(fixture_repo)])

        def boom(_query):
            raise RuntimeError("memory graph exploded")

        monkeypatch.setattr(project_resume, "_run_memory_search", boom)

        refreshed = project_resume.refresh(project["id"])

        assert refreshed["sources"]["memory"]["ok"] is False
        assert "exploded" in refreshed["sources"]["memory"]["error"]
        # a different source failing doesn't take git down with it
        assert refreshed["sources"]["git"]["ok"] is True

    def test_signals_source_matches_by_project_name(self, monkeypatch):
        project = project_store.create("Sansui", "admin")

        fake_signals = [
            {"id": 1, "payload": {"label": "https://example.com", "keyword_matches": ["sansui"]}},
            {"id": 2, "payload": {"label": "unrelated"}},
        ]
        monkeypatch.setattr(
            "gateway.signal_store.list_recent", lambda limit=200: fake_signals
        )

        refreshed = project_resume.refresh(project["id"])

        signals = refreshed["sources"]["signals"]
        assert signals["ok"] is True
        assert len(signals["matches"]) == 1
        assert signals["matches"][0]["id"] == 1


class TestIdempotency:
    def test_refresh_twice_with_no_change_does_not_drift_stored_fields(self, fixture_repo):
        project = project_store.create("fixture", "code", paths=[str(fixture_repo)])

        first = project_resume.refresh(project["id"])
        second = project_resume.refresh(project["id"])

        assert first["summary"] == second["summary"]
        assert first["open_questions"] == second["open_questions"] == []
        assert first["next_actions"] == second["next_actions"] == []


class TestResume:
    def test_resume_is_a_pure_read(self, fixture_repo):
        project = project_store.create("fixture", "code", paths=[str(fixture_repo)])
        project_resume.refresh(project["id"])

        resumed = project_resume.resume(project["id"])

        assert resumed["id"] == project["id"]
        assert resumed["name"] == "fixture"
        assert "sources" not in resumed

    def test_resume_missing_project_raises(self):
        with pytest.raises(project_store.ProjectNotFound):
            project_resume.resume(9999)

    def test_non_code_project_resume_has_zero_git_data(self):
        project = project_store.create("benefits", "admin")
        resumed = project_resume.resume(project["id"])
        assert resumed["kind"] == "admin"
        assert "git" not in resumed


def _empty_graph_result():
    from gateway.memory_graph import GraphResult

    return GraphResult()
