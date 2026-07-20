"""Audit \u00a72.2 third-cut cross-module tests for gateway.builder_queue_runs.

These tests guard the \u00a72.2 third-cut extraction:

1. Fa\u00e7ade identity (rendered as Facade in this file to keep Python
   identifiers ASCII-clean) \u2014 every run symbol reachable through ``bq.*`` must be
   the *same object* as the same symbol on ``builder_queue_runs``. ``__all__``
   covers the 16-symbol set; ``facade_identity_bq_is_bqr`` asserts each.
2. Public-surface location \u2014 the symbols live in ``builder_queue_runs`` (not
   in ``builder_queue`` itself \u2014 the cut extracted them, the file does not
   redefine them).
3. End-to-end run lifecycle via the ``bq`` alias \u2014 ``create_task`` then
   ``claim_task`` then ``create_run`` then ``update_run`` (running with PID) then
   ``finalize_run`` completes and lands the task in ``blocked``.

Pattern mirrors ``tests/test_builder_queue.py`` so pytest discovery is
consistent.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from gateway import builder_queue as bq
from gateway import builder_queue_runs as bqr


class FacadeIdentityTest(unittest.TestCase):
    """All 16 run symbols must reach the same object via bq.* and bqr.*."""

    def test_facade_identity_bq_is_bqr(self) -> None:
        symbols = [
            "create_run",
            "get_run",
            "list_runs",
            "update_run",
            "finalize_run",
            "generate_run_id",
            "capture_process_identity",
            "recover_interrupted_runs",
            "RUN_ACTIVE_STATES",
            "RUN_TERMINAL_STATES",
            "RUN_STARTING",
            "RUN_INTERRUPTED",
            "RUN_LEASE_LOST",
            "RUN_SCOPE_VIOLATION",
            "RUN_RUNNING",
            "RUN_TIMEOUT",
        ]
        for sym in symbols:
            with self.subTest(sym=sym):
                bq_v = getattr(bq, sym)
                bqr_v = getattr(bqr, sym, None)
                self.assertIsNotNone(bqr_v, f"{sym} missing on builder_queue_runs")
                self.assertIs(
                    bq_v,
                    bqr_v,
                    f"bq.{sym} is not the same object as bqr.{sym} "
                    f"(facade is shadowing the import)",
                )

    def test_run_exceptions_facade_identity(self) -> None:
        sym_pairs = [
            ("RunNotFoundError", "RunNotFoundError"),
            ("ActiveRunConflictError", "ActiveRunConflictError"),
            ("RunStateConflictError", "RunStateConflictError"),
        ]
        for bq_name, bqr_name in sym_pairs:
            with self.subTest(sym=bq_name):
                self.assertIs(getattr(bq, bq_name), getattr(bqr, bqr_name))

    def test_run_symbols_are_NOT_defined_locally_on_builder_queue(self) -> None:
        """The cut extracted the run functions; ``builder_queue`` must NOT
        still own them -- it should only re-export via facade import."""
        from gateway import builder_queue as module  # noqa: WPS433 - intentional
        from gateway.builder_queue_runs import (
            create_run as runs_create_run,
        )
        from gateway.builder_queue_runs import (
            finalize_run as runs_finalize_run,
        )

        local_create_run = module.__dict__.get("create_run")
        if local_create_run is not None:
            self.assertIs(
                local_create_run,
                runs_create_run,
                "builder_queue.create_run should be the same object as "
                "builder_queue_runs.create_run (likely the file still "
                "defines the function locally, defeating the cut)",
            )
        local_finalize_run = module.__dict__.get("finalize_run")
        if local_finalize_run is not None:
            self.assertIs(
                local_finalize_run,
                runs_finalize_run,
                "builder_queue.finalize_run should be the same object as "
                "builder_queue_runs.finalize_run",
            )


class RunLifecycleTest(unittest.TestCase):
    """End-to-end create_run/update_run/finalize_run via the bq alias."""

    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".sqlite", delete=False
        )
        self._tmp_path = Path(self._tmp.name)
        self._tmp.close()
        bq.init_db(self._tmp_path)

    def tearDown(self) -> None:
        if self._tmp_path.exists():
            self._tmp_path.unlink()

    def _create_and_claim_task(self) -> tuple[str, str, int]:
        task = bq.create_task("\u00a72.2 third-cut smoke", db_path=self._tmp_path)
        claimed = bq.claim_task(
            task["id"], "worker-test", lease_seconds=60, db_path=self._tmp_path
        )
        return (
            task["id"],
            str(claimed["lease_token"]),
            int(claimed["claim_version"]),
        )

    def test_create_update_finalize_round_trip(self) -> None:
        task_id, lease_token, claim_version = self._create_and_claim_task()

        run = bq.create_run(
            task_id,
            ["python3", "-c", "print('hello')"],
            lease_token=lease_token,
            claim_version=claim_version,
            worker="worker-test",
            db_path=self._tmp_path,
        )
        self.assertEqual(run["state"], bq.RUN_STARTING)
        self.assertEqual(run["task_id"], task_id)
        run_id = str(run["id"])

        # Worker normally transitions the TASK to RUNNING right after create_run;
        # finalize_run's runner_owns_running_task branch only fires when both the
        # task AND the run are running under the current lease.
        bq.worker_transition_task(
            task_id,
            bq.RUNNING,
            lease_token=lease_token,
            claim_version=claim_version,
            payload={"run_id": run_id, "worker": "worker-test"},
            db_path=self._tmp_path,
        )

        pid = os.getpid()
        identity = bq.capture_process_identity(pid) or "test-identity"
        advanced = bq.update_run(
            run_id,
            state=bq.RUN_RUNNING,
            pid=pid,
            process_identity=identity,
            mark_started=True,
            mark_heartbeat=True,
            expected_states=frozenset({bq.RUN_STARTING}),
            db_path=self._tmp_path,
        )
        self.assertEqual(advanced["state"], bq.RUN_RUNNING)
        self.assertEqual(int(advanced["pid"]), pid)
        self.assertEqual(advanced["process_identity"], identity)

        finalized = bq.finalize_run(
            run_id,
            bq.RUN_EXITED,
            exit_code=0,
            report={"outcome": bq.RUN_EXITED, "smoke": "ok"},
            lease_token=lease_token,
            claim_version=claim_version,
            block_reason="shadow_run_complete",
            db_path=self._tmp_path,
        )
        self.assertEqual(finalized["state"], bq.RUN_EXITED)
        self.assertEqual(finalized["exit_code"], 0)
        self.assertEqual(finalized["final_report"]["outcome"], bq.RUN_EXITED)
        self.assertEqual(
            finalized["final_report"]["task_update"], "blocked_by_runner"
        )

        # With the runner fenced on the running task, finalize should have
        # blocked the task with the supplied reason AND cleared the lease
        # columns (audit §1.3 reliability: BLOCKED tasks must not retain a
        # phantom-but-unrenewed lease that ``recover_expired_leases`` would
        # never sweep).
        final_task = bq.get_task(task_id, db_path=self._tmp_path)
        self.assertIsNotNone(final_task)
        self.assertEqual(final_task["state"], bq.BLOCKED)
        self.assertEqual(final_task["blocked_reason"], "shadow_run_complete")
        self.assertIsNone(final_task["lease_token"])
        self.assertIsNone(final_task["lease_owner"])
        self.assertIsNone(final_task["lease_expires_at"])

    def test_finalize_lease_lost_when_token_mismatched(self) -> None:
        """finalize_run must upgrade to RUN_LEASE_LOST when the fence fails.

        Simulates a race where another worker has stolen the lease:
        the original worker passes a stale lease_token to finalize_run;
        the fence check fails; finalize_run correctly upgrades the outcome
        to RUN_LEASE_LOST and leaves the task untouched.
        """
        task_id, original_token, claim_version = self._create_and_claim_task()

        # Original worker creates a run with the lease it still holds.
        run = bq.create_run(
            task_id,
            ["python3", "-c", "pass"],
            lease_token=original_token,
            claim_version=claim_version,
            worker="original-worker",
            db_path=self._tmp_path,
        )
        # Worker advances the TASK to RUNNING under its current (still-valid) lease.
        bq.worker_transition_task(
            task_id,
            bq.RUNNING,
            lease_token=original_token,
            claim_version=claim_version,
            payload={"run_id": run["id"]},
            db_path=self._tmp_path,
        )
        bq.update_run(
            run["id"],
            state=bq.RUN_RUNNING,
            pid=os.getpid(),
            process_identity=bq.capture_process_identity(os.getpid()) or "x",
            expected_states=frozenset({bq.RUN_STARTING}),
            db_path=self._tmp_path,
        )

        # Simulate a successful steal: another worker overrode our lease_token.
# (Direct DB write is the cleanest way to model this without time-traveling
# the SQLite clock.)
        import gateway.builder_queue_db as _db
        stolen_conn = _db.connect(self._tmp_path)
        try:
            stolen_conn.execute(
                "UPDATE tasks SET lease_token = ?, lease_owner = ?, claim_version = claim_version + 1 "
"                WHERE id = ?",
                ('THIS-IS-A-NEW-LONG-LEASE-TOKEN-xxxx-yyyy-zzzz-aaaa-bbbb-cccc-dddd', 'stealing-worker', task_id),
            )
            stolen_conn.commit()
        finally:
            stolen_conn.close()

        # Original worker finalizes with its STALE lease_token;
# the fence check fails; finalize_run correctly upgrades to RUN_LEASE_LOST.
        finalized = bq.finalize_run(
            run["id"],
            bq.RUN_EXITED,
            exit_code=0,
            report={"outcome": bq.RUN_EXITED},
            lease_token=original_token,
            claim_version=claim_version,
            block_reason="stale_run",
            db_path=self._tmp_path,
        )
        self.assertEqual(finalized["state"], bq.RUN_LEASE_LOST)
        self.assertEqual(finalized["final_report"]["outcome"], bq.RUN_LEASE_LOST)
        self.assertEqual(
            finalized["final_report"]["task_update"], "skipped_lease_lost"
        )

    def test_recover_interrupted_runs_returns_count_dict(self) -> None:
        result = bq.recover_interrupted_runs(db_path=self._tmp_path)
        for key in (
            "runs_interrupted",
            "starting_runs_deferred",
            "runs_unverified",
            "running_tasks_blocked",
            "claimed_tasks_requeued",
            "conflicts",
        ):
            with self.subTest(key=key):
                self.assertIn(key, result)
                self.assertIsInstance(result[key], int)
        self.assertEqual(result["runs_interrupted"], 0)


class BranchLeaseFacadeIdentityTest(unittest.TestCase):
    """The 4 branch-lease symbols must reach the same object via bq.* and bqbl.*."""

    def test_branch_lease_facade_identity(self) -> None:
        from gateway import builder_queue_branch_leases as bqbl

        sym_pairs = [
            ("claim_branch_lease", "claim_branch_lease"),
            ("verify_branch_lease", "verify_branch_lease"),
            ("get_branch_lease", "get_branch_lease"),
            ("release_branch_lease", "release_branch_lease"),
        ]
        for bq_name, bqbl_name in sym_pairs:
            with self.subTest(sym=bq_name):
                self.assertIs(
                    getattr(bq, bq_name),
                    getattr(bqbl, bqbl_name),
                    f"bq.{bq_name} is not the same object as "
                    f"bqbl.{bqbl_name} (facade is shadowing the import)",
                )


class BranchLeaseRoundTripTest(unittest.TestCase):
    """Branch lease lifecycle: claim / verify / release with fence-clause."""

    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".sqlite", delete=False
        )
        self._tmp_path = Path(self._tmp.name)
        self._tmp.close()
        bq.init_db(self._tmp_path)

    def tearDown(self) -> None:
        if self._tmp_path.exists():
            self._tmp_path.unlink()

    def test_claim_release_round_trip(self) -> None:
        bq.claim_branch_lease(
            "packet-r1", "worker-r1", "branch-r1", "/tmp/wt-r1", "a" * 40,
            db_path=self._tmp_path,
        )
        self.assertIsNotNone(bq.verify_branch_lease("packet-r1", db_path=self._tmp_path))
        lease = bq.verify_branch_lease("packet-r1", db_path=self._tmp_path)
        bq.release_branch_lease(
            lease["lease_id"], packet_id="packet-r1", worker_id="worker-r1",
            db_path=self._tmp_path,
        )
        self.assertIsNone(
            bq.verify_branch_lease("packet-r1", db_path=self._tmp_path)
        )

    def test_duplicate_claim_rejected(self) -> None:
        bq.claim_branch_lease(
            "packet-r2", "worker-r2", "branch-r2", "/tmp/wt-r2", "b" * 40,
            db_path=self._tmp_path,
        )
        with self.assertRaises(Exception) as ctx:
            bq.claim_branch_lease(
                "packet-r2", "worker-r2", "branch-r2", "/tmp/wt-r2", "c" * 40,
                db_path=self._tmp_path,
            )
        self.assertIn("Conflict", type(ctx.exception).__name__)

    def test_wrong_worker_release_rejected(self) -> None:
        bq.claim_branch_lease(
            "packet-r3", "worker-r3", "branch-r3", "/tmp/wt-r3", "d" * 40,
            db_path=self._tmp_path,
        )
        lease = bq.verify_branch_lease("packet-r3", db_path=self._tmp_path)
        with self.assertRaises(Exception) as ctx:
            bq.release_branch_lease(
                lease["lease_id"],
                packet_id="packet-r3",
                worker_id="NOT-WORKER",
                db_path=self._tmp_path,
            )
        self.assertIn("Conflict", type(ctx.exception).__name__)


class IdHelpersTest(unittest.TestCase):
    """Shared ID-generation helpers reachable from sibling modules."""

    def test_to_base36_helper(self) -> None:
        from gateway import _id_helpers as idh

        self.assertEqual(idh.to_base36(0), "0")
        self.assertEqual(idh.to_base36(35), "z")
        self.assertEqual(idh.to_base36(36), "10")
        with self.assertRaises(ValueError):
            idh.to_base36(-1)

    def test_generate_id_with_base36_shape(self) -> None:
        from gateway import _id_helpers as idh

        task_id = idh.generate_id_with_base36("kb")
        run_id = idh.generate_id_with_base36("run")
        self.assertRegex(task_id, r"^kb_[0-9a-z]+_[0-9a-f]{4}$")
        self.assertRegex(run_id, r"^run_[0-9a-z]+_[0-9a-f]{4}$")
