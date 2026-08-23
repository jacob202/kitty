"""Tests for project_resume — refresh()/resume() composer (P6, docs/packets/021).

Git composition is tested against a real fixture repo (tmp_path + git init +
real commits), not a mocked subprocess — proves the actual git invocations
work, not just that they were called.
"""
import subprocess
from typing import Any

import pytest

from gateway import artifact_store, builder_initiative, builder_queue, project_resume, project_store


@pytest.fixture(autouse=True)
def isolate_project_store(monkeypatch, tmp_path):
    # Both project_store and artifact_store point at the same physical
    # kitty.db in production (both derive from paths.KITTY_DB_FILE), so
    # isolating tests means patching both module-level constants to the
    # same tmp_path file — otherwise artifact_store would fall through
    # to the real on-disk database.
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(project_store, "PROJECTS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(artifact_store, "ARTIFACTS_DB_FILE", db_file, raising=False)
    # _work_source() reaches build_status_snapshot() with no db_path override,
    # which funnels through builder_queue.connect()/init_db() to this constant
    # — patch it too, or resume() tests would read/init the real Builder queue.
    monkeypatch.setattr(builder_queue, "BUILDER_QUEUE_DB", tmp_path / "kitty" / "builder_queue.db", raising=False)


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


def _register_artifact(tmp_path, *, project_id, name="file.txt", kind="text"):
    """Create a real artifact row against the isolated test DB."""
    src = tmp_path / name
    src.write_text(f"content for {name}", encoding="utf-8")
    return artifact_store.register_file(
        src,
        kind=kind,
        media_type="text/plain",
        project_id=project_id,
        created_by="test",
    )


class TestArtifactSource:
    def test_resume_returns_project_artifacts(self, tmp_path):
        project = project_store.create("with-artifacts", "admin")
        registered = _register_artifact(tmp_path, project_id=project["id"])

        resumed = project_resume.resume(project["id"])

        assert len(resumed["artifacts"]) == 1
        entry = resumed["artifacts"][0]
        assert entry["id"] == registered["id"]
        assert entry["kind"] == "text"
        assert entry["display_name"] == "file.txt"
        assert entry["state"] == "ready"
        assert entry["created_at"] == registered["created_at"]
        assert entry["media_type"] == "text/plain"
        assert entry["size_bytes"] == registered["size_bytes"]

    def test_resume_bounds_artifacts_to_the_limit(self, tmp_path, monkeypatch):
        monkeypatch.setattr(project_resume, "ARTIFACT_LIMIT", 3)
        project = project_store.create("many-artifacts", "admin")
        for i in range(5):
            _register_artifact(tmp_path, project_id=project["id"], name=f"file{i}.txt")

        resumed = project_resume.resume(project["id"])

        assert len(resumed["artifacts"]) == 3

    def test_project_with_zero_artifacts_returns_empty_list(self):
        project = project_store.create("no-artifacts", "admin")

        resumed = project_resume.resume(project["id"])

        assert resumed["artifacts"] == []

    def test_artifacts_are_scoped_to_the_requesting_project(self, tmp_path):
        project_a = project_store.create("project-a", "admin")
        project_b = project_store.create("project-b", "admin")
        _register_artifact(tmp_path, project_id=project_a["id"], name="a.txt")
        _register_artifact(tmp_path, project_id=project_b["id"], name="b.txt")

        resumed_a = project_resume.resume(project_a["id"])
        resumed_b = project_resume.resume(project_b["id"])

        assert [a["display_name"] for a in resumed_a["artifacts"]] == ["a.txt"]
        assert [a["display_name"] for a in resumed_b["artifacts"]] == ["b.txt"]


def _init_repo(tmp_path, name="repo"):
    repo = tmp_path / name
    repo.mkdir()
    for args in (
        ["git", "init"],
        ["git", "config", "user.email", "tests@example.invalid"],
        ["git", "config", "user.name", "Project Resume Tests"],
    ):
        subprocess.run(args, cwd=repo, check=True, capture_output=True, text=True)
    (repo / "README.md").write_text("# test repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True
    )
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True, capture_output=True, text=True)
    return repo


def _apply_initiative(tmp_path, *, initiative_id, project_id):
    manifest = {
        "manifest_version": 1,
        "initiative_id": initiative_id,
        "title": f"Work source test initiative {initiative_id}",
        "packets": [
            {
                "id": f"{initiative_id}-P1",
                "title": "Test packet",
                "objective": "Exercise the work source.",
                "acceptance_criteria": ["N/A"],
                "allowed_paths": ["gateway/project_resume.py"],
            }
        ],
    }
    repo = _init_repo(tmp_path, name=f"repo-{initiative_id}")
    builder_initiative.apply_manifest(manifest, repo_root=repo, project_id=project_id)


class TestWorkSource:
    def test_resume_returns_work_for_the_projects_own_initiative(self, tmp_path):
        project = project_store.create("with-work", "code")
        _apply_initiative(tmp_path, initiative_id="wk-a", project_id=project["id"])

        resumed = project_resume.resume(project["id"])

        assert [item["id"] for item in resumed["work"]["items"]] == ["wk-a"]

    def test_work_is_scoped_to_the_requesting_project(self, tmp_path):
        project_a = project_store.create("project-a-work", "code")
        project_b = project_store.create("project-b-work", "code")
        _apply_initiative(tmp_path, initiative_id="wk-scope-a", project_id=project_a["id"])
        _apply_initiative(tmp_path, initiative_id="wk-scope-b", project_id=project_b["id"])

        resumed_a = project_resume.resume(project_a["id"])
        resumed_b = project_resume.resume(project_b["id"])

        assert [item["id"] for item in resumed_a["work"]["items"]] == ["wk-scope-a"]
        assert [item["id"] for item in resumed_b["work"]["items"]] == ["wk-scope-b"]

    def test_project_with_zero_initiatives_returns_empty_work(self):
        project = project_store.create("no-work", "code")

        resumed = project_resume.resume(project["id"])

        assert resumed["work"]["items"] == []
        assert resumed["work"]["total_items"] == 0

    def test_artifact_store_failure_does_not_crash_resume(self, tmp_path, monkeypatch):
        project = project_store.create("flaky-artifacts", "admin")
        _register_artifact(tmp_path, project_id=project["id"])

        def boom(*, project_id=None, conversation_id=None, kind=None, limit=100):
            raise RuntimeError("artifact store exploded")

        monkeypatch.setattr(artifact_store, "list_artifacts", boom)

        resumed = project_resume.resume(project["id"])

        assert resumed["artifacts"] == []
        assert resumed["id"] == project["id"]

    def test_resume_with_artifacts_is_still_a_pure_read(self, tmp_path, monkeypatch):
        project = project_store.create("pure-read-check", "admin")
        _register_artifact(tmp_path, project_id=project["id"])

        calls: list[Any] = []
        monkeypatch.setattr(
            project_store,
            "update_fields",
            lambda *a, **kw: calls.append((a, kw)) or pytest.fail("resume() must not mutate the project row"),
        )

        resumed = project_resume.resume(project["id"])

        assert calls == []
        assert len(resumed["artifacts"]) == 1


def _empty_graph_result():
    from gateway.memory_graph import GraphResult

    return GraphResult()
