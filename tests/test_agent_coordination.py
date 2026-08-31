from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import agent_coordination as ac

NOW = datetime(2026, 8, 31, 6, 30, tzinfo=timezone.utc)
SHA_A = "a" * 40
SHA_B = "b" * 40


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": 1,
        "lane_id": "chat-runtime",
        "event": "claim",
        "owner": "codex:chat-runtime",
        "execution_owner": "interactive",
        "lane": "Chat runtime reliability",
        "base_sha": SHA_A,
        "head_sha": SHA_A,
        "branch": "feat/chat-runtime",
        "worktree": "chat-runtime",
        "output": "PR TBD",
        "paths": ["gateway/routes/completions.py", "gateway/kitty-chat/**"],
        "status": "own",
        "claim_started_at": NOW.isoformat().replace("+00:00", "Z"),
        "recorded_at": NOW.isoformat().replace("+00:00", "Z"),
        "lease_until": (NOW + timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
    }
    base.update(overrides)
    return base

def test_structured_comment_round_trips() -> None:
    body = ac.render_event_comment(_payload())
    event = ac.parse_lane_comment(body, comment_id=17, github_created_at=NOW)

    assert event is not None
    assert event.comment_id == 17
    assert event.lane_id == "chat-runtime"
    assert event.paths == ("gateway/routes/completions.py", "gateway/kitty-chat/**")
    assert event.status == "own"


def test_invalid_claim_path_is_rejected() -> None:
    payload = _payload(paths=["../secrets", "/tmp/absolute"])
    with pytest.raises(ac.ProtocolError, match="repo-relative"):
        ac.validate_payload(payload)


def test_arbitrary_glob_syntax_is_rejected() -> None:
    with pytest.raises(ac.ProtocolError, match=r"only exact paths or /\*\*"):
        ac.validate_payload(_payload(paths=["gateway/*.py"]))


def test_interactive_lease_may_not_exceed_four_hours() -> None:
    with pytest.raises(ac.ProtocolError, match="four hours"):
        ac.validate_payload(
            _payload(
                lease_until=(NOW + timedelta(hours=5)).isoformat().replace("+00:00", "Z")
            )
        )


def test_latest_event_collapses_lane_and_release_is_terminal() -> None:
    first = ac.event_from_payload(_payload(), comment_id=1, github_created_at=NOW)
    released_at = NOW + timedelta(minutes=30)
    release = ac.event_from_payload(
        _payload(
            event="release",
            status="released",
            recorded_at=released_at.isoformat().replace("+00:00", "Z"),
            lease_until=None,
        ),
        comment_id=2,
        github_created_at=released_at,
    )

    states = ac.current_lane_states([first, release], now=NOW + timedelta(hours=1))

    assert states["chat-runtime"].status == "released"
    assert states["chat-runtime"].blocking is False

def test_expired_claim_is_stale_not_blocking() -> None:
    event = ac.event_from_payload(_payload(), comment_id=1, github_created_at=NOW)
    states = ac.current_lane_states([event], now=NOW + timedelta(hours=4))

    state = states["chat-runtime"]
    assert state.stale is True
    assert state.blocking is False


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("gateway/routes/completions.py", "gateway/routes/completions.py", True),
        ("gateway/**", "gateway/routes/completions.py", True),
        ("gateway/routes/**", "gateway/routes/completions.py", True),
        ("gateway/routes/**", "gateway/kitty-chat/**", False),
        ("scripts/a.py", "scripts/b.py", False),
    ],
)
def test_path_overlap_is_deterministic(left: str, right: str, expected: bool) -> None:
    assert ac.paths_overlap(left, right) is expected

def test_active_own_claim_blocks_overlapping_candidate() -> None:
    other = ac.event_from_payload(
        _payload(lane_id="other", branch="feat/other", paths=["scripts/**"]),
        comment_id=3,
        github_created_at=NOW,
    )
    states = ac.current_lane_states([other], now=NOW + timedelta(minutes=5))

    collisions = ac.detect_candidate_collisions(
        lane_id="mine",
        branch="feat/mine",
        paths=["scripts/new_tool.py"],
        states=states,
        external_scopes=(),
    )

    assert [(item.source_kind, item.source_id) for item in collisions] == [
        ("claim", "other")
    ]

def test_review_claim_does_not_block_implementation() -> None:
    review = ac.event_from_payload(
        _payload(lane_id="reviewer", status="review", paths=["scripts/**"]),
        comment_id=4,
        github_created_at=NOW,
    )
    states = ac.current_lane_states([review], now=NOW + timedelta(minutes=5))

    collisions = ac.detect_candidate_collisions(
        lane_id="mine",
        branch="feat/mine",
        paths=["scripts/new_tool.py"],
        states=states,
        external_scopes=(),
    )

    assert collisions == []


def test_open_pr_scope_blocks_candidate_but_own_branch_is_ignored() -> None:
    scope = ac.ExternalScope(
        kind="pull_request",
        source_id="#705",
        branch="feat/library-chat",
        paths=("gateway/routes/completions.py",),
    )
    blocked = ac.detect_candidate_collisions(
        lane_id="mine",
        branch="feat/mine",
        paths=["gateway/routes/completions.py"],
        states={},
        external_scopes=(scope,),
    )
    own = ac.detect_candidate_collisions(
        lane_id="mine",
        branch="feat/library-chat",
        paths=["gateway/routes/completions.py"],
        states={},
        external_scopes=(scope,),
    )

    assert blocked[0].source_id == "#705"
    assert own == []


def test_builder_allowed_paths_are_collision_evidence() -> None:
    scope = ac.ExternalScope(
        kind="builder",
        source_id="KITTY-RECOVERY-001/PACKET-01",
        branch=None,
        paths=("gateway/health_surface.py",),
    )
    collisions = ac.detect_candidate_collisions(
        lane_id="mine",
        branch="feat/mine",
        paths=["gateway/health_surface.py"],
        states={},
        external_scopes=(scope,),
    )

    assert collisions[0].source_kind == "builder"


def test_registry_race_reports_earliest_claim_as_winner() -> None:
    early = ac.event_from_payload(
        _payload(lane_id="early", paths=["gateway/**"]),
        comment_id=10,
        github_created_at=NOW,
    )
    later_time = NOW + timedelta(minutes=1)
    late = ac.event_from_payload(
        _payload(
            lane_id="late",
            paths=["gateway/routes/completions.py"],
            claim_started_at=later_time.isoformat().replace("+00:00", "Z"),
            recorded_at=later_time.isoformat().replace("+00:00", "Z"),
            lease_until=(later_time + timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
        ),
        comment_id=11,
        github_created_at=later_time,
    )
    states = ac.current_lane_states([late, early], now=NOW + timedelta(minutes=2))
    conflicts = ac.registry_collisions(states)

    assert len(conflicts) == 1
    assert conflicts[0].winner_lane_id == "early"
    assert conflicts[0].loser_lane_id == "late"


def test_legacy_prose_comment_is_ignored() -> None:
    assert ac.parse_lane_comment(
        "OWNER: somebody\nLANE: prose only",
        comment_id=99,
        github_created_at=NOW,
    ) is None


def test_malformed_structured_comment_fails_loud() -> None:
    body = "<!-- kitty-lane:v1 {not-json} -->"
    with pytest.raises(ac.ProtocolError, match="invalid JSON"):
        ac.parse_lane_comment(body, comment_id=5, github_created_at=NOW)


def test_github_comment_extraction_preserves_malformed_marker_as_gap() -> None:
    good = ac.render_event_comment(_payload())
    comments = [
        {"id": 1, "created_at": "2026-08-31T06:30:00Z", "body": good},
        {"id": 2, "created_at": "2026-08-31T06:31:00Z", "body": "ordinary prose"},
        {"id": 3, "created_at": "2026-08-31T06:32:00Z", "body": "<!-- kitty-lane:v1 {bad} -->"},
    ]

    events, gaps = ac.extract_events_from_github_comments(comments)

    assert [event.comment_id for event in events] == [1]
    assert len(gaps) == 1
    assert gaps[0].source == "github_comment:#3"
    assert "invalid JSON" in gaps[0].reason


def test_parse_worktree_porcelain_keeps_branch_and_detached_identity() -> None:
    text = """worktree /repo\nHEAD aaaaa\nbranch refs/heads/main\n\nworktree /repo/wt\nHEAD bbbbb\ndetached\n"""
    records = ac.parse_worktree_porcelain(text)

    assert records[0].path == "/repo"
    assert records[0].branch == "main"
    assert records[1].branch is None
    assert records[1].detached is True


def test_builder_scope_projection_reads_only_active_task_paths(tmp_path) -> None:
    import sqlite3

    db = tmp_path / "builder.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE tasks (id TEXT, state TEXT, allowed_paths_json TEXT, "
        "lease_owner TEXT, lease_expires_at TEXT)"
    )
    conn.execute(
        "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
        ("run-1", "running", '["gateway/health_surface.py"]', "worker-a", "2026-08-31T07:00:00Z"),
    )
    conn.execute(
        "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
        ("queued-1", "queued", '["gateway/routes/completions.py"]', None, None),
    )
    conn.commit()
    conn.close()

    scopes, gap = ac.builder_scopes_from_db(db)

    assert gap is None
    assert [(scope.source_id, scope.paths) for scope in scopes] == [
        ("run-1", ("gateway/health_surface.py/**",))
    ]


def test_builder_corrupt_allowed_paths_becomes_evidence_gap(tmp_path) -> None:
    import sqlite3

    db = tmp_path / "builder.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE tasks (id TEXT, state TEXT, allowed_paths_json TEXT, "
        "lease_owner TEXT, lease_expires_at TEXT)"
    )
    conn.execute(
        "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
        ("run-1", "running", "not-json", "worker-a", "2026-08-31T07:00:00Z"),
    )
    conn.commit()
    conn.close()

    scopes, gap = ac.builder_scopes_from_db(db)

    assert scopes == []
    assert gap is not None
    assert gap.source == "builder"
    assert "allowed_paths_json" in gap.reason


def test_claim_payload_binds_exact_local_identity() -> None:
    identity = ac.RepoIdentity(
        base_sha=SHA_A,
        head_sha=SHA_B,
        branch="feat/coord",
        worktree="agent-coordination-registry-20260831",
    )
    payload = ac.build_claim_payload(
        lane_id="coord-registry",
        owner="chatgpt:thread-master",
        lane="Coordination registry",
        output="PR TBD",
        paths=["scripts/agent_coordination.py", "tests/test_agent_coordination.py"],
        identity=identity,
        now=NOW,
        lease_minutes=180,
    )

    assert payload["base_sha"] == SHA_A
    assert payload["head_sha"] == SHA_B
    assert payload["branch"] == "feat/coord"
    assert payload["lease_until"] == "2026-08-31T09:30:00Z"


def test_publish_claim_refuses_unknown_coordination_state_without_writing() -> None:
    payload = _payload(lane_id="mine", branch="feat/mine", paths=["scripts/**"])
    calls: list[list[str]] = []

    def runner(args, *, cwd=None, timeout=30):
        calls.append(list(args))
        return ac.CommandResult(0, '{"id": 1}', "")

    with pytest.raises(ac.EvidenceUnavailableError, match="github"):
        ac.publish_claim(
            payload,
            states={},
            external_scopes=(),
            evidence_gaps=(ac.EvidenceGap("github", "unavailable"),),
            repo="jacob202/kitty",
            issue=490,
            post=True,
            runner=runner,
        )

    assert calls == []


def test_publish_claim_refuses_collision_without_writing() -> None:
    other = ac.event_from_payload(
        _payload(lane_id="other", branch="feat/other", paths=["scripts/**"]),
        comment_id=3,
        github_created_at=NOW,
    )
    states = ac.current_lane_states([other], now=NOW + timedelta(minutes=5))
    calls: list[list[str]] = []

    def runner(args, *, cwd=None, timeout=30):
        calls.append(list(args))
        return ac.CommandResult(0, '{"id": 1}', "")

    with pytest.raises(ac.CollisionError, match="other"):
        ac.publish_claim(
            _payload(lane_id="mine", branch="feat/mine", paths=["scripts/new.py"]),
            states=states,
            external_scopes=(),
            evidence_gaps=(),
            repo="jacob202/kitty",
            issue=490,
            post=True,
            runner=runner,
        )

    assert calls == []


def test_publish_claim_posts_canonical_comment_after_clean_preflight() -> None:
    calls: list[list[str]] = []

    def runner(args, *, cwd=None, timeout=30):
        calls.append(list(args))
        if args[:4] == ["gh", "api", "-X", "POST"]:
            return ac.CommandResult(0, '{"id": 42}', "")
        if args[:3] == ["gh", "api", "--paginate"]:
            comment = {
                "id": 42,
                "created_at": "2026-08-31T06:30:01Z",
                "body": ac.render_event_comment(_payload(lane_id="mine", branch="feat/mine", paths=["scripts/new.py"])),
            }
            return ac.CommandResult(0, __import__("json").dumps([[comment]]), "")
        raise AssertionError(args)

    result = ac.publish_claim(
        _payload(lane_id="mine", branch="feat/mine", paths=["scripts/new.py"]),
        states={},
        external_scopes=(),
        evidence_gaps=(),
        repo="jacob202/kitty",
        issue=490,
        post=True,
        runner=runner,
    )

    assert result["posted"] is True
    assert result["comment_id"] == 42
    assert calls and calls[0][:4] == ["gh", "api", "-X", "POST"]
    assert "kitty-lane:v1" in calls[0][-1]


def test_builder_task_without_allowlist_is_repo_wide_collision(tmp_path) -> None:
    import sqlite3

    db = tmp_path / "builder.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE tasks (id TEXT, state TEXT, allowed_paths_json TEXT, "
        "lease_owner TEXT, lease_expires_at TEXT)"
    )
    conn.execute(
        "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
        ("run-anywhere", "running", None, "worker-a", "2026-08-31T07:00:00Z"),
    )
    conn.commit()
    conn.close()

    scopes, gap = ac.builder_scopes_from_db(db)
    collisions = ac.detect_candidate_collisions(
        lane_id="mine", branch="feat/mine", paths=["README.md"],
        states={}, external_scopes=scopes,
    )

    assert gap is None
    assert scopes[0].unbounded is True
    assert collisions[0].source_id == "run-anywhere"


def test_load_github_lane_events_handles_paginated_slurp() -> None:
    body = ac.render_event_comment(_payload())
    pages = [[{"id": 7, "created_at": "2026-08-31T06:30:00Z", "body": body}]]

    def runner(args, *, cwd=None, timeout=30):
        return ac.CommandResult(0, __import__("json").dumps(pages), "")

    events, gaps = ac.load_github_lane_events(
        "jacob202/kitty", 490, runner=runner
    )

    assert [event.comment_id for event in events] == [7]
    assert gaps == []


def test_load_github_lane_events_reports_transport_failure() -> None:
    def runner(args, *, cwd=None, timeout=30):
        return ac.CommandResult(1, "", "network down")

    events, gaps = ac.load_github_lane_events(
        "jacob202/kitty", 490, runner=runner
    )

    assert events == []
    assert gaps[0].source == "github"
    assert "network down" in gaps[0].reason


def test_load_open_pr_scopes_reads_changed_files() -> None:
    import json

    def runner(args, *, cwd=None, timeout=30):
        if args[:3] == ["gh", "pr", "list"]:
            return ac.CommandResult(
                0,
                json.dumps([
                    {"number": 705, "headRefName": "feat/library-chat", "title": "Library chat"}
                ]),
                "",
            )
        if args[:4] == ["gh", "pr", "view", "705"]:
            return ac.CommandResult(
                0,
                json.dumps({"files": [{"path": "gateway/routes/completions.py"}]}),
                "",
            )
        raise AssertionError(args)

    scopes, gaps = ac.load_open_pr_scopes("jacob202/kitty", runner=runner)

    assert gaps == []
    assert scopes == [
        ac.ExternalScope("pull_request", "#705", "feat/library-chat", ("gateway/routes/completions.py",))
    ]


def test_load_worktree_scopes_finds_unpublished_branch_files() -> None:
    porcelain = (
        "worktree /repo\nHEAD aaaaa\nbranch refs/heads/main\n\n"
        "worktree /repo/wt\nHEAD bbbbb\nbranch refs/heads/feat/other\n"
    )

    def runner(args, *, cwd=None, timeout=30):
        if args[:3] == ["git", "worktree", "list"]:
            return ac.CommandResult(0, porcelain, "")
        if args[:3] == ["git", "merge-base", "--is-ancestor"]:
            return ac.CommandResult(1, "", "")
        if args[:3] == ["git", "diff", "--name-only"]:
            return ac.CommandResult(0, "scripts/other.py\n", "")
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return ac.CommandResult(0, "", "")
        raise AssertionError(args)

    scopes, gaps = ac.load_worktree_scopes(
        Path("/repo"), base_ref="origin/main", ignore_branches={"main"}, runner=runner
    )

    assert gaps == []
    assert scopes[0].kind == "worktree"
    assert scopes[0].branch == "feat/other"
    assert scopes[0].paths == ("scripts/other.py",)


def test_dirty_detached_worktree_is_collision_evidence() -> None:
    porcelain = "worktree /repo/review\nHEAD ccccc\ndetached\n"

    def runner(args, *, cwd=None, timeout=30):
        if args[:3] == ["git", "worktree", "list"]:
            return ac.CommandResult(0, porcelain, "")
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return ac.CommandResult(0, "?? notes/recovered.txt\0", "")
        raise AssertionError(args)

    scopes, gaps = ac.load_worktree_scopes(
        Path("/repo"), base_ref="origin/main", ignore_branches=set(), runner=runner
    )

    assert gaps == []
    assert scopes[0].source_id == "/repo/review"
    assert scopes[0].paths == ("notes/recovered.txt",)


def test_repo_identity_reads_exact_branch_head_and_base() -> None:
    replies = {
        ("git", "rev-parse", "origin/main"): SHA_A + "\n",
        ("git", "rev-parse", "HEAD"): SHA_B + "\n",
        ("git", "branch", "--show-current"): "feat/coord\n",
        ("git", "rev-parse", "--show-toplevel"): "/repo/coord-wt\n",
    }
    def runner(args, *, cwd=None, timeout=30):
        key = tuple(args)
        if key not in replies:
            raise AssertionError(args)
        return ac.CommandResult(0, replies[key], "")

    identity, gap = ac.read_repo_identity(
        Path("/repo/coord-wt"), base_ref="origin/main", runner=runner
    )

    assert gap is None
    assert identity == ac.RepoIdentity(
        base_sha=SHA_A,
        head_sha=SHA_B,
        branch="feat/coord",
        worktree="coord-wt",
    )


def test_refresh_payload_preserves_claim_identity_and_updates_head() -> None:
    original = ac.event_from_payload(_payload(lane_id="coord-lane"), comment_id=1, github_created_at=NOW)
    state = ac.current_lane_states([original], now=NOW + timedelta(minutes=10))["coord-lane"]
    identity = ac.RepoIdentity(SHA_B, "c" * 40, "feat/chat-runtime", "coord-wt")

    payload = ac.build_followup_payload(
        state=state,
        event="refresh",
        identity=identity,
        owner="codex:chat-runtime",
        now=NOW + timedelta(minutes=10),
        lease_minutes=120,
    )

    assert payload["event"] == "refresh"
    assert payload["claim_started_at"] == "2026-08-31T06:30:00Z"
    assert payload["head_sha"] == "c" * 40
    assert payload["paths"] == ["gateway/routes/completions.py", "gateway/kitty-chat/**"]
    assert payload["lease_until"] == "2026-08-31T08:40:00Z"


def test_release_payload_is_terminal_and_preserves_scope() -> None:
    original = ac.event_from_payload(_payload(lane_id="coord-lane"), comment_id=1, github_created_at=NOW)
    state = ac.current_lane_states([original], now=NOW + timedelta(minutes=5))["coord-lane"]
    identity = ac.RepoIdentity(SHA_B, "d" * 40, "feat/chat-runtime", "coord-wt")

    payload = ac.build_followup_payload(
        state=state,
        event="release",
        identity=identity,
        owner="codex:chat-runtime",
        now=NOW + timedelta(minutes=5),
    )

    assert payload["event"] == "release"
    assert payload["status"] == "released"
    assert payload["lease_until"] is None
    assert payload["paths"] == ["gateway/routes/completions.py", "gateway/kitty-chat/**"]
    assert payload["claim_started_at"] == "2026-08-31T06:30:00Z"


def test_followup_refuses_other_owner_and_stale_refresh() -> None:
    original = ac.event_from_payload(_payload(lane_id="coord-lane"), comment_id=1, github_created_at=NOW)
    active = ac.current_lane_states([original], now=NOW + timedelta(minutes=5))["coord-lane"]
    stale = ac.current_lane_states([original], now=NOW + timedelta(hours=4))["coord-lane"]
    identity = ac.RepoIdentity(SHA_B, "e" * 40, "feat/chat-runtime", "coord-wt")

    with pytest.raises(ac.ProtocolError, match="owner"):
        ac.build_followup_payload(
            state=active, event="refresh", identity=identity,
            owner="someone-else", now=NOW + timedelta(minutes=5),
        )
    with pytest.raises(ac.ProtocolError, match="stale"):
        ac.build_followup_payload(
            state=stale, event="refresh", identity=identity,
            owner="codex:chat-runtime", now=NOW + timedelta(hours=4),
        )


def test_render_survey_json_exposes_truth_and_gaps() -> None:
    event = ac.event_from_payload(_payload(lane_id="coord-lane"), comment_id=9, github_created_at=NOW)
    states = ac.current_lane_states([event], now=NOW + timedelta(minutes=5))
    survey = ac.Survey(
        identity=ac.RepoIdentity(SHA_A, SHA_B, "feat/coord", "coord-wt"),
        states=states,
        external_scopes=(
            ac.ExternalScope("pull_request", "#709", "docs/packet", ("docs/packets/**",)),
        ),
        registry_conflicts=(),
        evidence_gaps=(ac.EvidenceGap("builder", "unavailable"),),
    )

    data = __import__("json").loads(ac.render_survey(survey, format="json"))

    assert data["identity"]["branch"] == "feat/coord"
    assert data["lanes"][0]["lane_id"] == "coord-lane"
    assert data["external_scopes"][0]["source_id"] == "#709"
    assert data["evidence_gaps"][0]["source"] == "builder"
    assert data["healthy"] is False


def test_render_survey_markdown_flags_stale_and_conflicts() -> None:
    first = ac.event_from_payload(_payload(lane_id="a-lane", paths=["scripts/**"]), comment_id=1, github_created_at=NOW)
    second = ac.event_from_payload(
        _payload(lane_id="b-lane", branch="feat/b", paths=["scripts/new.py"]),
        comment_id=2,
        github_created_at=NOW + timedelta(seconds=1),
    )
    states = ac.current_lane_states([first, second], now=NOW + timedelta(minutes=5))
    survey = ac.Survey(
        identity=None,
        states=states,
        external_scopes=(),
        registry_conflicts=tuple(ac.registry_collisions(states)),
        evidence_gaps=(),
    )

    text = ac.render_survey(survey, format="markdown")

    assert "a-lane" in text and "b-lane" in text
    assert "COLLISION" in text
    assert "a-lane" in text and "b-lane" in text


def test_publish_claim_rechecks_registry_and_releases_if_it_loses_race() -> None:
    mine = _payload(lane_id="mine", branch="feat/mine", paths=["scripts/new.py"])
    other = _payload(lane_id="other", branch="feat/other", paths=["scripts/**"])
    other_body = ac.render_event_comment(other)
    mine_body = ac.render_event_comment(mine)
    post_bodies: list[str] = []

    def runner(args, *, cwd=None, timeout=30):
        if args[:4] == ["gh", "api", "-X", "POST"]:
            body = args[-1].removeprefix("body=")
            post_bodies.append(body)
            return ac.CommandResult(0, __import__("json").dumps({"id": 42 + len(post_bodies)}), "")
        if args[:3] == ["gh", "api", "--paginate"]:
            comments = [[
                {"id": 40, "created_at": "2026-08-31T06:30:00Z", "body": other_body},
                {"id": 43, "created_at": "2026-08-31T06:30:01Z", "body": mine_body},
            ]]
            return ac.CommandResult(0, __import__("json").dumps(comments), "")
        raise AssertionError(args)

    with pytest.raises(ac.CollisionError, match="lost the durable claim race"):
        ac.publish_claim(
            mine,
            states={}, external_scopes=(), evidence_gaps=(),
            repo="jacob202/kitty", issue=490, post=True, runner=runner,
        )

    assert len(post_bodies) == 2
    assert '"event":"release"' in post_bodies[1]
    assert '"status":"released"' in post_bodies[1]


def test_default_builder_db_anchors_to_canonical_common_dir() -> None:
    def runner(args, *, cwd=None, timeout=30):
        assert args == ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]
        return ac.CommandResult(0, "/repo/.git\n", "")

    path, gap = ac.default_builder_db(Path("/repo/wt"), runner=runner)

    assert gap is None
    assert path == Path("/repo/data/kittybuilder/builder_queue.db")


def test_cli_survey_prints_machine_readable_json(capsys) -> None:
    survey = ac.Survey(
        identity=ac.RepoIdentity(SHA_A, SHA_B, "feat/coord", "coord-wt"),
        states={}, external_scopes=(), registry_conflicts=(), evidence_gaps=(),
    )

    def loader(**kwargs):
        return survey

    rc = ac.main(
        ["--repo-root", "/repo", "survey", "--format", "json"],
        survey_loader=loader,
    )

    output = __import__("json").loads(capsys.readouterr().out)
    assert rc == 0
    assert output["healthy"] is True
    assert output["identity"]["branch"] == "feat/coord"


def test_cli_claim_dry_run_emits_structured_event_without_write(capsys) -> None:
    survey = ac.Survey(
        identity=ac.RepoIdentity(SHA_A, SHA_B, "feat/coord", "coord-wt"),
        states={}, external_scopes=(), registry_conflicts=(), evidence_gaps=(),
    )
    calls: list[list[str]] = []

    def loader(**kwargs):
        return survey

    def runner(args, *, cwd=None, timeout=30):
        calls.append(list(args))
        raise AssertionError("dry-run claim must not invoke a command")

    rc = ac.main(
        [
            "--repo-root", "/repo", "claim",
            "--lane-id", "coord-cli", "--owner", "chatgpt",
            "--lane", "Coordination CLI", "--output", "PR TBD",
            "--path", "scripts/agent_coordination.py",
        ],
        runner=runner,
        survey_loader=loader,
    )

    text = capsys.readouterr().out
    assert rc == 0
    assert "kitty-lane:v1" in text
    assert calls == []


def test_cli_release_requires_known_lane(capsys) -> None:
    survey = ac.Survey(
        identity=ac.RepoIdentity(SHA_A, SHA_B, "feat/coord", "coord-wt"),
        states={}, external_scopes=(), registry_conflicts=(), evidence_gaps=(),
    )

    rc = ac.main(
        ["--repo-root", "/repo", "release", "--lane-id", "missing", "--owner", "chatgpt"],
        survey_loader=lambda **kwargs: survey,
    )

    assert rc == 2
    assert "unknown lane" in capsys.readouterr().err.lower()


def test_launcher_exposes_coordination_command() -> None:
    launcher = Path("kitty").read_text()
    assert "cmd_coordination" in launcher
    assert "coordination)" in launcher
