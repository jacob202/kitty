"""Tests for project_store — the projects registry (P6, docs/packets/021)."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from gateway import project_store


@pytest.fixture(autouse=True)
def isolate_project_store(monkeypatch, tmp_path):
    """Keep project tests away from live user data."""
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(project_store, "PROJECTS_DB_FILE", db_file, raising=False)


def test_init_seeds_kitty_as_project_one():
    project_store.init_db()
    projects = {p["name"]: p for p in project_store.list_projects()}
    assert "kitty" in projects
    assert projects["kitty"]["kind"] == "code"
    assert projects["kitty"]["paths"] == [str(project_store.PROJECT_ROOT)]


def test_init_seeds_benefits_admin_project():
    project_store.init_db()
    projects = {p["name"]: p for p in project_store.list_projects()}
    assert "benefits-admin" in projects
    assert projects["benefits-admin"]["kind"] == "admin"
    assert projects["benefits-admin"]["status"] == "active"


def test_seed_is_idempotent_across_repeated_init():
    project_store.init_db()
    project_store.init_db()
    project_store.init_db()
    projects = project_store.list_projects()
    assert len(projects) == 2
    assert {p["name"] for p in projects} == {"kitty", "benefits-admin"}


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


def test_delete_refuses_hard_deletion_and_preserves_project():
    project = project_store.create("keep history", "admin")

    with pytest.raises(project_store.ProjectDeletionDisabledError, match="archive"):
        project_store.delete(project["id"])

    assert project_store.get(project["id"])["status"] == "active"


def test_delete_on_fresh_database_migrates_then_returns_not_found():
    # The destructive entrypoint still distinguishes a missing project from a
    # real project whose hard deletion is deliberately unavailable.
    with pytest.raises(project_store.ProjectNotFound):
        project_store.delete(999999)


@pytest.fixture()
def todos(monkeypatch, tmp_path):
    """Point the todo store at the same isolated database as projects."""
    from gateway import todo_store

    monkeypatch.setattr(todo_store, "TODO_DB_FILE", tmp_path / "kitty" / "kitty.db")
    monkeypatch.setattr(todo_store, "TODO_DB", tmp_path / "legacy" / "todos.db")
    return todo_store


class TestSelectedTodo:
    """The one action the user chose outranks everything generated."""

    def test_selecting_a_todo_records_it_on_the_project(self, todos):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])

        updated = project_store.select_todo(project["id"], created[0]["id"])

        assert updated["selected_todo_id"] == created[0]["id"]
        assert project_store.selected_todo(project["id"])["content"] == "Send the application"

    def test_selecting_another_todo_replaces_the_choice(self, todos):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "First"}, {"content": "Second"}])
        project_store.select_todo(project["id"], created[0]["id"])

        project_store.select_todo(project["id"], created[1]["id"])

        assert project_store.selected_todo(project["id"])["content"] == "Second"

    def test_regenerating_suggestions_never_disturbs_the_selection(self, todos):
        """P4 acceptance 4: explicit priority beats generated suggestions."""
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])
        chosen = created[0]["id"]
        project_store.select_todo(project["id"], chosen)
        todos.set_progress(chosen, "attached the resume")

        # The model regenerates the list and the project's mechanical actions.
        todos.update([
            {"content": "Tidy the desk"},
            {"content": "Send the application"},
            {"content": "Read the news"},
        ])
        project_store.update_fields(project["id"], next_actions_json=["something else"])

        still = project_store.selected_todo(project["id"])
        assert still["id"] == chosen
        assert still["progress_note"] == "attached the resume"

    def test_a_deleted_todo_clears_the_pointer_instead_of_dangling(self, todos):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])
        project_store.select_todo(project["id"], created[0]["id"])

        todos.delete_by_id(created[0]["id"])

        assert project_store.selected_todo(project["id"]) is None
        assert project_store.get(project["id"])["selected_todo_id"] is None

    def test_selecting_a_todo_that_does_not_exist_is_refused(self, todos):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")

        with pytest.raises(project_store.ProjectNotFound):
            project_store.select_todo(project["id"], 4242)

    def test_clearing_the_selection_leaves_the_todo_alone(self, todos):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])
        project_store.select_todo(project["id"], created[0]["id"])

        project_store.clear_selected_todo(project["id"])

        assert project_store.selected_todo(project["id"]) is None
        assert [t["content"] for t in todos.get()] == ["Send the application"]

    def test_a_project_with_no_selection_reports_none(self):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")

        assert project["selected_todo_id"] is None
        assert project_store.selected_todo(project["id"]) is None


class TestSelectionGuards:
    def test_regeneration_that_omits_the_selected_todo_does_not_delete_it(self, todos):
        """P4: new suggestions cannot replace the action the user chose."""
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])
        chosen = created[0]["id"]
        project_store.select_todo(project["id"], chosen)
        todos.set_progress(chosen, "attached the resume")

        # The model regenerates a list that does not mention the chosen item.
        todos.update([{"content": "Tidy the desk"}, {"content": "Read the news"}])

        survivor = project_store.selected_todo(project["id"])
        assert survivor is not None
        assert survivor["id"] == chosen
        assert survivor["progress_note"] == "attached the resume"

    def test_explicit_deletion_still_removes_a_selected_todo(self, todos):
        """Protection is against a sweep, not against the user saying delete."""
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])
        project_store.select_todo(project["id"], created[0]["id"])

        assert todos.delete_by_id(created[0]["id"]) is True
        assert project_store.selected_todo(project["id"]) is None

    def test_a_todo_owned_by_another_project_cannot_be_stolen(self, todos):
        project_store.init_db()
        mine = project_store.create(name="job-search", kind="admin")
        theirs = project_store.create(name="benefits", kind="admin")
        created = todos.update([{"content": "Send the application"}])
        project_store.select_todo(theirs["id"], created[0]["id"])

        with pytest.raises(project_store.ProjectError, match="belongs to project"):
            project_store.select_todo(mine["id"], created[0]["id"])

    def test_selecting_an_unowned_todo_adopts_it_into_the_project(self, todos):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])

        project_store.select_todo(project["id"], created[0]["id"])

        assert project_store.selected_todo(project["id"])["project_id"] == project["id"]

    def test_a_completed_todo_cannot_be_the_next_action(self, todos):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])
        todos.complete_by_id(created[0]["id"])

        with pytest.raises(project_store.ProjectError, match="is completed and cannot be"):
            project_store.select_todo(project["id"], created[0]["id"])

    def test_a_boolean_is_never_treated_as_todo_id_one(self, todos):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        todos.update([{"content": "Send the application"}])

        with pytest.raises(project_store.ProjectError, match="must be int"):
            project_store.select_todo(project["id"], True)


class TestSelectionStaysHonest:
    def test_a_failing_projects_store_refuses_the_update_rather_than_deleting(
        self, todos, monkeypatch
    ):
        """Failing open here would destroy the chosen action exactly when
        the projects store is unhealthy."""
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])
        project_store.select_todo(project["id"], created[0]["id"])

        healthy = project_store.init_db

        def _broken():
            raise RuntimeError("projects store unavailable")

        monkeypatch.setattr(project_store, "init_db", _broken)

        with pytest.raises(todos.TodoStoreError, match="without reading project selections"):
            todos.update([{"content": "Something else entirely"}])

        # Nothing was deleted. Restore only this patch — monkeypatch.undo()
        # would also revert the autouse store isolation.
        monkeypatch.setattr(project_store, "init_db", healthy)
        assert project_store.selected_todo(project["id"])["id"] == created[0]["id"]

    def test_stale_repair_cannot_clear_a_newer_selection(self, todos, monkeypatch):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Old"}, {"content": "New"}])
        old_id, new_id = created[0]["id"], created[1]["id"]
        project_store.select_todo(project["id"], old_id)
        real_get = todos.get

        def replace_selection_during_read():
            project_store.select_todo(project["id"], new_id)
            return [todo for todo in real_get() if todo["id"] != old_id]

        monkeypatch.setattr(todos, "get", replace_selection_during_read)

        assert project_store.selected_todo(project["id"]) is None
        assert project_store.get(project["id"])["selected_todo_id"] == new_id

    def test_two_projects_cannot_both_claim_one_unowned_todo(self, todos):
        project_store.init_db()
        first = project_store.create(name="first", kind="admin")
        second = project_store.create(name="second", kind="admin")
        todo_id = todos.update([{"content": "One action"}])[0]["id"]

        def choose(project_id):
            try:
                project_store.select_todo(project_id, todo_id)
                return "selected"
            except project_store.ProjectError:
                return "refused"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(choose, [first["id"], second["id"]]))

        assert sorted(results) == ["refused", "selected"]
        owner = todos.get()[0]["project_id"]
        assert owner in {first["id"], second["id"]}
        loser = second if owner == first["id"] else first
        assert project_store.get(loser["id"])["selected_todo_id"] is None

    def test_refresh_and_selection_cannot_leave_a_dangling_choice(
        self, todos, monkeypatch
    ):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Choose me"}, {"content": "Keep me"}])
        target_id = created[0]["id"]
        update_has_lock = Event()
        selector_started = Event()
        real_match = todos._match_existing_todo

        def pause_with_update_lock(*args, **kwargs):
            update_has_lock.set()
            assert selector_started.wait(timeout=5)
            return real_match(*args, **kwargs)

        monkeypatch.setattr(todos, "_match_existing_todo", pause_with_update_lock)

        def refresh():
            todos.update([{"content": "Keep me"}])

        def select():
            assert update_has_lock.wait(timeout=5)
            selector_started.set()
            try:
                project_store.select_todo(project["id"], target_id)
                return "selected"
            except project_store.ProjectNotFound:
                return "refused"

        with ThreadPoolExecutor(max_workers=2) as pool:
            refresh_future = pool.submit(refresh)
            select_future = pool.submit(select)
            refresh_future.result(timeout=10)
            assert select_future.result(timeout=10) == "refused"

        assert project_store.get(project["id"])["selected_todo_id"] is None
        assert all(todo["id"] != target_id for todo in todos.get())

    def test_completing_the_selected_todo_clears_it_as_the_next_action(self, todos):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])
        project_store.select_todo(project["id"], created[0]["id"])

        todos.complete_by_id(created[0]["id"])

        assert project_store.selected_todo(project["id"]) is None
        assert project_store.get(project["id"])["selected_todo_id"] is None
        # The todo itself survives as history.
        assert todos.get()[0]["status"] == "completed"

    def test_a_todo_reassigned_to_another_project_stops_being_the_selection(self, todos):
        project_store.init_db()
        mine = project_store.create(name="job-search", kind="admin")
        theirs = project_store.create(name="benefits", kind="admin")
        created = todos.update([{"content": "Send the application"}])
        project_store.select_todo(mine["id"], created[0]["id"])

        todos.set_project(created[0]["id"], theirs["id"])

        assert project_store.selected_todo(mine["id"]) is None


class TestSelectionEdges:
    def test_a_deprioritized_todo_is_not_a_next_action(self, todos):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Maybe later", "status": "deprioritized"}])

        with pytest.raises(project_store.ProjectError, match="deprioritized"):
            project_store.select_todo(project["id"], created[0]["id"])

    def test_deprioritizing_the_selection_clears_it(self, todos):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])
        project_store.select_todo(project["id"], created[0]["id"])

        todos.update([{"id": created[0]["id"], "content": "Send the application",
                       "status": "deprioritized"}])

        assert project_store.selected_todo(project["id"]) is None

    def test_explicitly_unassigning_the_project_clears_the_selection(self, todos):
        """/todos/{id}/project accepts null; an unowned todo is not ours."""
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])
        project_store.select_todo(project["id"], created[0]["id"])

        todos.set_project(created[0]["id"], None)

        assert project_store.selected_todo(project["id"]) is None

    def test_a_preserved_todo_gets_a_position_of_its_own(self, todos):
        """Duplicate sort_order would make complete(index) finish several rows."""
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])
        project_store.select_todo(project["id"], created[0]["id"])

        todos.update([{"content": "Tidy the desk"}, {"content": "Read the news"}])

        orders = [t["sort_order"] for t in todos.get()]
        assert len(orders) == len(set(orders)), f"duplicate sort_order: {orders}"
        survivor = next(t for t in todos.get() if t["id"] == created[0]["id"])
        assert survivor["sort_order"] == 2

    def test_adoption_and_selection_land_together(self, todos, monkeypatch):
        project_store.init_db()
        project = project_store.create(name="job-search", kind="admin")
        created = todos.update([{"content": "Send the application"}])

        project_store.select_todo(project["id"], created[0]["id"])

        chosen = project_store.selected_todo(project["id"])
        assert chosen["project_id"] == project["id"]
        assert project_store.get(project["id"])["selected_todo_id"] == created[0]["id"]
