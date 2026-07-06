"""Tests for project_store — the projects registry (P6, docs/packets/021)."""
import pytest

from gateway import project_store


@pytest.fixture(autouse=True)
def isolate_project_store(monkeypatch, tmp_path):
    """Keep project tests away from live user data."""
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(project_store, "PROJECTS_DB_FILE", db_file, raising=False)


def test_init_seeds_kitty_as_project_one():
    project_store.init_db()
    projects = project_store.list_projects()
    assert len(projects) == 1
    assert projects[0]["name"] == "kitty"
    assert projects[0]["kind"] == "code"
    assert projects[0]["paths"] == [str(project_store.PROJECT_ROOT)]


def test_seed_is_idempotent_across_repeated_init():
    project_store.init_db()
    project_store.init_db()
    project_store.init_db()
    assert len(project_store.list_projects()) == 1


def test_create_returns_project_with_id():
    project = project_store.create("benefits paperwork", "admin")
    assert project["id"] > 0
    assert project["name"] == "benefits paperwork"
    assert project["kind"] == "admin"
    assert project["paths"] == []
    assert project["status"] == "active"
    assert project["summary"] == ""
    assert project["open_questions"] == []
    assert project["next_actions"] == []


def test_create_with_paths_and_links():
    project = project_store.create(
        "car repair", "admin", paths=["/tmp/notes"], links=[{"label": "quote", "url": "https://x"}]
    )
    assert project["paths"] == ["/tmp/notes"]
    assert project["links"] == [{"label": "quote", "url": "https://x"}]


def test_get_missing_returns_none():
    assert project_store.get(9999) is None


def test_list_projects_filters_by_status():
    a = project_store.create("a", "code")
    project_store.create("b", "code")
    project_store.update_fields(a["id"], status="archived")

    active = project_store.list_projects(status="active")
    archived = project_store.list_projects(status="archived")

    assert a["id"] not in [p["id"] for p in active]
    assert a["id"] in [p["id"] for p in archived]


def test_update_fields_persists_json_fields():
    project = project_store.create("x", "code")
    updated = project_store.update_fields(
        project["id"],
        summary="on track",
        open_questions_json=["what about Y?"],
        next_actions_json=["ship the thing"],
    )
    assert updated["summary"] == "on track"
    assert updated["open_questions"] == ["what about Y?"]
    assert updated["next_actions"] == ["ship the thing"]


def test_update_fields_rejects_unknown_field():
    project = project_store.create("x", "code")
    with pytest.raises(project_store.ProjectError):
        project_store.update_fields(project["id"], not_a_real_field="oops")


def test_update_fields_raises_not_found_for_missing_project():
    with pytest.raises(project_store.ProjectNotFound):
        project_store.update_fields(9999, summary="x")


def test_touch_bumps_last_touched():
    project = project_store.create("x", "code")
    assert project["last_touched"] is None
    project_store.touch(project["id"])
    touched = project_store.get(project["id"])
    assert touched["last_touched"] is not None
