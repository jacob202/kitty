#!/usr/bin/env python3.12
"""Live Builder recovery proof for roadmap outcome 1.1.

Drives the real Builder queue through five induced failure modes plus one
clean completion, using deterministic local worker fixtures instead of a model
provider. Every assertion reads the operator-visible ``./kitty builder`` JSON
surfaces, so a passing run is evidence an operator can reproduce by hand.

The harness never contacts a provider, never pushes, and never opens a PR. It
applies its manifest under a per-run initiative id so repeat runs stay
isolated, and it archives its tasks and removes its worktrees on the way out.

Usage:
    python3.12 scripts/builder_recovery_proof.py [--json] [--keep]
                                                 [--report PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_TEMPLATE = REPO_ROOT / "docs/initiatives/phase1-1-recovery-proof-v1.json"
DEFAULT_REPORT = REPO_ROOT / "docs/research/phase1-1-builder-recovery-proof.md"

# The adapter contract's provider-exhaustion signal (gateway/builder_loop.py).
PROVIDER_EXHAUSTED_EXIT_CODE = 75


class ProofError(RuntimeError):
    """A harness precondition failed; the proof could not be run at all."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def kitty(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a ``./kitty`` subcommand from the repository root."""
    result = subprocess.run(
        [str(REPO_ROOT / "kitty"), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if check and result.returncode != 0:
        raise ProofError(
            f"./kitty {' '.join(args)} exited {result.returncode}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def kitty_json(*args: str, check: bool = True) -> Any:
    """Run a ``./kitty`` subcommand and parse its JSON payload.

    The CLI prefixes some commands with human warnings on stdout, so this
    parses from the first ``{`` or ``[`` rather than the first byte.
    """
    result = kitty(*args, check=check)
    text = result.stdout
    start = min(
        (i for i in (text.find("{"), text.find("[")) if i >= 0),
        default=-1,
    )
    if start < 0:
        raise ProofError(
            f"./kitty {' '.join(args)} produced no JSON: {text.strip()!r}"
        )
    return json.loads(text[start:])


class Fixtures:
    """Deterministic worker/reviewer scripts standing in for a model."""

    def __init__(self, directory: Path) -> None:
        self.dir = directory

    def _write(self, name: str, body: str) -> str:
        path = self.dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        return str(path)

    def completing_worker(self, marker: str, text: str) -> str:
        return self._write(
            f"worker_{marker}.sh",
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "mkdir -p data/recovery_proof\n"
            f"printf '{text}\\n' > data/recovery_proof/{marker}.txt\n"
            'cat > "${KB_RESULT_PATH}" <<JSON\n'
            '{"contract_version":1,"status":"completed",'
            f'"summary":"wrote data/recovery_proof/{marker}.txt",'
            f'"diff_summary":"data/recovery_proof/{marker}.txt",'
            '"validation":{"passed":true,"output":"fixture validation ok"},'
            f'"claims":["wrote data/recovery_proof/{marker}.txt"]}}\n'
            "JSON\n",
        )

    def crashing_worker(self, marker: str) -> str:
        """Writes partial output, then SIGKILLs itself mid-execution."""
        return self._write(
            f"worker_{marker}_crash.sh",
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "mkdir -p data/recovery_proof\n"
            f"printf 'partial write before crash' > data/recovery_proof/{marker}.txt\n"
            "kill -9 $$\n",
        )

    def debris_worker(self, debris_path: str) -> str:
        """Dirties a tracked path and exits 0 without writing a result."""
        return self._write(
            "worker_debris.sh",
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f"printf '\\n<!-- recovery-proof debris -->\\n' >> {debris_path}\n",
        )

    def exhausted_worker(self) -> str:
        return self._write(
            "worker_exhausted.sh",
            "#!/usr/bin/env bash\n"
            'echo "every configured free provider was unavailable" >&2\n'
            f"exit {PROVIDER_EXHAUSTED_EXIT_CODE}\n",
        )

    def failing_worker(self) -> str:
        """Exits non-zero without a result — a plain worker failure."""
        return self._write(
            "worker_failing.sh",
            "#!/usr/bin/env bash\n"
            'echo "worker could not implement the packet" >&2\n'
            "exit 1\n",
        )

    def crashing_reviewer(self) -> str:
        return self._write(
            "reviewer_crash.sh",
            "#!/usr/bin/env bash\nkill -9 $$\n",
        )


class Scenario:
    """One induced failure and the facts Builder must record about it."""

    def __init__(self, packet_id: str, name: str) -> None:
        self.packet_id = packet_id
        self.name = name
        self.checks: list[dict[str, Any]] = []
        self.evidence: dict[str, Any] = {}

    def check(self, claim: str, passed: bool, observed: Any) -> None:
        self.checks.append(
            {"claim": claim, "passed": bool(passed), "observed": observed}
        )

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c["passed"] for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "name": self.name,
            "passed": self.passed,
            "checks": self.checks,
            "evidence": self.evidence,
        }


class RecoveryProof:
    def __init__(self, *, keep: bool) -> None:
        self.keep = keep
        self.started_at = utc_now()
        self.run_suffix = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        self.initiative_id = f"phase1-1-recovery-proof-{self.run_suffix}"
        self.scenarios: list[Scenario] = []
        self.task_ids: dict[str, str] = {}
        self.workdir = Path(".")
        self.baseline_doctor: dict[str, Any] = {}
        self.final_doctor: dict[str, Any] = {}
        self.head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    # -- setup ---------------------------------------------------------------

    def pid(self, base_packet_id: str) -> str:
        """Suffix a template packet id with this run's identifier.

        Branch-lease identity treats packet ids as globally unique across
        initiatives, so a repeat run reusing the template ids is rejected as
        ambiguous. Suffixing keeps every proof run independent.
        """
        return f"{base_packet_id}-{self.run_suffix}"

    def apply_manifest(self, workdir: Path) -> None:
        manifest = json.loads(MANIFEST_TEMPLATE.read_text(encoding="utf-8"))
        manifest["initiative_id"] = self.initiative_id
        for packet in manifest["packets"]:
            packet["id"] = self.pid(packet["id"])
        path = workdir / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        kitty("builder", "initiative", "validate", str(path))
        applied = kitty_json("builder", "initiative", "apply", str(path), "--json")
        self.task_ids = {p["packet_id"]: p["task_id"] for p in applied["packets"]}

    def doctor(self) -> dict[str, Any]:
        return kitty_json("builder", "initiative", "doctor", "--json", check=False)

    def run_packet(self, packet_id: str, worker: str, reviewer: str | None = None):
        args = [
            "builder", "initiative", "run-packet", self.initiative_id, packet_id,
            "--worker-command", json.dumps([worker]),
            "--no-governor", "--json",
        ]
        if reviewer is not None:
            args[args.index("--no-governor"):args.index("--no-governor")] = [
                "--review-command", json.dumps([reviewer])
            ]
        return kitty_json(*args, check=False)

    def task_events(self, packet_id: str) -> list[dict[str, Any]]:
        return kitty_json(
            "builder", "queue", "events", self.task_ids[packet_id], "--json",
            check=False,
        )

    def packet_status(self, packet_id: str) -> dict[str, Any]:
        status = kitty_json(
            "builder", "initiative", "status", self.initiative_id, "--json",
            check=False,
        )
        evidence = (status.get("evidence") or {}).get(packet_id)
        if evidence is None:
            raise ProofError(f"packet {packet_id} missing from initiative status")
        return evidence

    # -- scenarios -----------------------------------------------------------

    def scenario_crash(self, fx: Fixtures) -> Scenario:
        s = Scenario(self.pid("RP-01-crash-proto"), "Worker crash mid-execution")
        result = self.run_packet(s.packet_id, fx.crashing_worker("rp01"))
        attempt = (result.get("attempts") or [{}])[-1]
        run = kitty_json(
            "builder", "queue", "show-run", attempt.get("run_id", ""), "--json",
            check=False,
        ) if attempt.get("run_id") else {}
        worktree = REPO_ROOT / ".worktrees/kittybuilder" / self.task_ids[s.packet_id]
        partial = worktree / "data/recovery_proof/rp01.txt"
        blocked = [
            e for e in self.task_events(s.packet_id)
            if e.get("type") == "blocked"
        ]

        s.evidence = {
            "run_outcome": result.get("outcome"),
            "attempt_outcome": attempt.get("outcome"),
            "exit_code": run.get("exit_code"),
            "blocked_reasons": [e.get("payload", {}).get("reason") for e in blocked],
            "partial_output_path": str(partial),
        }
        s.check(
            "the crashed attempt is not recorded as succeeded",
            attempt.get("outcome") != "succeeded",
            attempt.get("outcome"),
        )
        s.check(
            "the real kill signal is recorded as the exit code",
            run.get("exit_code") == -9,
            run.get("exit_code"),
        )
        s.check(
            "the failure is attributed to the worker, not invented",
            any(
                e.get("payload", {}).get("reason") == "worker_failed"
                for e in blocked
            ),
            s.evidence["blocked_reasons"],
        )
        s.check(
            "partial work written before the crash survives in the worktree",
            partial.is_file() and "partial" in partial.read_text(encoding="utf-8"),
            partial.is_file(),
        )
        return s

    def scenario_stale_lease(self, fx: Fixtures) -> Scenario:
        s = Scenario(
            self.pid("RP-02-stale-lease-proto"),
            "Stale claim lease reconciliation",
        )
        task_id = self.task_ids[s.packet_id]
        kitty(
            "builder", "queue", "claim", task_id,
            "--worker", "recovery-proof-abandoned",
            "--lease-seconds", "1", "--json",
        )
        claimed = kitty_json("builder", "queue", "show", task_id, "--json")
        time.sleep(2)
        recovered = kitty_json("builder", "queue", "recover", "--json")
        after = kitty_json("builder", "queue", "show", task_id, "--json")
        events = self.task_events(s.packet_id)
        result = self.run_packet(s.packet_id, fx.completing_worker("rp02", "rp02 ok"))

        s.evidence = {
            "state_while_claimed": claimed.get("state"),
            "recover_summary": recovered,
            "state_after_recover": after.get("state"),
            "rerun_outcome": result.get("outcome"),
        }
        s.check(
            "the task was genuinely claimed before the lease expired",
            claimed.get("state") == "claimed",
            claimed.get("state"),
        )
        s.check(
            "the recovery scan requeued the expired claim",
            recovered.get("claimed_requeued", 0) >= 1,
            recovered.get("claimed_requeued"),
        )
        s.check(
            "the task is queued again rather than left claimed",
            after.get("state") == "queued",
            after.get("state"),
        )
        s.check(
            "the release is written to the event trail, not applied silently",
            any("release" in str(e.get("type", "")) or
                "requeue" in str(e.get("type", "")) for e in events),
            sorted({str(e.get("type")) for e in events}),
        )
        s.check(
            "the packet completes normally after recovery",
            result.get("outcome") == "succeeded",
            result.get("outcome"),
        )
        return s

    def scenario_dirty_worktree(self, fx: Fixtures) -> Scenario:
        s = Scenario(
            self.pid("RP-03-dirty-worktree-proto"),
            "Out-of-scope debris is caught and preserved",
        )
        debris_path = "AGENTS.md"
        result = self.run_packet(s.packet_id, fx.debris_worker(debris_path))
        attempt = (result.get("attempts") or [{}])[-1]
        run = kitty_json(
            "builder", "queue", "show-run", attempt.get("run_id", ""), "--json",
            check=False,
        ) if attempt.get("run_id") else {}
        worktree = REPO_ROOT / ".worktrees/kittybuilder" / self.task_ids[s.packet_id]
        debris = worktree / debris_path
        report = run.get("final_report") or {}
        dirty_files = (report.get("worktree_state") or {}).get("dirty_files") or []

        s.evidence = {
            "attempt_outcome": attempt.get("outcome"),
            "failure": attempt.get("failure"),
            "dirty_files": dirty_files,
            "changed_paths": report.get("changed_paths"),
            "debris_path": str(debris),
        }
        s.check(
            "the attempt is recorded as failed, not succeeded",
            attempt.get("outcome") == "failed",
            attempt.get("outcome"),
        )
        s.check(
            "the failure names the out-of-scope change specifically",
            "allowed scope" in str(attempt.get("failure", "")),
            attempt.get("failure"),
        )
        s.check(
            "the uncommitted debris survives the failed attempt",
            debris.is_file()
            and "recovery-proof debris" in debris.read_text(encoding="utf-8"),
            debris.is_file(),
        )
        s.check(
            "the dirty worktree is reported rather than hidden",
            debris_path in dirty_files or debris_path in (report.get("changed_paths") or []),
            {"dirty_files": dirty_files, "changed_paths": report.get("changed_paths")},
        )
        return s

    def scenario_interrupted_review(self, fx: Fixtures) -> Scenario:
        s = Scenario(
            self.pid("RP-04-interrupted-review-proto"),
            "Interrupted review stays honest",
        )
        result = self.run_packet(
            s.packet_id,
            fx.completing_worker("rp04", "rp04 ok"),
            reviewer=fx.crashing_reviewer(),
        )
        attempt = (result.get("attempts") or [{}])[-1]

        s.evidence = {
            "implementation_status": attempt.get("implementation_status"),
            "validation_status": attempt.get("validation_status"),
            "attempt_outcome": attempt.get("outcome"),
            "failure": attempt.get("failure"),
        }
        s.check(
            "the implementation is recorded as completed",
            attempt.get("implementation_status") == "completed",
            attempt.get("implementation_status"),
        )
        s.check(
            "validation is recorded as passed",
            attempt.get("validation_status") == "passed",
            attempt.get("validation_status"),
        )
        s.check(
            "the attempt is not reported as succeeded without a review",
            attempt.get("outcome") != "succeeded",
            attempt.get("outcome"),
        )
        s.check(
            "the failure blames the review interruption, not the worker",
            "review" in str(attempt.get("failure", "")).lower(),
            attempt.get("failure"),
        )
        return s

    def scenario_provider_exhausted(self, fx: Fixtures) -> Scenario:
        s = Scenario(
            self.pid("RP-05-provider-exhausted-proto"),
            "Provider exhaustion is distinct",
        )
        result = self.run_packet(s.packet_id, fx.exhausted_worker())
        attempt = (result.get("attempts") or [{}])[-1]
        packet = self.packet_status(s.packet_id)

        s.evidence = {
            "run_outcome": result.get("outcome"),
            "task_state": result.get("task_state"),
            "attempt_outcome": attempt.get("outcome"),
            "provider_exhausted": attempt.get("provider_exhausted"),
            "packet_exhausted": packet.get("exhausted"),
            "packet_state": packet.get("current_state"),
            "attempts_used": packet.get("attempts_used"),
            "attempt_budget": packet.get("attempt_budget"),
        }
        s.check(
            "the run reports provider exhaustion, not a worker failure",
            result.get("outcome") == "provider_exhausted",
            result.get("outcome"),
        )
        s.check(
            "the attempt is flagged as provider-exhausted",
            attempt.get("provider_exhausted") is True,
            attempt.get("provider_exhausted"),
        )
        s.check(
            "the task returns to queued so the packet stays resumable",
            result.get("task_state") == "queued",
            result.get("task_state"),
        )
        s.check(
            "the exhausted attempt is budget-neutral",
            packet.get("exhausted") is not True,
            packet.get("exhausted"),
        )
        return s

    def scenario_operator_closeout(self, fx: Fixtures) -> Scenario:
        """Packet 026's untested acceptance criterion, exercised end to end.

        A worker failure, then an operator completion, then an independent
        review approval must render as three separate facts. The failure mode
        this guards against is the rollup quietly reporting a worker success
        that never happened.
        """
        s = Scenario(
            self.pid("RP-07-operator-closeout-proto"),
            "Worker failure, operator completion, independent review",
        )
        task_id = self.task_ids[s.packet_id]

        # Deliberately NOT run_packet: its repair loop retries a failing worker
        # until the budget is gone, which leaves no attempt for the operator.
        # Driving the attempts by hand is the only way to reach this workflow.
        worker_attempt = kitty_json(
            "builder", "initiative", "start-attempt",
            self.initiative_id, s.packet_id, "--json",
        )
        worker_attempt_id = worker_attempt.get("attempt_id") or worker_attempt.get("id")
        worker_result = self.workdir / "worker_failed.json"
        worker_result.write_text(
            json.dumps(
                {
                    "contract_version": 1,
                    "status": "failed",
                    "summary": "worker could not implement the packet",
                    "diff_summary": "",
                    "validation": {"passed": False, "output": "not attempted"},
                    "claims": [],
                }
            ),
            encoding="utf-8",
        )
        kitty(
            "builder", "initiative", "record-implementation", str(worker_attempt_id),
            "--file", str(worker_result), "--json",
        )
        kitty(
            "builder", "initiative", "close-attempt", str(worker_attempt_id), "failed",
            "--json",
        )
        after_failure = self.packet_status(s.packet_id)

        # The operator supplies the completion and says so on the record; the
        # `operator: true` flag on report_attached is what separates this from
        # a worker's own result.
        report = self.workdir / "operator_report.json"
        report.write_text(
            json.dumps(
                {
                    "outcome": "completed",
                    "summary": "operator completed the packet by hand after the worker failed",
                    "completion_sha": self.head_sha,
                }
            ),
            encoding="utf-8",
        )
        kitty(
            "builder", "queue", "attach-report", task_id,
            "--report-file", str(report),
            "--operator-reason", "recovery proof: operator-completed closeout",
            "--json",
        )

        # A review cannot be attached to a closed attempt, and the worker's
        # attempt closed when it failed — so the operator's work needs an
        # attempt of its own. This is the only supported shape, and it only
        # works while the packet still has budget.
        opened = kitty_json(
            "builder", "initiative", "start-attempt",
            self.initiative_id, s.packet_id, "--json",
            check=False,
        )
        attempt_id = opened.get("attempt_id") or opened.get("id")

        implementation = self.workdir / "operator_implementation.json"
        implementation.write_text(
            json.dumps(
                {
                    "contract_version": 1,
                    "status": "completed",
                    "summary": "operator completed the packet by hand",
                    "diff_summary": "data/recovery_proof/rp07.txt",
                    "validation": {"passed": True, "output": "operator verified"},
                    "claims": ["operator wrote data/recovery_proof/rp07.txt"],
                }
            ),
            encoding="utf-8",
        )
        kitty(
            "builder", "initiative", "record-implementation", str(attempt_id),
            "--file", str(implementation), "--json",
        )

        review = self.workdir / "review_approve.json"
        review.write_text(
            json.dumps(
                {
                    "contract_version": 1,
                    "verdict": "approve",
                    "summary": "independent reviewer approved the operator's completion",
                    "findings": [],
                }
            ),
            encoding="utf-8",
        )
        review_result = kitty(
            "builder", "initiative", "record-review", str(attempt_id),
            "--file", str(review), "--json",
            check=False,
        )
        kitty(
            "builder", "initiative", "close-attempt", str(attempt_id), "succeeded",
            "--json",
        )
        final = self.packet_status(s.packet_id)

        s.evidence = {
            "worker_attempt_id": worker_attempt_id,
            "operator_attempt_id": attempt_id,
            "worker_failed_after_failure": after_failure.get("worker_failed"),
            "record_review_exit": review_result.returncode,
            "final": {
                key: final.get(key)
                for key in (
                    "worker_failed", "operator_completed", "review_approved",
                    "review_verdict", "operator_action", "attempts_used",
                    "attempt_outcomes", "done",
                )
            },
        }
        s.check(
            "the worker failure is recorded, not overwritten by the operator",
            final.get("worker_failed") is True,
            final.get("worker_failed"),
        )
        s.check(
            "the operator completion is recorded as an operator action",
            final.get("operator_completed") is True,
            final.get("operator_action"),
        )
        s.check(
            "the independent review approval is recorded",
            final.get("review_approved") is True,
            final.get("review_verdict"),
        )
        s.check(
            "all three facts render together, with no fabricated worker success",
            final.get("worker_failed") is True
            and final.get("operator_completed") is True
            and final.get("review_approved") is True,
            [
                final.get("worker_failed"),
                final.get("operator_completed"),
                final.get("review_approved"),
            ],
        )
        s.check(
            "the review was accepted onto the operator's attempt",
            review_result.returncode == 0,
            review_result.stderr.strip() or review_result.returncode,
        )
        s.check(
            "the worker attempt stays failed and only the operator's succeeds",
            final.get("attempt_outcomes") == ["failed", "succeeded"],
            final.get("attempt_outcomes"),
        )
        return s

    def scenario_clean_completion(self, fx: Fixtures) -> Scenario:
        s = Scenario(
            self.pid("RP-06-clean-completion-proto"),
            "Clean completion after the failures",
        )
        result = self.run_packet(s.packet_id, fx.completing_worker("rp06", "rp06 ok"))
        attempt = (result.get("attempts") or [{}])[-1]

        s.evidence = {
            "run_outcome": result.get("outcome"),
            "implementation_status": attempt.get("implementation_status"),
            "validation_status": attempt.get("validation_status"),
        }
        s.check(
            "the packet succeeds after five induced failures",
            result.get("outcome") == "succeeded",
            result.get("outcome"),
        )
        s.check(
            "implementation and validation are both recorded green",
            attempt.get("implementation_status") == "completed"
            and attempt.get("validation_status") == "passed",
            [attempt.get("implementation_status"), attempt.get("validation_status")],
        )
        return s

    # -- orchestration -------------------------------------------------------

    def run(self) -> bool:
        with tempfile.TemporaryDirectory(prefix="kb-recovery-proof-") as tmp:
            workdir = self.workdir = Path(tmp)
            fx = Fixtures(workdir)
            self.baseline_doctor = self.doctor()
            self.apply_manifest(workdir)

            self.scenarios = [
                self.scenario_crash(fx),
                self.scenario_stale_lease(fx),
                self.scenario_dirty_worktree(fx),
                self.scenario_interrupted_review(fx),
                self.scenario_provider_exhausted(fx),
                self.scenario_operator_closeout(fx),
                self.scenario_clean_completion(fx),
            ]
            self.final_doctor = self.doctor()

        consistency = Scenario("doctor", "Doctor consistency across the run")
        before = self.baseline_doctor.get("summary", {})
        after = self.final_doctor.get("summary", {})
        consistency.evidence = {"before": before, "after": after}
        consistency.check(
            "inducing five failures adds no new doctor FAIL",
            after.get("fail", 0) <= before.get("fail", 0),
            {"before_fail": before.get("fail"), "after_fail": after.get("fail")},
        )
        self.scenarios.append(consistency)

        if not self.keep:
            self.cleanup()
        return all(s.passed for s in self.scenarios)

    def cleanup(self) -> None:
        """Remove this run's worktrees and archive its tasks.

        Cleanup failures are recorded loudly on stderr but never mask the
        proof's own verdict.
        """
        for task_id in self.task_ids.values():
            # Builder correctly refuses to clean the debris scenario's dirty
            # worktree, so fall through to a forced removal the harness owns.
            kitty("builder", "queue", "clean-worktree", task_id, check=False)
            path = REPO_ROOT / ".worktrees/kittybuilder" / task_id
            if path.exists():
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(path)],
                    cwd=REPO_ROOT, capture_output=True, text=True,
                )
                shutil.rmtree(path, ignore_errors=True)
            if path.exists():
                print(
                    f"WARNING: proof worktree survived cleanup: {path}",
                    file=sys.stderr,
                )
        shutil.rmtree(REPO_ROOT / "data/recovery_proof", ignore_errors=True)

    # -- reporting -----------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof": "phase1-1-builder-recovery",
            "initiative_id": self.initiative_id,
            "head_sha": self.head_sha,
            "started_at": self.started_at,
            "finished_at": utc_now(),
            "passed": all(s.passed for s in self.scenarios),
            "scenarios": [s.to_dict() for s in self.scenarios],
            "doctor_baseline": self.baseline_doctor.get("summary"),
            "doctor_final": self.final_doctor.get("summary"),
        }

    def to_markdown(self) -> str:
        data = self.to_dict()
        verdict = "PASS" if data["passed"] else "FAIL"
        lines = [
            "# Phase 1.1 — Builder recovery proof",
            "",
            f"**Verdict:** {verdict}",
            f"**Initiative:** `{data['initiative_id']}`",
            f"**HEAD:** `{data['head_sha']}`",
            f"**Ran:** {data['started_at']} → {data['finished_at']}",
            "",
            "Generated by `scripts/builder_recovery_proof.py`. Every scenario runs",
            "against the real Builder queue with deterministic local worker",
            "fixtures — no model provider is contacted and no spend occurs.",
            "Reproduce with:",
            "",
            "```bash",
            "python3.12 scripts/builder_recovery_proof.py --json",
            "```",
            "",
            "## Scenarios",
            "",
            "| Scenario | Verdict | Checks |",
            "| --- | --- | --- |",
        ]
        for s in data["scenarios"]:
            passed = sum(1 for c in s["checks"] if c["passed"])
            lines.append(
                f"| {s['name']} | {'PASS' if s['passed'] else 'FAIL'} | "
                f"{passed}/{len(s['checks'])} |"
            )
        lines.append("")
        for s in data["scenarios"]:
            lines += [f"### {s['name']} (`{s['packet_id']}`)", ""]
            for c in s["checks"]:
                mark = "PASS" if c["passed"] else "FAIL"
                lines.append(f"- **{mark}** — {c['claim']}")
                lines.append(f"  - observed: `{json.dumps(c['observed'])}`")
            lines += ["", "Evidence:", "", "```json",
                      json.dumps(s["evidence"], indent=2), "```", ""]
        lines += [
            "## Doctor consistency",
            "",
            f"- baseline: `{json.dumps(data['doctor_baseline'])}`",
            f"- final: `{json.dumps(data['doctor_final'])}`",
            "",
        ]
        return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON to stdout")
    parser.add_argument(
        "--keep", action="store_true",
        help="keep the proof's worktrees and tasks for inspection",
    )
    parser.add_argument(
        "--report", type=Path, default=DEFAULT_REPORT,
        help=f"markdown report path (default: {DEFAULT_REPORT})",
    )
    args = parser.parse_args()

    if os.environ.get("KITTY_BUILDER_QUEUE_ENABLED") == "0":
        raise ProofError(
            "the Builder queue kill switch is engaged "
            "(KITTY_BUILDER_QUEUE_ENABLED=0); refusing to run the proof"
        )

    proof = RecoveryProof(keep=args.keep)
    passed = proof.run()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(proof.to_markdown(), encoding="utf-8")

    if args.json:
        print(json.dumps(proof.to_dict(), indent=2))
    else:
        for s in proof.scenarios:
            print(f"{'PASS' if s.passed else 'FAIL'}  {s.name}")
        print(f"\nReport: {args.report}")

    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProofError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
