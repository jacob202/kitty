"""Tests for durable conversational image sessions (issue #336, slice A1).

Covers the A1 acceptance list: session create/resume, anchor selection, parent
lineage, unknown-reference rejection, and restart-resume proven by reopening
the store.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gateway import image_jobs as jobs
from gateway import image_sessions as sessions
from gateway.image_jobs import ImageJobStatus
from gateway.image_sessions import (
    AnchorError,
    ImageSessionError,
    ImageSessionStatus,
    SessionEndedError,
    SessionNotFoundError,
    TurnRole,
)


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path):
    test_db = tmp_path / "kitty.db"
    test_db.parent.mkdir(parents=True, exist_ok=True)
    import gateway.paths as gp

    original = gp.KITTY_DB_FILE
    gp.KITTY_DB_FILE = test_db

    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    sessions._ensure_db(conn)
    conn.commit()
    conn.close()

    yield test_db

    gp.KITTY_DB_FILE = original


def _succeeded_job(output_path: str = "/tmp/out.png", artifact_id: str = "art_1"):
    """A job in the only state that may become an anchor."""
    job = jobs.create_job("comfyui", "txt2img", prompt="a portrait")
    jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
    jobs.transition(job.job_id, ImageJobStatus.RUNNING)
    jobs.update_job(job.job_id, output_path=output_path, artifact_id=artifact_id)
    return jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)


class TestCreateAndResume:
    def test_create_returns_active_session_with_defaults(self):
        s = sessions.create_session(title="James portraits")
        assert s.status is ImageSessionStatus.ACTIVE
        assert s.title == "James portraits"
        assert s.anchor_job_id is None
        assert s.spend_usd == 0.0
        assert s.attempt_count == 0
        assert s.session_id.startswith("imgses_")

    def test_get_session_returns_none_for_unknown_id(self):
        assert sessions.get_session("imgses_nope") is None

    def test_require_session_raises_for_unknown_id(self):
        with pytest.raises(SessionNotFoundError, match="imgses_nope"):
            sessions.require_session("imgses_nope")

    def test_session_survives_store_reopen(self):
        """Restart-resume: a new connection must see the same session state."""
        s = sessions.create_session(
            title="resume me",
            character_id="char_james",
            reference_ids=["ref_a", "ref_b"],
            protected_traits=["face", "apparent age"],
        )
        sessions.append_turn(s.session_id, TurnRole.USER, "make him broader")

        # Every call opens its own connection, so re-reading through a fresh
        # one is what "restart Kitty and continue" actually exercises.
        resumed = sessions.require_session(s.session_id)
        assert resumed.title == "resume me"
        assert resumed.character_id == "char_james"
        assert resumed.reference_ids == ["ref_a", "ref_b"]
        assert resumed.protected_traits == ["face", "apparent age"]

        turns = sessions.list_turns(s.session_id)
        assert [t.content for t in turns] == ["make him broader"]

    def test_list_sessions_filters_by_status(self):
        active = sessions.create_session(title="active")
        ended = sessions.create_session(title="ended")
        sessions.end_session(ended.session_id)

        ids = {s.session_id for s in sessions.list_sessions(status=ImageSessionStatus.ACTIVE)}
        assert active.session_id in ids
        assert ended.session_id not in ids


class TestTurns:
    def test_turns_get_dense_increasing_sequence(self):
        s = sessions.create_session()
        first = sessions.append_turn(s.session_id, TurnRole.USER, "one")
        second = sessions.append_turn(s.session_id, TurnRole.ASSISTANT, "two")
        third = sessions.append_turn(s.session_id, "user", "three")
        assert [first.seq, second.seq, third.seq] == [1, 2, 3]

    def test_turns_are_returned_in_conversation_order(self):
        s = sessions.create_session()
        for text in ("a", "b", "c"):
            sessions.append_turn(s.session_id, TurnRole.USER, text)
        assert [t.content for t in sessions.list_turns(s.session_id)] == ["a", "b", "c"]

    def test_turn_sequences_are_scoped_per_session(self):
        one = sessions.create_session()
        two = sessions.create_session()
        sessions.append_turn(one.session_id, TurnRole.USER, "in one")
        turn = sessions.append_turn(two.session_id, TurnRole.USER, "in two")
        assert turn.seq == 1

    def test_turn_rejects_unknown_job_id(self):
        s = sessions.create_session()
        with pytest.raises(ImageSessionError, match="job_nope"):
            sessions.append_turn(s.session_id, TurnRole.ASSISTANT, "done", job_id="job_nope")

    def test_turn_rejects_unknown_session(self):
        with pytest.raises(SessionNotFoundError):
            sessions.append_turn("imgses_nope", TurnRole.USER, "hello")

    def test_appending_a_turn_advances_updated_at(self):
        s = sessions.create_session()
        sessions.append_turn(s.session_id, TurnRole.USER, "hello")
        assert sessions.require_session(s.session_id).updated_at >= s.updated_at


class TestAnchor:
    def test_succeeded_job_with_artifact_becomes_anchor(self):
        s = sessions.create_session()
        job = _succeeded_job(artifact_id="art_42")
        updated = sessions.set_anchor(s.session_id, job.job_id)
        assert updated.anchor_job_id == job.job_id
        assert updated.anchor_artifact_id == "art_42"

    def test_unknown_job_is_rejected(self):
        s = sessions.create_session()
        with pytest.raises(AnchorError, match="job_nope"):
            sessions.set_anchor(s.session_id, "job_nope")

    def test_unfinished_job_is_rejected(self):
        """An anchor that cannot be fed to a renderer must fail at selection."""
        s = sessions.create_session()
        job = jobs.create_job("comfyui", "txt2img", prompt="wip")
        with pytest.raises(AnchorError, match="only a succeeded job"):
            sessions.set_anchor(s.session_id, job.job_id)

    def test_job_store_prevents_artifactless_success(self):
        """set_anchor's artifact check is defence in depth — the job store gets there first.

        A succeeded-but-artifactless job is what would let a "follow-up edit"
        silently become a fresh reroll. image_jobs.transition already refuses to
        create that state, so the anchor path can rely on it; this test pins that
        upstream guarantee so removing it fails here rather than surfacing later
        as an unexplained reroll.
        """
        job = jobs.create_job("comfyui", "txt2img", prompt="no output")
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        with pytest.raises(jobs.ImageJobError, match="no artifact_id or output_path"):
            jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)

    def test_clear_anchor_returns_session_to_fresh_generation(self):
        s = sessions.create_session()
        job = _succeeded_job()
        sessions.set_anchor(s.session_id, job.job_id)
        cleared = sessions.clear_anchor(s.session_id)
        assert cleared.anchor_job_id is None
        assert cleared.anchor_artifact_id is None

    def test_anchor_survives_store_reopen(self):
        s = sessions.create_session()
        job = _succeeded_job(artifact_id="art_persist")
        sessions.set_anchor(s.session_id, job.job_id)
        assert sessions.require_session(s.session_id).anchor_artifact_id == "art_persist"


class TestLineage:
    def test_follow_up_job_records_anchor_as_parent(self):
        """The two-turn shape from issue #336: second job descends from the first."""
        s = sessions.create_session()
        first = _succeeded_job()
        sessions.set_anchor(s.session_id, first.job_id)

        anchor = sessions.require_session(s.session_id).anchor_job_id
        second = jobs.create_job("comfyui", "img2img", prompt="broader build", parent_id=anchor)

        assert second.parent_id == first.job_id
        assert [c.job_id for c in jobs.list_children(first.job_id)] == [second.job_id]

    def test_attach_job_links_job_to_session(self):
        s = sessions.create_session()
        job = jobs.create_job("comfyui", "txt2img", prompt="one")
        sessions.attach_job(s.session_id, job.job_id)
        assert [j.job_id for j in sessions.list_session_jobs(s.session_id)] == [job.job_id]

    def test_attach_job_rejects_unknown_job(self):
        s = sessions.create_session()
        with pytest.raises(ImageSessionError, match="job_nope"):
            sessions.attach_job(s.session_id, "job_nope")

    def test_session_jobs_exclude_other_sessions(self):
        one = sessions.create_session()
        two = sessions.create_session()
        mine = jobs.create_job("comfyui", "txt2img", prompt="mine")
        theirs = jobs.create_job("comfyui", "txt2img", prompt="theirs")
        sessions.attach_job(one.session_id, mine.job_id)
        sessions.attach_job(two.session_id, theirs.job_id)
        assert [j.job_id for j in sessions.list_session_jobs(one.session_id)] == [mine.job_id]


class TestContextUpdates:
    def test_update_replaces_only_supplied_fields(self):
        s = sessions.create_session(title="keep me", character_id="char_james")
        updated = sessions.update_session(s.session_id, protected_traits=["face"])
        assert updated.title == "keep me"
        assert updated.character_id == "char_james"
        assert updated.protected_traits == ["face"]

    def test_clear_character_detaches_without_touching_other_fields(self):
        s = sessions.create_session(title="keep me", character_id="char_james")
        updated = sessions.update_session(s.session_id, clear_character=True)
        assert updated.character_id is None
        assert updated.title == "keep me"
        assert updated.protected_traits == []

    def test_last_plan_round_trips(self):
        s = sessions.create_session()
        plan = {"operation": "img2img", "refined_prompt": "broader build", "denoise": 0.4}
        updated = sessions.update_session(s.session_id, last_plan=plan)
        assert updated.last_plan == plan

    def test_last_plan_must_be_a_dict(self):
        s = sessions.create_session()
        with pytest.raises(ImageSessionError, match="last_plan must be a dict"):
            sessions.update_session(s.session_id, last_plan=["not", "a", "dict"])

    def test_empty_update_is_an_error_not_a_silent_noop(self):
        s = sessions.create_session()
        with pytest.raises(ImageSessionError, match="nothing to update"):
            sessions.update_session(s.session_id)

    def test_duplicate_references_are_rejected(self):
        with pytest.raises(ImageSessionError, match="duplicate entry"):
            sessions.create_session(reference_ids=["ref_a", "ref_a"])

    def test_blank_references_are_rejected(self):
        with pytest.raises(ImageSessionError, match="empty entries"):
            sessions.create_session(reference_ids=["ref_a", "   "])


class TestSpendAndLifecycle:
    def test_record_attempt_accumulates_count_and_cost(self):
        s = sessions.create_session()
        sessions.record_attempt(s.session_id, cost_usd=0.02)
        final = sessions.record_attempt(s.session_id, cost_usd=0.03)
        assert final.attempt_count == 2
        assert final.spend_usd == pytest.approx(0.05)

    def test_negative_cost_is_rejected(self):
        s = sessions.create_session()
        with pytest.raises(ImageSessionError, match="must not be negative"):
            sessions.record_attempt(s.session_id, cost_usd=-1.0)

    def test_end_session_marks_it_terminal(self):
        s = sessions.create_session()
        ended = sessions.end_session(s.session_id)
        assert ended.status is ImageSessionStatus.ENDED
        assert ended.ended_at is not None

    def test_ended_session_rejects_further_mutation(self):
        s = sessions.create_session()
        sessions.end_session(s.session_id)
        with pytest.raises(SessionEndedError):
            sessions.append_turn(s.session_id, TurnRole.USER, "still there?")

    def test_ending_twice_is_an_error_not_a_silent_noop(self):
        s = sessions.create_session()
        sessions.end_session(s.session_id)
        with pytest.raises(SessionEndedError):
            sessions.end_session(s.session_id)

    def test_ended_session_is_still_readable(self):
        """Ending closes the session to writes; the history stays inspectable."""
        s = sessions.create_session()
        sessions.append_turn(s.session_id, TurnRole.USER, "hello")
        sessions.end_session(s.session_id)
        assert [t.content for t in sessions.list_turns(s.session_id)] == ["hello"]


def _insert_project(db_file: Path, *, name: str = "Image project") -> int:
    migration = Path("gateway/migrations/010_projects.sql").read_text(encoding="utf-8")
    with sqlite3.connect(db_file) as conn:
        conn.executescript(migration)
        cur = conn.execute(
            "INSERT INTO projects (name, kind) VALUES (?, ?)", (name, "creative")
        )
        conn.commit()
        assert cur.lastrowid is not None
        return int(cur.lastrowid)


def test_session_project_scope_round_trips(_fresh_db):
    project_id = _insert_project(_fresh_db)
    created = sessions.create_session(title="project portraits", project_id=project_id)

    assert created.project_id == project_id
    assert sessions.require_session(created.session_id).project_id == project_id
    assert created.to_dict()["project_id"] == project_id


def test_session_project_scope_rejects_unknown_project(_fresh_db):
    _insert_project(_fresh_db)
    with pytest.raises(ImageSessionError, match="project"):
        sessions.create_session(project_id=999_999)
