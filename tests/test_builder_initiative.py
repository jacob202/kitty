"""Tests for gateway/builder_initiative.py — KB-S1A manifests.

Covers: canonicalization/hashing, semantic validation (duplicates, missing
deps, self-deps, cycles, policies, acceptance criteria, allowed paths),
atomic + idempotent apply, dry-run, read helpers, and the CLI surface.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway.builder_cli import main

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    bi.init_db(p)
    return p


def _manifest(**overrides) -> dict:
    base = {
        "manifest_version": 1,
        "initiative_id": "kitty-alpha-v1",
        "title": "Kitty Alpha build",
        "description": "Multi-phase Kitty Alpha build.",
        "packets": [
            {
                "id": "KB-A1",
                "title": "First packet",
                "objective": "Do the first thing.",
                "depends_on": [],
                "acceptance_criteria": ["it works"],
                "allowed_paths": ["gateway/a.py"],
                "policy": {"max_attempts": 2, "priority": 5},
            },
            {
                "id": "KB-A2",
                "title": "Second packet",
                "objective": "Do the second thing.",
                "depends_on": ["KB-A1"],
                "acceptance_criteria": ["it also works"],
                "allowed_paths": ["gateway/b.py", "tests/test_b.py"],
            },
        ],
    }
    base.update(overrides)
    return base


def _packet(pid: str = "KB-X1", **overrides) -> dict:
    base = {
        "id": pid,
        "title": f"Packet {pid}",
        "objective": f"Objective for {pid}.",
        "acceptance_criteria": ["done"],
        "allowed_paths": ["gateway/x.py"],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Canonicalization / hashing
# ---------------------------------------------------------------------------


class TestCanonicalization:
    def test_key_order_does_not_change_hash(self):
        a = {"manifest_version": 1, "initiative_id": "x", "title": "t"}
        b = {"title": "t", "initiative_id": "x", "manifest_version": 1}
        assert bi.manifest_sha256(a) == bi.manifest_sha256(b)

    def test_content_change_changes_hash(self):
        m1 = _manifest()
        m2 = _manifest(title="Different title")
        assert bi.manifest_sha256(m1) != bi.manifest_sha256(m2)

    def test_canonical_form_is_compact_and_sorted(self):
        canonical = bi.canonicalize_manifest({"b": 1, "a": 2})
        assert canonical == '{"a":2,"b":1}'

    def test_canonical_form_preserves_unicode(self):
        canonical = bi.canonicalize_manifest({"title": "café"})
        assert "café" in canonical


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_manifest_has_no_errors(self):
        assert bi.validate_manifest(_manifest()) == []

    def test_non_dict_root(self):
        assert bi.validate_manifest([1, 2]) == [
            "manifest root must be a JSON object"
        ]

    def test_wrong_manifest_version(self):
        errors = bi.validate_manifest(_manifest(manifest_version=99))
        assert any("manifest_version" in e for e in errors)

    def test_missing_initiative_id(self):
        m = _manifest()
        del m["initiative_id"]
        assert any("initiative_id" in e for e in bi.validate_manifest(m))

    def test_bad_initiative_id_characters(self):
        errors = bi.validate_manifest(_manifest(initiative_id="has spaces!"))
        assert any("initiative_id" in e for e in errors)

    def test_trailing_newline_in_id_rejected(self):
        errors = bi.validate_manifest(_manifest(initiative_id="kitty-alpha-v1\n"))
        assert any("initiative_id" in e for e in errors)

    def test_unknown_top_level_key(self):
        errors = bi.validate_manifest(_manifest(extra_key=True))
        assert any("unknown top-level keys" in e for e in errors)

    def test_empty_packets(self):
        errors = bi.validate_manifest(_manifest(packets=[]))
        assert any("packets" in e for e in errors)

    def test_duplicate_packet_ids(self):
        m = _manifest(packets=[_packet("KB-D1"), _packet("KB-D1")])
        assert any("duplicate packet id" in e for e in bi.validate_manifest(m))

    def test_missing_dependency(self):
        m = _manifest(packets=[_packet("KB-M1", depends_on=["KB-NOPE"])])
        assert any(
            "unknown dependency 'KB-NOPE'" in e for e in bi.validate_manifest(m)
        )

    def test_self_dependency(self):
        m = _manifest(packets=[_packet("KB-S1", depends_on=["KB-S1"])])
        assert any("depends on itself" in e for e in bi.validate_manifest(m))

    def test_dependency_cycle(self):
        m = _manifest(
            packets=[
                _packet("KB-C1", depends_on=["KB-C2"]),
                _packet("KB-C2", depends_on=["KB-C1"]),
            ]
        )
        assert any("dependency cycle" in e for e in bi.validate_manifest(m))

    def test_empty_acceptance_criteria(self):
        m = _manifest(packets=[_packet("KB-E1", acceptance_criteria=[])])
        assert any("acceptance_criteria" in e for e in bi.validate_manifest(m))

    def test_whitespace_acceptance_criteria(self):
        m = _manifest(packets=[_packet("KB-E2", acceptance_criteria=["  "])])
        assert any("acceptance_criteria" in e for e in bi.validate_manifest(m))

    def test_absent_allowed_paths(self):
        m = _manifest(packets=[_packet("KB-P1")])
        del m["packets"][0]["allowed_paths"]
        assert any("allowed_paths" in e for e in bi.validate_manifest(m))

    def test_absolute_allowed_path(self):
        m = _manifest(packets=[_packet("KB-P2", allowed_paths=["/etc/passwd"])])
        assert any("repo-relative" in e for e in bi.validate_manifest(m))

    def test_parent_traversal_allowed_path(self):
        m = _manifest(packets=[_packet("KB-P3", allowed_paths=["../outside"])])
        assert any("'..'" in e for e in bi.validate_manifest(m))

    def test_invalid_policy_type(self):
        m = _manifest(packets=[_packet("KB-Y1", policy="fast")])
        assert any("policy must be a JSON object" in e for e in bi.validate_manifest(m))

    def test_unknown_policy_key(self):
        m = _manifest(packets=[_packet("KB-Y2", policy={"retries": 3})])
        assert any("unknown policy keys" in e for e in bi.validate_manifest(m))

    def test_non_positive_max_attempts(self):
        m = _manifest(packets=[_packet("KB-Y3", policy={"max_attempts": 0})])
        assert any("max_attempts" in e for e in bi.validate_manifest(m))

    def test_boolean_priority_rejected(self):
        m = _manifest(packets=[_packet("KB-Y4", policy={"priority": True})])
        assert any("priority" in e for e in bi.validate_manifest(m))

    def test_missing_objective(self):
        m = _manifest(packets=[_packet("KB-O1")])
        del m["packets"][0]["objective"]
        assert any("objective" in e for e in bi.validate_manifest(m))

    def test_unknown_packet_key(self):
        m = _manifest(packets=[_packet("KB-U1", surprise=1)])
        assert any("unknown keys" in e for e in bi.validate_manifest(m))

    def test_multiple_errors_reported_together(self):
        m = _manifest(
            manifest_version=2,
            packets=[_packet("KB-B1", acceptance_criteria=[], depends_on=["KB-GONE"])],
        )
        errors = bi.validate_manifest(m)
        assert len(errors) >= 3

    def test_load_manifest_rejects_bad_json(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(bi.ManifestError):
            bi.load_manifest(bad)

    def test_load_manifest_rejects_missing_file(self, tmp_path: Path):
        with pytest.raises(bi.ManifestError):
            bi.load_manifest(tmp_path / "absent.json")

    def test_load_manifest_rejects_non_object_root(self, tmp_path: Path):
        p = tmp_path / "list.json"
        p.write_text("[1,2]", encoding="utf-8")
        with pytest.raises(bi.ManifestError):
            bi.load_manifest(p)


# ---------------------------------------------------------------------------
# Lint warnings (CP-02)
# ---------------------------------------------------------------------------


def _init_git_repo(tmp_path: Path) -> Path:
    """A throwaway git repo so T3's ``git ls-files`` has something to answer,
    independent of whatever the real kitty checkout happens to contain."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    return tmp_path


class TestWarnings:
    # -- (a) acceptance_criteria without validation_commands -----------------

    def test_missing_validation_commands_warns(self, tmp_path: Path):
        m = _manifest(packets=[_packet("KB-W1")])
        warnings = bi.warn_manifest(m, repo_root=tmp_path)
        assert any("validation_commands" in w for w in warnings)

    def test_present_validation_commands_no_false_positive(self, tmp_path: Path):
        m = _manifest(
            packets=[_packet("KB-W1", validation_commands=["pytest tests/"])]
        )
        warnings = bi.warn_manifest(m, repo_root=tmp_path)
        assert not any("validation_commands" in w for w in warnings)

    # -- (b) allowed_paths collision without a dependency relation -----------

    def test_path_collision_without_dependency_warns(self, tmp_path: Path):
        m = _manifest(
            packets=[
                _packet(
                    "KB-C1",
                    depends_on=[],
                    allowed_paths=["gateway/shared/"],
                    validation_commands=["true"],
                ),
                _packet(
                    "KB-C2",
                    depends_on=[],
                    allowed_paths=["gateway/shared/a.py"],
                    validation_commands=["true"],
                ),
            ]
        )
        warnings = bi.warn_manifest(m, repo_root=tmp_path)
        assert any("allowed_paths collide" in w for w in warnings)

    def test_path_collision_with_dependency_no_false_positive(self, tmp_path: Path):
        m = _manifest(
            packets=[
                _packet(
                    "KB-C1",
                    depends_on=[],
                    allowed_paths=["gateway/shared/"],
                    validation_commands=["true"],
                ),
                _packet(
                    "KB-C2",
                    depends_on=["KB-C1"],
                    allowed_paths=["gateway/shared/a.py"],
                    validation_commands=["true"],
                ),
            ]
        )
        warnings = bi.warn_manifest(m, repo_root=tmp_path)
        assert not any("allowed_paths collide" in w for w in warnings)

    def test_disjoint_paths_no_false_positive(self, tmp_path: Path):
        m = _manifest(
            packets=[
                _packet(
                    "KB-C1",
                    depends_on=[],
                    allowed_paths=["gateway/a.py"],
                    validation_commands=["true"],
                ),
                _packet(
                    "KB-C2",
                    depends_on=[],
                    allowed_paths=["gateway/b.py"],
                    validation_commands=["true"],
                ),
            ]
        )
        warnings = bi.warn_manifest(m, repo_root=tmp_path)
        assert not any("allowed_paths collide" in w for w in warnings)

    # -- (c) prototype-shaped manifest without a "-proto" packet -------------

    def test_t1_four_packets_no_proto_warns(self, tmp_path: Path):
        m = _manifest(
            packets=[
                _packet(f"KB-T1-{n}", depends_on=[], allowed_paths=[f"gateway/f{n}.py"], validation_commands=["true"])
                for n in range(4)
            ]
        )
        warnings = bi.warn_manifest(m, repo_root=tmp_path)
        assert any("prototype-shaped" in w and "T1" in w for w in warnings)

    def test_t2_two_subsystems_no_proto_warns(self, tmp_path: Path):
        m = _manifest(
            packets=[
                _packet(
                    "KB-T2-1",
                    depends_on=[],
                    allowed_paths=["gateway/f.py"],
                    validation_commands=["true"],
                ),
                _packet(
                    "KB-T2-2",
                    depends_on=[],
                    allowed_paths=["docs/f.md"],
                    validation_commands=["true"],
                ),
            ]
        )
        warnings = bi.warn_manifest(m, repo_root=tmp_path)
        assert any("prototype-shaped" in w and "T2" in w for w in warnings)

    def test_t3_new_directory_no_proto_warns(self, tmp_path: Path):
        repo = _init_git_repo(tmp_path)
        m = _manifest(
            packets=[
                _packet(
                    "KB-T3-1",
                    depends_on=[],
                    allowed_paths=["gateway/brand_new_module/"],
                    validation_commands=["true"],
                )
            ]
        )
        warnings = bi.warn_manifest(m, repo_root=repo)
        assert any("prototype-shaped" in w and "T3" in w for w in warnings)

    def test_tracked_directory_no_false_positive(self, tmp_path: Path):
        repo = _init_git_repo(tmp_path)
        (repo / "gateway").mkdir()
        tracked = repo / "gateway" / "existing.py"
        tracked.write_text("# tracked\n", encoding="utf-8")
        subprocess.run(["git", "add", "gateway/existing.py"], cwd=repo, check=True)

        m = _manifest(
            packets=[
                _packet(
                    "KB-T3-2",
                    depends_on=[],
                    allowed_paths=["gateway/existing.py"],
                    validation_commands=["true"],
                )
            ]
        )
        warnings = bi.warn_manifest(m, repo_root=repo)
        assert not any("prototype-shaped" in w for w in warnings)

    def test_proto_packet_suppresses_prototype_shaped_warning(self, tmp_path: Path):
        m = _manifest(
            packets=[
                _packet(
                    f"KB-P-{n}",
                    depends_on=[],
                    allowed_paths=[f"gateway/f{n}.py"],
                    validation_commands=["true"],
                )
                for n in range(3)
            ]
            + [
                _packet(
                    "kitty-alpha-v1-proto",
                    depends_on=[],
                    allowed_paths=["docs/f.md"],
                    validation_commands=["true"],
                )
            ]
        )
        warnings = bi.warn_manifest(m, repo_root=tmp_path)
        assert not any("prototype-shaped" in w for w in warnings)

    def test_clean_manifest_has_no_warnings(self, tmp_path: Path):
        repo = _init_git_repo(tmp_path)
        (repo / "gateway").mkdir()
        tracked = repo / "gateway" / "a.py"
        tracked.write_text("# tracked\n", encoding="utf-8")
        subprocess.run(["git", "add", "gateway/a.py"], cwd=repo, check=True)

        m = _manifest(
            packets=[
                _packet(
                    "KB-CLEAN-1",
                    depends_on=[],
                    allowed_paths=["gateway/a.py"],
                    validation_commands=["pytest"],
                )
            ]
        )
        assert bi.warn_manifest(m, repo_root=repo) == []


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


class TestApply:
    def test_first_apply_creates_everything(self, db_path: Path):
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        assert result["status"] == "created"
        assert len(result["packets"]) == 2

        # Initiative row exists.
        initiative = bi.get_initiative("kitty-alpha-v1", db_path=db_path)
        assert initiative is not None
        assert initiative["state"] == "active"
        assert initiative["manifest_sha256"] == bi.manifest_sha256(_manifest())

        # One queued task per packet with objective/acceptance/paths.
        for mapping, packet in zip(result["packets"], _manifest()["packets"]):
            task = bq.get_task(mapping["task_id"], db_path=db_path)
            assert task is not None
            assert task["state"] == bq.QUEUED
            assert packet["id"] in task["title"]
            assert task["description"] == packet["objective"]
            assert task["acceptance_criteria"] == packet["acceptance_criteria"]
            assert task["allowed_paths"] == packet["allowed_paths"]
            assert task["bridge_source"] == "initiative"
            assert (
                task["bridge_external_id"]
                == f"kitty-alpha-v1/{packet['id']}"
            )

    def test_policy_priority_flows_to_task(self, db_path: Path):
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        first = bq.get_task(result["packets"][0]["task_id"], db_path=db_path)
        second = bq.get_task(result["packets"][1]["task_id"], db_path=db_path)
        assert first["priority"] == 5
        assert second["priority"] == 0

    def test_identical_reapply_is_unchanged(self, db_path: Path):
        first = bi.apply_manifest(_manifest(), db_path=db_path)
        second = bi.apply_manifest(_manifest(), db_path=db_path)
        assert second["status"] == "unchanged"
        # Same stable packet-to-task mapping, no new tasks.
        assert second["packets"] == first["packets"]
        assert len(bq.list_tasks(db_path=db_path)) == 2

    def test_key_order_variant_is_still_unchanged(self, db_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        reordered = json.loads(
            json.dumps(_manifest(), sort_keys=True)
        )
        result = bi.apply_manifest(reordered, db_path=db_path)
        assert result["status"] == "unchanged"

    def test_changed_manifest_same_id_conflicts_without_mutation(
        self, db_path: Path
    ):
        bi.apply_manifest(_manifest(), db_path=db_path)
        changed = _manifest(title="Renamed initiative")
        with pytest.raises(bi.InitiativeConflictError):
            bi.apply_manifest(changed, db_path=db_path)
        # No partial mutation: still 2 tasks, stored manifest unchanged.
        assert len(bq.list_tasks(db_path=db_path)) == 2
        initiative = bi.get_initiative("kitty-alpha-v1", db_path=db_path)
        assert initiative["manifest"]["title"] == "Kitty Alpha build"

    def test_invalid_manifest_raises_and_mutates_nothing(self, db_path: Path):
        with pytest.raises(bi.ManifestError):
            bi.apply_manifest(_manifest(packets=[]), db_path=db_path)
        assert bi.list_initiatives(db_path=db_path) == []
        assert bq.list_tasks(db_path=db_path) == []

    def test_dry_run_reports_would_create_without_mutation(self, db_path: Path):
        result = bi.apply_manifest(_manifest(), dry_run=True, db_path=db_path)
        assert result["status"] == "would_create"
        assert [p["task_id"] for p in result["packets"]] == [None, None]
        assert bi.list_initiatives(db_path=db_path) == []
        assert bq.list_tasks(db_path=db_path) == []

    def test_dry_run_does_not_require_git_refs(
        self, db_path: Path, tmp_path: Path
    ):
        result = bi.apply_manifest(
            _manifest(), dry_run=True, db_path=db_path, repo_root=tmp_path
        )
        assert result["status"] == "would_create"

    def test_first_apply_without_base_ref_fails_without_mutation(
        self, db_path: Path, tmp_path: Path
    ):
        with pytest.raises(bi.BaseSHAResolutionError, match="durable packet base SHA"):
            bi.apply_manifest(_manifest(), db_path=db_path, repo_root=tmp_path)

        assert bi.list_initiatives(db_path=db_path) == []
        assert bq.list_tasks(db_path=db_path) == []

    def test_dry_run_on_existing_reports_unchanged(self, db_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        result = bi.apply_manifest(_manifest(), dry_run=True, db_path=db_path)
        assert result["status"] == "unchanged"
        assert len(bq.list_tasks(db_path=db_path)) == 2

    def test_dry_run_on_conflict_raises(self, db_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        with pytest.raises(bi.InitiativeConflictError):
            bi.apply_manifest(
                _manifest(title="Changed"), dry_run=True, db_path=db_path
            )

    def test_apply_is_atomic_on_mid_apply_failure(
        self, db_path: Path, monkeypatch
    ):
        # Fail while creating the SECOND task; nothing may survive.
        real_create = bq.create_task
        calls = {"n": 0}

        def flaky_create(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("simulated crash mid-apply")
            return real_create(*args, **kwargs)

        monkeypatch.setattr(bi.bq, "create_task", flaky_create)
        with pytest.raises(RuntimeError, match="simulated crash"):
            bi.apply_manifest(_manifest(), db_path=db_path)
        assert bi.list_initiatives(db_path=db_path) == []
        assert bq.list_tasks(db_path=db_path) == []
        # Event log must not contain orphaned 'created' events either.
        conn = sqlite3.connect(str(db_path))
        try:
            count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        finally:
            conn.close()
        assert count == 0

    def test_tasks_created_events_are_appended(self, db_path: Path):
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        conn = sqlite3.connect(str(db_path))
        try:
            for mapping in result["packets"]:
                count = conn.execute(
                    "SELECT COUNT(*) FROM events WHERE task_id = ? AND type = 'created'",
                    (mapping["task_id"],),
                ).fetchone()[0]
                assert count == 1
        finally:
            conn.close()

    def test_existing_queue_behavior_untouched(self, db_path: Path):
        """Materialized tasks obey the ordinary task state machine."""
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        task_id = result["packets"][0]["task_id"]
        claimed = bq.claim_task(task_id, "w1", db_path=db_path)
        assert claimed["state"] == bq.CLAIMED

    def test_create_task_without_conn_still_commits(self, db_path: Path):
        """Regression: the conn-threading change keeps standalone behavior."""
        task = bq.create_task("standalone", db_path=db_path)
        fetched = bq.get_task(task["id"], db_path=db_path)
        assert fetched is not None
        assert fetched["state"] == bq.QUEUED


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


class TestReadHelpers:
    def test_list_initiatives_reports_counts(self, db_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        items = bi.list_initiatives(db_path=db_path)
        assert len(items) == 1
        assert items[0]["id"] == "kitty-alpha-v1"
        assert items[0]["packet_count"] == 2

    def test_get_initiative_returns_ordered_packets(self, db_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        initiative = bi.get_initiative("kitty-alpha-v1", db_path=db_path)
        packet_ids = [p["packet_id"] for p in initiative["packets"]]
        assert packet_ids == ["KB-A1", "KB-A2"]
        assert initiative["packets"][1]["depends_on"] == ["KB-A1"]
        assert initiative["packets"][0]["policy"] == {
            "max_attempts": 2,
            "priority": 5,
        }

    def test_get_initiative_missing_returns_none(self, db_path: Path):
        assert bi.get_initiative("nope", db_path=db_path) is None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_db(tmp_path: Path, monkeypatch) -> Path:
    """Point the module-level default DB at a tmp path for end-to-end CLI runs."""
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    monkeypatch.setattr(bq, "BUILDER_QUEUE_DB", p)
    return p


def _write_manifest(tmp_path: Path, manifest: dict) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


class TestCli:
    def test_validate_ok(self, tmp_path: Path, cli_db, capsys):
        path = _write_manifest(tmp_path, _manifest())
        assert main(["initiative", "validate", str(path)]) == 0
        out = capsys.readouterr().out
        assert "OK" in out and "kitty-alpha-v1" in out

    def test_validate_reports_every_error(self, tmp_path: Path, cli_db, capsys):
        bad = _manifest(
            manifest_version=9,
            packets=[_packet("KB-B1", acceptance_criteria=[])],
        )
        path = _write_manifest(tmp_path, bad)
        assert main(["initiative", "validate", str(path)]) == 1
        err = capsys.readouterr().err
        assert "manifest_version" in err
        assert "acceptance_criteria" in err

    def test_apply_then_reapply_unchanged(self, tmp_path: Path, cli_db, capsys):
        path = _write_manifest(tmp_path, _manifest())
        assert main(["initiative", "apply", str(path)]) == 0
        assert "created" in capsys.readouterr().out
        assert main(["initiative", "apply", str(path)]) == 0
        assert "unchanged" in capsys.readouterr().out

    def test_apply_dry_run_creates_nothing(self, tmp_path: Path, cli_db, capsys):
        path = _write_manifest(tmp_path, _manifest())
        assert main(["initiative", "apply", str(path), "--dry-run"]) == 0
        assert "would_create" in capsys.readouterr().out
        assert bi.list_initiatives() == []

    def test_apply_conflict_exits_nonzero(self, tmp_path: Path, cli_db, capsys):
        path = _write_manifest(tmp_path, _manifest())
        assert main(["initiative", "apply", str(path)]) == 0
        capsys.readouterr()
        changed = _write_manifest(tmp_path, _manifest(title="Changed"))
        assert main(["initiative", "apply", str(changed)]) == 1
        assert "different contents" in capsys.readouterr().err

    def test_apply_json_output(self, tmp_path: Path, cli_db, capsys):
        path = _write_manifest(tmp_path, _manifest())
        assert main(["initiative", "apply", str(path), "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "created"
        assert len(payload["packets"]) == 2

    def test_list_and_show(self, tmp_path: Path, cli_db, capsys):
        path = _write_manifest(tmp_path, _manifest())
        main(["initiative", "apply", str(path)])
        capsys.readouterr()

        assert main(["initiative", "list"]) == 0
        assert "kitty-alpha-v1" in capsys.readouterr().out

        assert main(["initiative", "show", "kitty-alpha-v1"]) == 0
        out = capsys.readouterr().out
        assert "KB-A1" in out and "KB-A2" in out

        assert main(["initiative", "show", "kitty-alpha-v1", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert [p["packet_id"] for p in payload["packets"]] == ["KB-A1", "KB-A2"]

    def test_show_missing_initiative(self, cli_db, capsys):
        assert main(["initiative", "show", "ghost"]) == 1
        assert "not found" in capsys.readouterr().err

    def test_kill_switch_blocks_apply(
        self, tmp_path: Path, cli_db, capsys, monkeypatch
    ):
        monkeypatch.setenv("KITTY_BUILDER_QUEUE_ENABLED", "0")
        path = _write_manifest(tmp_path, _manifest())
        assert main(["initiative", "apply", str(path)]) == 1
        assert "disabled" in capsys.readouterr().err
        monkeypatch.delenv("KITTY_BUILDER_QUEUE_ENABLED")
        assert bi.list_initiatives() == []

    def test_kill_switch_allows_validate_and_list(
        self, tmp_path: Path, cli_db, capsys, monkeypatch
    ):
        monkeypatch.setenv("KITTY_BUILDER_QUEUE_ENABLED", "0")
        path = _write_manifest(tmp_path, _manifest())
        assert main(["initiative", "validate", str(path)]) == 0
        capsys.readouterr()
        assert main(["initiative", "list"]) == 0

    def test_example_manifest_validates(self, cli_db, capsys):
        example = Path("docs/examples/kitty_alpha_initiative.example.json")
        assert example.exists(), "example manifest must ship with KB-S1A"
        assert main(["initiative", "validate", str(example)]) == 0

    def test_validate_json_output_includes_warnings(
        self, tmp_path: Path, cli_db, capsys
    ):
        path = _write_manifest(
            tmp_path,
            _manifest(packets=[_packet("KB-J1")]),  # no validation_commands
        )
        assert main(["initiative", "validate", str(path), "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["valid"] is True
        assert payload["initiative_id"] == "kitty-alpha-v1"
        assert any("validation_commands" in w for w in payload["warnings"])

    def test_validate_warnings_do_not_change_exit_code(
        self, tmp_path: Path, cli_db, capsys
    ):
        path = _write_manifest(
            tmp_path, _manifest(packets=[_packet("KB-J2")])
        )
        assert main(["initiative", "validate", str(path)]) == 0
        err = capsys.readouterr().err
        assert "warning:" in err


# ---------------------------------------------------------------------------
# KB-S1B — eligibility and initiative status (read-only)
# ---------------------------------------------------------------------------


def _drive_to_done(task_id: str, db_path: Path) -> None:
    """Move a queued task through the legal state machine to ``done``."""
    bq.transition_task(task_id, bq.CLAIMED, db_path=db_path)
    bq.transition_task(task_id, bq.RUNNING, db_path=db_path)
    bq.transition_task(task_id, bq.PR_OPENED, db_path=db_path)
    bq.transition_task(task_id, bq.AWAITING_REVIEW, db_path=db_path)
    bq.transition_task(task_id, bq.DONE, db_path=db_path)


def _three_chain_manifest() -> dict:
    return {
        "manifest_version": 1,
        "initiative_id": "chain-v1",
        "title": "Three-packet chain",
        "packets": [
            {
                "id": "C1",
                "title": "First",
                "objective": "one",
                "depends_on": [],
                "acceptance_criteria": ["ok"],
                "allowed_paths": ["gateway/a.py"],
            },
            {
                "id": "C2",
                "title": "Second",
                "objective": "two",
                "depends_on": ["C1"],
                "acceptance_criteria": ["ok"],
                "allowed_paths": ["gateway/b.py"],
            },
            {
                "id": "C3",
                "title": "Third",
                "objective": "three",
                "depends_on": ["C2"],
                "acceptance_criteria": ["ok"],
                "allowed_paths": ["gateway/c.py"],
            },
        ],
    }


class TestKbS1bEligibility:
    def test_initial_eligible_is_dependency_free_packet(self, db_path: Path):
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        eligible = bi.eligible_packets("kitty-alpha-v1", db_path=db_path)
        assert [p["packet_id"] for p in eligible] == ["KB-A1"]
        assert result["packets"][0]["packet_id"] == "KB-A1"

    def test_next_packet_is_lowest_seq_among_eligible(self, db_path: Path):
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        nxt = bi.next_packet("kitty-alpha-v1", db_path=db_path)
        assert nxt["packet_id"] == "KB-A1"
        assert nxt["task_id"] == result["packets"][0]["task_id"]

    def test_dependent_not_eligible_until_dependency_done(self, db_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        eligible = bi.eligible_packets("kitty-alpha-v1", db_path=db_path)
        assert "KB-A2" not in [p["packet_id"] for p in eligible]

    def test_two_independent_packets_both_eligible_ordered_by_seq(self, db_path: Path):
        manifest = _manifest(
            packets=[
                _packet("KB-Z1", depends_on=[]),
                _packet("KB-Z2", depends_on=[]),
            ]
        )
        bi.apply_manifest(manifest, db_path=db_path)
        eligible = bi.eligible_packets("kitty-alpha-v1", db_path=db_path)
        assert [p["packet_id"] for p in eligible] == ["KB-Z1", "KB-Z2"]

    def test_blocked_forever_when_dependency_task_failed(self, db_path: Path):
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        dep_task = result["packets"][0]["task_id"]
        bq.transition_task(dep_task, bq.FAILED, db_path=db_path)

        eligible = bi.eligible_packets("kitty-alpha-v1", db_path=db_path)
        assert eligible == []

        blocked = bi.blocked_packets("kitty-alpha-v1", db_path=db_path)
        assert [b["packet_id"] for b in blocked] == ["KB-A2"]
        assert blocked[0]["blocked_by"][0]["packet_id"] == "KB-A1"

    def test_blocked_propagates_transitively(self, db_path: Path):
        result = bi.apply_manifest(_three_chain_manifest(), db_path=db_path)
        c1_task = result["packets"][0]["task_id"]
        bq.transition_task(c1_task, bq.FAILED, db_path=db_path)

        blocked = bi.blocked_packets("chain-v1", db_path=db_path)
        assert {b["packet_id"] for b in blocked} == {"C2", "C3"}

    def test_completed_when_all_tasks_done(self, db_path: Path):
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        for mapping in result["packets"]:
            _drive_to_done(mapping["task_id"], db_path)

        status = bi.initiative_status("kitty-alpha-v1", db_path=db_path)
        assert status["state"] == bi.INITIATIVE_COMPLETED
        assert set(status["done"]) == {"KB-A1", "KB-A2"}
        assert status["next_packet"] is None

    def test_paused_when_in_flight_and_nothing_eligible(self, db_path: Path):
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        # Claim KB-A1 (in flight); KB-A2 waits on it. Nothing is claimable now.
        bq.transition_task(result["packets"][0]["task_id"], bq.CLAIMED, db_path=db_path)

        status = bi.initiative_status("kitty-alpha-v1", db_path=db_path)
        assert status["state"] == bi.INITIATIVE_PAUSED
        assert status["eligible"] == []
        assert status["in_progress"] == ["KB-A1"]
        assert status["pending"] == ["KB-A2"]

    def test_failed_state_on_direct_task_failure(self, db_path: Path):
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        bq.transition_task(result["packets"][1]["task_id"], bq.FAILED, db_path=db_path)

        status = bi.initiative_status("kitty-alpha-v1", db_path=db_path)
        assert status["state"] == bi.INITIATIVE_FAILED
        assert status["failed"] == ["KB-A2"]

    def test_active_state_with_eligible_packet(self, db_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        status = bi.initiative_status("kitty-alpha-v1", db_path=db_path)
        assert status["state"] == bi.INITIATIVE_ACTIVE
        assert status["next_packet"] == "KB-A1"

    def test_status_exposes_truthful_operator_and_review_evidence(self, db_path: Path):
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        task_id = result["packets"][0]["task_id"]
        bq.append_event(task_id, "operator_completed", payload={"source": "human"}, db_path=db_path)
        bq.append_event(
            task_id,
            "review_evidence_bound",
            payload={"review_sha": "abc123", "diff_sha256": "def456"},
            db_path=db_path,
        )

        evidence = bi.initiative_status("kitty-alpha-v1", db_path=db_path)["evidence"]["KB-A1"]
        assert evidence["operator_completed"] is True
        assert evidence["review_approved"] is False
        assert evidence["review_binding"]["review_sha"] == "abc123"
        assert evidence["done"] is False
        assert evidence["infrastructure_failures"] == 0
        assert evidence["latest_run_id"] is None
        assert evidence["pr"] is None

    def test_status_not_found_raises(self, db_path: Path):
        with pytest.raises(bi.InitiativeNotFoundError):
            bi.initiative_status("ghost", db_path=db_path)


class TestKbS1bAttemptExhaustion:
    """Attempt-exhausted packets must not be reported as eligible or in progress."""

    def _apply_and_exhaust(
        self, db_path: Path, max_attempts: int = 2
    ) -> tuple[str, str]:
        manifest = _manifest(
            packets=[
                _packet(
                    "KB-E1",
                    policy={"max_attempts": max_attempts, "priority": 5},
                ),
                _packet("KB-E2", depends_on=["KB-E1"]),
            ]
        )
        result = bi.apply_manifest(manifest, db_path=db_path)
        task_id = result["packets"][0]["task_id"]
        for attempt_no in range(1, max_attempts + 1):
            attempt = ba.start_attempt(
                "kitty-alpha-v1", "KB-E1", db_path=db_path
            )
            assert attempt["attempt_no"] == attempt_no
            ba.close_attempt(
                attempt["id"], ba.ATTEMPT_FAILED, db_path=db_path
            )
        return task_id, result["packets"][1]["task_id"]

    def test_exhausted_packet_not_eligible(self, db_path: Path):
        self._apply_and_exhaust(db_path)
        eligible = bi.eligible_packets("kitty-alpha-v1", db_path=db_path)
        assert [p["packet_id"] for p in eligible] == []

    def test_exhausted_packet_reported_in_status(self, db_path: Path):
        self._apply_and_exhaust(db_path)
        status = bi.initiative_status("kitty-alpha-v1", db_path=db_path)
        assert status["exhausted"] == ["KB-E1"]
        assert "KB-E1" not in status["eligible"]
        assert "KB-E1" not in status["in_progress"]
        assert "KB-E1" not in status["pending"]

    def test_exhausted_packet_marks_initiative_failed(self, db_path: Path):
        self._apply_and_exhaust(db_path)
        status = bi.initiative_status("kitty-alpha-v1", db_path=db_path)
        assert status["state"] == bi.INITIATIVE_FAILED

    def test_dependents_of_exhausted_packet_are_blocked(self, db_path: Path):
        self._apply_and_exhaust(db_path)
        blocked = bi.blocked_packets("kitty-alpha-v1", db_path=db_path)
        assert {b["packet_id"] for b in blocked} == {"KB-E2"}

    def test_successful_attempt_clears_exhaustion(self, db_path: Path):
        manifest = _manifest(
            packets=[
                _packet(
                    "KB-E1",
                    policy={"max_attempts": 2, "priority": 5},
                ),
            ]
        )
        bi.apply_manifest(manifest, db_path=db_path)
        # First attempt fails...
        attempt1 = ba.start_attempt(
            "kitty-alpha-v1", "KB-E1", db_path=db_path
        )
        ba.close_attempt(attempt1["id"], ba.ATTEMPT_FAILED, db_path=db_path)
        # Second attempt succeeds.
        attempt2 = ba.start_attempt(
            "kitty-alpha-v1", "KB-E1", db_path=db_path
        )
        ba.close_attempt(
            attempt2["id"], ba.ATTEMPT_SUCCEEDED, db_path=db_path
        )

        status = bi.initiative_status("kitty-alpha-v1", db_path=db_path)
        assert status["exhausted"] == []
        assert status["state"] == bi.INITIATIVE_ACTIVE

    def test_historical_attempt_records_preserved(self, db_path: Path):
        self._apply_and_exhaust(db_path, max_attempts=2)
        attempts = ba.list_attempts(
            "kitty-alpha-v1", "KB-E1", db_path=db_path
        )
        assert len(attempts) == 2
        assert all(a["outcome"] == ba.ATTEMPT_FAILED for a in attempts)


class TestReadProjectionDerivation:
    """Pure status helpers must stay aligned with scheduler-owned semantics."""

    @pytest.mark.parametrize(
        ("dependency_state", "expected_state"),
        [
            (bq.DONE, "eligible"),
            (bq.RUNNING, "waiting"),
            (bq.BLOCKED, "waiting"),
            (bq.FAILED, "blocked"),
            (bq.CANCELLED, "blocked"),
        ],
    )
    def test_packet_eligibility_matches_dependency_semantics(
        self,
        dependency_state: str,
        expected_state: str,
    ):
        result = bi.derive_packet_eligibility(
            packet_id="KB-A2",
            task_state=bq.QUEUED,
            depends_on=["KB-A1"],
            task_states={"KB-A1": dependency_state, "KB-A2": bq.QUEUED},
            exhausted_packet_ids=set(),
        )

        assert result == {
            "state": expected_state,
            "blocked_by": [] if expected_state == "eligible" else ["KB-A1"],
        }

    def test_packet_eligibility_reports_missing_dependency_data(self):
        result = bi.derive_packet_eligibility(
            packet_id="KB-A2",
            task_state=bq.QUEUED,
            depends_on=["KB-A1"],
            task_states={"KB-A2": bq.QUEUED},
            exhausted_packet_ids=set(),
        )

        assert result == {"state": "unavailable", "blocked_by": ["KB-A1"]}

    @pytest.mark.parametrize(
        ("kwargs", "expected_state"),
        [
            ({"total_packets": 2, "done_count": 2}, bi.INITIATIVE_COMPLETED),
            ({"has_failed": True}, bi.INITIATIVE_FAILED),
            ({"has_exhausted": True}, bi.INITIATIVE_FAILED),
            ({"has_eligible": False}, bi.INITIATIVE_PAUSED),
            ({}, bi.INITIATIVE_ACTIVE),
        ],
    )
    def test_initiative_state_uses_canonical_rollup_precedence(
        self,
        kwargs: dict,
        expected_state: str,
    ):
        inputs = {
            "stored_state": bi.INITIATIVE_ACTIVE,
            "total_packets": 2,
            "done_count": 0,
            "has_blocked": False,
            "has_failed": False,
            "has_exhausted": False,
            "has_eligible": True,
        }
        inputs.update(kwargs)

        assert bi.derive_initiative_state(**inputs) == expected_state

    def test_stored_pause_takes_precedence(self):
        assert bi.derive_initiative_state(
            stored_state=bi.INITIATIVE_PAUSED,
            total_packets=1,
            done_count=1,
            has_blocked=False,
            has_failed=False,
            has_exhausted=False,
            has_eligible=False,
        ) == bi.INITIATIVE_PAUSED


class TestKbS1bCli:
    def test_status_active(self, cli_db, capsys):
        path = _write_manifest(cli_db.parent.parent, _manifest())
        assert main(["initiative", "apply", str(path)]) == 0
        capsys.readouterr()

        assert main(["initiative", "status", "kitty-alpha-v1"]) == 0
        out = capsys.readouterr().out
        assert "[active]" in out
        assert "KB-A1" in out

    def test_status_json_contains_rollup(self, cli_db, capsys):
        path = _write_manifest(cli_db.parent.parent, _manifest())
        assert main(["initiative", "apply", str(path)]) == 0
        capsys.readouterr()

        assert main(["initiative", "status", "kitty-alpha-v1", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["state"] == "active"
        assert payload["next_packet"] == "KB-A1"

    def test_status_missing_initiative(self, cli_db, capsys):
        assert main(["initiative", "status", "ghost"]) == 1
        assert "not found" in capsys.readouterr().err


class TestCp04HealthMetrics:
    """CP-04: read-only health block derived from attempts/events."""

    def _implementation(self, status: str = "completed") -> dict:
        return {
            "contract_version": ba.CONTRACT_VERSION,
            "status": status,
            "summary": "did the thing",
        }

    def _review(self, verdict: str) -> dict:
        return {
            "contract_version": ba.CONTRACT_VERSION,
            "verdict": verdict,
            "summary": "reviewed",
        }

    def test_attempts_per_packet_and_first_pass_approval(self, db_path: Path):
        manifest = _manifest(
            packets=[
                _packet("KB-H1", policy={"max_attempts": 3}),
                _packet("KB-H2", depends_on=[]),
            ]
        )
        bi.apply_manifest(manifest, db_path=db_path)

        # KB-H1: first attempt request_changes, second attempt approve.
        a1 = ba.start_attempt("kitty-alpha-v1", "KB-H1", db_path=db_path)
        ba.record_implementation_result(a1["id"], self._implementation(), db_path=db_path)
        ba.record_review_result(a1["id"], self._review("request_changes"), db_path=db_path)
        ba.close_attempt(a1["id"], ba.ATTEMPT_FAILED, db_path=db_path)

        a2 = ba.start_attempt("kitty-alpha-v1", "KB-H1", db_path=db_path)
        ba.record_implementation_result(a2["id"], self._implementation(), db_path=db_path)
        ba.record_review_result(a2["id"], self._review("approve"), db_path=db_path)
        ba.close_attempt(a2["id"], ba.ATTEMPT_SUCCEEDED, db_path=db_path)

        # KB-H2: single attempt, first-pass approve.
        b1 = ba.start_attempt("kitty-alpha-v1", "KB-H2", db_path=db_path)
        ba.record_implementation_result(b1["id"], self._implementation(), db_path=db_path)
        ba.record_review_result(b1["id"], self._review("approve"), db_path=db_path)
        ba.close_attempt(b1["id"], ba.ATTEMPT_SUCCEEDED, db_path=db_path)

        health = bi.initiative_status("kitty-alpha-v1", db_path=db_path)["health"]
        assert health["attempts_per_packet"]["avg"] == 1.5
        assert health["attempts_per_packet"]["max"] == 2
        # 1 of 2 packets had an approving *first* attempt.
        assert health["first_pass_review_approval_rate"] == 0.5
        assert health["exhausted_count"] == 0

    def test_exhausted_count_reflects_attempt_budget_spent(self, db_path: Path):
        manifest = _manifest(
            packets=[_packet("KB-H1", policy={"max_attempts": 1})]
        )
        bi.apply_manifest(manifest, db_path=db_path)
        attempt = ba.start_attempt("kitty-alpha-v1", "KB-H1", db_path=db_path)
        ba.close_attempt(attempt["id"], ba.ATTEMPT_FAILED, db_path=db_path)

        health = bi.initiative_status("kitty-alpha-v1", db_path=db_path)["health"]
        assert health["exhausted_count"] == 1

    def test_stop_class_counts_absent_when_no_decisions_made(self, db_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        health = bi.initiative_status("kitty-alpha-v1", db_path=db_path)["health"]
        assert health["stop_class_counts"] == {}

    def test_stop_class_counts_tallied_from_decision_events(self, db_path: Path):
        result = bi.apply_manifest(_manifest(), db_path=db_path)
        task_id = result["packets"][0]["task_id"]
        bq.append_event(
            task_id,
            "initiative_decision",
            payload={"stop_class": "needs_decision", "decision": "packet_exhausted"},
            db_path=db_path,
        )
        bq.append_event(
            task_id,
            "initiative_decision",
            payload={"stop_class": "routine", "decision": "packet_succeeded"},
            db_path=db_path,
        )

        health = bi.initiative_status("kitty-alpha-v1", db_path=db_path)["health"]
        assert health["stop_class_counts"] == {"needs_decision": 1, "routine": 1}

    def test_health_metrics_are_read_only(self, db_path: Path):
        bi.apply_manifest(_manifest(), db_path=db_path)
        before = sqlite3.connect(db_path).execute(
            "SELECT COUNT(*) FROM events"
        ).fetchone()[0]

        bi.initiative_status("kitty-alpha-v1", db_path=db_path)

        after = sqlite3.connect(db_path).execute(
            "SELECT COUNT(*) FROM events"
        ).fetchone()[0]
        assert after == before

    def test_health_block_present_in_cli_json_status(self, cli_db, capsys):
        path = _write_manifest(cli_db.parent.parent, _manifest())
        assert main(["initiative", "apply", str(path)]) == 0
        capsys.readouterr()

        assert main(["initiative", "status", "kitty-alpha-v1", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert "health" in payload
        assert "attempts_per_packet" in payload["health"]

    def test_health_summary_line_in_human_readable_status(self, cli_db, capsys):
        path = _write_manifest(cli_db.parent.parent, _manifest())
        assert main(["initiative", "apply", str(path)]) == 0
        capsys.readouterr()

        assert main(["initiative", "status", "kitty-alpha-v1"]) == 0
        out = capsys.readouterr().out
        assert "health:" in out
