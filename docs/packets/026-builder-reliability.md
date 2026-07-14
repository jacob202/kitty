# Packet 026 — Builder reliability and truthful state

**Status:** implementation in progress · reliability rails landed locally; closeout evidence still required
**Priority:** next Builder packet
**Class:** `active_packet`
**Best executor:** Codex or Claude Code with an independent reviewer
**Owner:** Jacob/Codex for state-machine decisions; executor for bounded implementation

## Current implementation slice

The local implementation now has read-only worktree/Git preflight before an
attempt is opened, task/attempt-scoped context artifacts with identity/hash
validation, deterministic worker diff digests, SHA-bound reviewer context and
post-review drift rejection, infrastructure-failure events that do not count
toward the attempt budget, truthful initiative evidence fields, and the
`initiative run-packet --watch` launch surface. The packet remains in progress:
restart/recovery proof and the full operator-completed/review-approved closeout
scenario still need to be exercised before marking it complete.

## Why this packet exists

The current Builder has the right seams — isolated worktrees, context
manifests, attempt rows, run manifests, deterministic validation, and review
contracts — but the last LF-01 run exposed the failure mode this packet must
close: a stale runner omitted `KB_CONTEXT_MANIFEST_PATH`, the worker never
received repository context, and the attempt budget was exhausted without a
truthful distinction between infrastructure failure, worker failure, and
operator recovery.

This packet is the reliability gate for every later free-worker packet. It
must make a failed run inspectable and restartable without making a green
claim that the evidence does not support.

## Objective

Make KittyBuilder capable of launching and recovering the next packet wave
without babysitting while preserving fail-loud behavior and exact evidence.

The implementation must:

1. preflight worktree and Git metadata permissions before consuming an
   implementation attempt;
2. always pass, validate, and hash `KB_CONTEXT_MANIFEST_PATH` for both worker
   and reviewer;
3. isolate every bundle, result, review, manifest, log, and run by task and
   run/attempt identity;
4. make packet and initiative rollups truthful for blocked, exhausted,
   operator-completed, reviewed, PR-opened, and done states;
5. represent `worker failed → operator completed → reviewer approved` as three
   separate facts, never as a fabricated worker success;
6. keep infrastructure/setup failures from consuming implementation budget
   when no worker process could start;
7. bind reviewer input to an exact commit SHA, changed-path set, and diff
   digest, rejecting a changed worktree or mismatched result; and
8. add restart/recovery coverage plus one safe command that launches and
   monitors a packet with durable progress output.

## Visible demo

After this packet lands, the operator can run one command such as:

```bash
./kitty builder initiative run-packet <initiative-id> 026 \
  --worker-command '["scripts/kittybuilder_opencode_worker.sh"]' \
  --review-command '["scripts/kittybuilder_opencode_reviewer.sh"]' \
  --watch --json
```

The command must perform the read-only preflight before opening an attempt,
emit phase transitions and the durable task/run/attempt identifiers, and end
with a truthful summary pointing at the exact run manifest and artifact
directory. A preflight failure must exit non-zero before the attempt budget
changes.

## Scope — files likely touched

Use the existing seams. Do not add a second queue, runner, database, or
telemetry service.

- `[MOD]` `gateway/builder_runner.py` — permission preflight, process-start
  boundary, worktree start SHA, changed-path/diff capture, and recovery-safe
  run evidence.
- `[MOD]` `gateway/builder_loop.py` — manifest path propagation/validation,
  task+attempt artifact roots, infrastructure-vs-worker classification,
  reviewer SHA/diff binding, and phase events.
- `[MOD]` `gateway/builder_attempt.py` — explicit outcome/evidence fields or
  event helpers that keep non-consuming infrastructure failures separate from
  implementation attempts; version the review context if the contract needs
  new fields.
- `[MOD]` `gateway/builder_initiative.py` — deterministic rollups that expose
  packet-level facts instead of collapsing every non-green result into
  `failed` or `paused`.
- `[MOD]` `gateway/builder_run.py` — restart/recovery reconciliation and
  truthful initiative summaries.
- `[MOD]` `gateway/builder_doctor.py` — read-only checks for every preflight
  prerequisite, including writable/executable worktree and Git metadata
  paths.
- `[MOD]` `gateway/builder_cli.py` — add the `--watch`/safe launch surface and
  make its output point to durable evidence; preserve the existing explicit
  `--publish` operator gate.
- `[MOD]` `scripts/kittybuilder_opencode_worker.sh` and
  `scripts/kittybuilder_opencode_reviewer.sh` — reject missing, external, or
  mismatched context/result paths and preserve the exact SHA inputs.
- `[MOD]` `docs/KITTYBUILDER_ORCA_SETUP.md` — document the final adapter,
  preflight, recovery, review-SHA, and monitoring contract.
- `[NEW/MOD]` targeted tests in `tests/test_builder_runner.py`,
  `tests/test_builder_loop.py`, `tests/test_builder_attempt.py`,
  `tests/test_builder_initiative.py`, `tests/test_builder_run.py`,
  `tests/test_builder_doctor.py`, `tests/test_builder_cli.py`, and
  `tests/test_kittybuilder_opencode_adapters.py`.

No Kitty UI, provider/auth/secrets, GitHub mutation, publish behavior, or T2
security-boundary redesign belongs in this packet. If a schema migration is
required, stop and split it into a separately reviewed packet before changing
the database.

## Required state/evidence contract

The exact field names may follow the existing code style, but the persisted
result must expose these facts independently:

| Fact | Required truth |
| --- | --- |
| `blocked` | The task cannot proceed now; include the durable reason and next operator action. |
| `infrastructure_failed` | Setup/preflight failed before worker execution; `counts_toward_budget=false`. |
| `worker_failed` | A worker process started and failed, timed out, violated scope, or missed its contract. |
| `operator_completed` | An operator supplied/accepted an exact completion SHA and evidence; never rewrite worker history. |
| `review_approved` | An independent reviewer approved that exact SHA and diff digest. |
| `pr_opened` | A PR URL and head SHA were explicitly recorded; never inferred from a branch name. |
| `done` | Completion evidence, required review, and any packet-specific merge/operator gate are all satisfied. |
| `exhausted` | The implementation budget was actually consumed; infrastructure-only failures do not count. |

The rollup must include at minimum: initiative/packet/task IDs, current
state, latest run ID, attempt IDs and counted attempts, infrastructure-failure
count, worker outcome, operator action, reviewer verdict, reviewed SHA, diff
digest, PR metadata, artifact directory, and the next allowed action. Missing
evidence is an explicit `unknown`/failure, never a default success.

## Acceptance criteria

- A read-only preflight catches a non-writable worktree root, non-writable Git
  metadata, missing required tools, or an unsafe existing worktree before
  `start_attempt` increments the packet budget.
- A worker and reviewer both receive an attempt-local
  `KB_CONTEXT_MANIFEST_PATH`; missing, outside-root, stale, or hash-mismatched
  manifests fail loudly and leave the evidence inspectable.
- Two tasks using attempt number `1` cannot read or overwrite one another's
  bundle, result, review, log, or run manifest. A stale artifact from a prior
  run is rejected by identity/hash checks.
- Reviewer input contains the worker's exact `HEAD` SHA, changed paths, and
  diff digest. The review is rejected if `HEAD`, the diff, or the worktree
  changes after capture; a reviewer cannot approve its own mutation.
- A worker failure followed by an operator completion and independent review
  renders all three facts in `initiative-status --json`; it does not report a
  fabricated worker success.
- An infrastructure failure before worker start leaves the implementation
  budget unchanged and records the reason, while a started worker failure
  consumes one implementation attempt and remains retryable only through the
  explicit policy.
- Restarting after a process crash, stale heartbeat, expired lease, missing
  result, or interrupted review reconciles exactly once; it does not duplicate
  attempts, lose artifacts, or mark work `done` without evidence.
- `--watch` prints durable phase transitions and exits non-zero for blocked,
  failed, exhausted, or unverifiable outcomes. The final JSON points to the
  run manifest and artifact directory.
- Existing Builder tests remain green, and new tests cover permission denial,
  manifest omission/mismatch, stale artifact reuse, all rollup facts, exact
  review SHA/diff binding, crash/restart recovery, and the safe command.

## Verification commands

```bash
bash -n scripts/kittybuilder_opencode_worker.sh \
  scripts/kittybuilder_opencode_reviewer.sh
venv/bin/ruff check gateway/builder_runner.py gateway/builder_loop.py \
  gateway/builder_attempt.py gateway/builder_initiative.py gateway/builder_run.py \
  gateway/builder_doctor.py gateway/builder_cli.py tests/test_builder_*.py
venv/bin/python -m pytest \
  tests/test_builder_runner.py tests/test_builder_loop.py \
  tests/test_builder_attempt.py tests/test_builder_initiative.py \
  tests/test_builder_run.py tests/test_builder_doctor.py \
  tests/test_builder_cli.py tests/test_kittybuilder_opencode_adapters.py -q \
  --tb=short
./kitty builder initiative doctor --json
./kitty builder initiative run-packet <initiative-id> 026 \
  --worker-command '["scripts/kittybuilder_opencode_worker.sh"]' \
  --review-command '["scripts/kittybuilder_opencode_reviewer.sh"]' \
  --watch --json
```

The final command must be exercised with a deterministic fake worker/reviewer
fixture in tests. Do not spend a real provider call or consume a real packet
attempt merely to prove the CLI wiring.

## Stop conditions

Stop and report instead of widening this packet when:

- the fix requires changing task-state meanings used by existing packets;
- a migration or destructive cleanup is required;
- GitHub push/PR/merge, credentials, auth, or provider routing must change;
- the reviewer cannot be made independent and SHA-bound; or
- the implementation needs a second queue/daemon/service to monitor work.

## Closeout evidence

The handoff must include the commit SHA, exact focused test result, preflight
fixture result, one successful fake-worker run, one infrastructure-failure
run with unchanged attempt budget, one worker-failure → operator-completed →
review-approved rollup, one restart/recovery run, and the remaining known
uncertainty. Do not call the packet complete from code inspection alone.
