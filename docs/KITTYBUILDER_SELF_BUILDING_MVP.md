# KittyBuilder Self-Building MVP — Roadmap

Goal: autonomously execute a multi-phase Kitty Alpha build with minimal
operator babysitting. The single-task layer (queue state machine, claims,
lease fencing, recovery, worker briefs, shadow runner) is done — this roadmap
is the orchestration layer above it.

Constraints (hold for every packet): single repo, single machine, sequential
packet execution, operator-controlled merge, no orchestration framework, no
distributed workers, no dashboard, no general-purpose planning. The queue
task state machine is used unchanged; orchestration state lives in separate
tables (`initiatives`, `initiative_packets`, later `packet_attempts`).

## Packets

### KB-S1A — Initiative manifest, persistence, validation ✅ (this PR)

`gateway/builder_initiative.py`: versioned JSON manifests, canonicalization +
SHA-256, semantic validation (duplicate IDs, missing/self/cyclic deps,
policies, acceptance criteria, allowed paths), atomic + idempotent apply that
materializes one queue task per packet with a stable mapping, dry-run, and
`./kitty builder initiative validate|apply|list|show`.

### KB-S1B — Packet eligibility and initiative status ✅ (this PR)

- `eligible_packets(initiative_id)`: packets whose dependencies' tasks are
  all `done`, own task still `queued`.
- `next_packet(initiative_id)`: deterministic selection (seq order among
  eligible; priority is advisory metadata only).
- Initiative status rollup: per-packet task state → initiative
  `active | completed | failed | paused`; `initiative status` CLI.
- Blocked-forever detection: dependency task `failed/cancelled` → report the
  packet as unreachable rather than silently never-eligible.
- No execution here — pure reads over existing state.

### KB-S2 — Context bundles and result contracts ✅ (this PR)

- Bounded context bundle per packet: brief (existing `builder_brief`) +
  manifest objective/acceptance/paths + prior-attempt summaries, persisted in
  a `packet_attempts` table so retries see what attempt N-1 did and why it
  failed.
- Structured implementation-result contract (JSON: status, diff summary,
  validation output, claims) and review-result contract (verdict, findings).
  Reuse `builder_contract.py` validation style; hard size caps on every
  free-text field.

### KB-S3 — Deterministic validation, independent review, bounded repair

- Validation stage: run the packet's declared checks (pytest slice, mypy,
  ruff, `git diff --check`) in the task worktree; results recorded on the
  attempt, pass/fail is deterministic.
- Independent review: a second worker invocation with a review brief and no
  memory of the implementation conversation; emits the review contract.
- Repair loop: implement → validate → review → repair, capped by
  `policy.max_attempts`; each attempt is a new run record via the existing
  runner. Cap exhausted → task `blocked`, initiative pauses.

### KB-S4 — Push, PR, CI reconciliation, merge detection

- Safe branch push from the task worktree (existing branch naming,
  `kittybuilder/<task_id>`), PR create-or-update via `gh` with the final
  report as body.
- CI + review state sync into the existing advisory `pr_links` table
  (`attach-pr` machinery); merge detection promotes the task
  `awaiting_review → done`, which unlocks dependent packets.
- Merge remains operator-controlled; the builder never merges.

### KB-S5 — Continuation loop, budgets, pause/resume, restart reconciliation

- `initiative run` driver: loop { next eligible packet → S2/S3 pipeline →
  S4 } until no packet is eligible (all done, or blocked awaiting operator
  merge/decision).
- Durable decisions log (why a packet was blocked/skipped/repaired) in the
  events table.
- Budgets: per-packet and per-initiative attempt/time caps; exceeding pauses
  the initiative with a stated reason.
- Pause/resume CLI; on restart, reconcile via existing run/lease recovery,
  then resume the loop idempotently (re-applying the manifest is a no-op;
  in-flight tasks are recovered by the existing machinery).

## Order and dependencies

S1A → S1B → S2 → S3 → S4 → S5. Each packet lands as one reviewed PR with
focused tests plus the full Builder regression suite (pytest, mypy, ruff,
`git diff --check`).
