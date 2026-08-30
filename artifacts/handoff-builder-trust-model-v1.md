# HANDOFF / COMPACT — Builder Trust Model design task

**This session:** forensic investigation of the B8 wrong-assignment incident.
**Next task (explicit operator assignment):** **Worker: Design Builder's Trust Model** — full brief in section 1.
**Execution owner of this session:** interactive (no code changed this session).
`.claude/HANDOFF.md` / `.claude/STATE.md` are owned by a **parallel** interactive lane (repository simplification) — leave them alone.

---

## 1. Task brief (verbatim, for the next worker)

"Design Builder’s Trust Model.

Do not propose a bug fix first.

Assume the B8 incident was merely one symptom.

Your task is to design Builder so that this entire class of failures becomes architecturally impossible.

Treat Builder as a distributed control system, not merely a task queue.

Answer these questions from first principles.

1. **What is the canonical source of truth?** There should never be ambiguity between: operator intent, initiative state, packet selection, worker execution, review, publication. Determine which component owns truth for each.

2. **What invariants must always hold?** For example: a worker may only execute an approved packet; approval must be durable; packet selection must never resurrect obsolete work; operator intent cannot be bypassed; stale packets cannot become eligible again without an explicit state transition; every execution must be explainable from durable state. Find every invariant.

3. **Where should trust boundaries exist?** Map every boundary: Operator → Planner → Queue → Packet selection → Lease → Worker → Reviewer → Publisher → Resume loop. Identify where validation belongs and where it does not.

4. **Which failures should become impossible?** Not merely detected. Impossible. Examples: executing obsolete packets, executing superseded work, duplicate ownership, stale approvals, zombie initiatives, leaked attempts, packet resurrection, approval drift.

5. **State machine audit.** Redesign the Builder state machine so every transition is explicit. No implicit recovery. No silent retries. No hidden resurrection. Every transition should have: authority, reason, evidence, audit trail.

6. **Should Builder become event-sourced?** Investigate whether Builder should move toward an append-only event log where every decision can be reconstructed from immutable history instead of inferred from mutable rows. Compare this with the current SQLite design.

7. **Produce Builder Trust Model v1.** The deliverable is not code. It is a permanent architectural document defining: Builder’s trust model, authority hierarchy, invariants, state transitions, failure domains, recovery philosophy, operator authority, autonomous authority, audit requirements. The goal is that any future implementation — whether in SQLite, PostgreSQL, Temporal, or another backend — would still satisfy this trust model. Do not optimize for the B8 bug. Optimize so the next hundred unknown trust failures cannot occur."

---

## 2. Inputs the design MUST incorporate

### 2.1 Forensic facts from this session (evidence-backed)

Committed to `artifacts/forensic-b8-wrong-assignment-2026-08-05.md`. Core findings:

- B8 (`trustworthy-kittybuilder-b2-b10-v1` / `B8-clean-checkout-mission`, task `kb_msb4yx3n_f6e8`) is a **doc-only trivia proof packet**. Its worker ran correctly; the failure is **selection**, not the worker.
- **Budget never exhausts:** `_attempts_exhausted` counts only `_BUDGET_CONSUMING_OUTCOMES={failed,aborted}` vs `policy.max_attempts`; `crashed` is budget-neutral and `grant_attempt` (`builder_attempt.py:599`) ratcheted 3→7. Result: 9 attempts (5 crashed / 4 failed) yet **not exhausted**.
- **Recovery resurrection:** `next_packet` (`builder_initiative.py:1273`) returns B8 when blocked + leaked open attempt (`outcome IS NULL`, `_recovery_packets` `:1236`) because attempt 111 was never closed. `run_packet` (`builder_loop.py:749-781`) auto-releases blocked tasks; the repair loop auto-releases between retries (`:956-964`).
- **Escalation is record-only:** `_classify_exhaustion` (`builder_run.py:68-92`) returns `stop_class=needs_decision` for the identity escalation, but `run_initiative` (`builder_run.py:545-591`) logs `continued_after_packet_failure` + `continue` → `idle` → **exit 0** (`builder_cli.py:1521`). Nothing gates on `needs_decision`.
- **Operator intent never entered the system:** "Repair first-run onboarding and Work navigation" has no row in `builder_queue.db`. Selection is decoupled from approval.
- The worker's commits failed identity verification at `builder_identity.py:245-258` (commit subject must contain `[B8-clean-checkout-mission]`); that catch fired only after the worker ran and committed.
- Driver of the repeat runs: tmux `builder-b2-b10` (created 2026-08-05 08:48:46 L) running `./kitty builder initiative run trustworthy-kittybuilder-b2-b10-v1 --free ...`. Hourly drain (`nightly_packet_drain.sh`) was **not** the driver (all Aug 5 drains ran `kx-06`, idle).

### 2.2 Design constraints already decided (do not relitigate)

- **ADR 0036 (accepted, parallel lane):** preserve SQLite/native Builder; **no** migration to Temporal/Hatchet/Prefect/Dagster. The Trust Model v1 must hold *within* the current backend and be backend-agnostic in statement. Question 6 still calls for the event-sourcing tradeoff analysis, but the conclusion must fit ADR 0036.
- ADR 0017 (Mission owns product intent; Builder owns execution state), ADR 0021 (proactive selection), CP-03 stop classification (`docs/plans/KITTYBUILDER_DAILY_DRIVER_PLAN.md` §1.3/§4.4).
- Parallel lane also produced (uncommitted on main): `docs/adr/0028..0036`, `docs/ROADMAP_V2.md`, `docs/initiatives/v2-driver-baseline-v1.json` — read them for direction; do not modify.

### 2.3 Minimum invariants the trust model must enforce (from forensics)

1. A `needS_decision` / escalation terminal state is a **hard gate**: no re-selection, no silent retry, non-zero exit, operator override must be durable and post-date the escalation.
2. "Exhausted" ≠ "idle": a packet that finished all attempts without success must never appear as ordinary eligible work.
3. Every worker launch must trace to a **durable approval** whose approval is still valid; unapproved/obsolete work cannot be launched.
4. A leaked open attempt must be closed/reconciled before *any* code may treat the packet as recoverable.
5. No hidden resurrection: a packet can only become eligible again via an explicit, recorded state transition (authority + reason + evidence).

---

## 3. Live state snapshot (verified 2026-08-05)

- main HEAD: `4c0bf06b` (parallel lane: "simplify: archive dead unreferenced code…") — **behind origin/main by 72**, ahead 1.
- Dirty on main: `.claude/HANDOFF.md`, `.claude/STATE.md`, `docs/adr/README.md`, `docs/memory-stale.md`, `docs/skill-improvement-queue.md` (parallel lane's; don't touch).
- Untracked on main: `artifacts/` (this session's forensics + handoff), `docs/ROADMAP_V2.md`, `docs/adr/0028–0036`, `docs/initiatives/v2-driver-baseline-v1.json` (parallel lane's).
- Builder DB: `data/kittybuilder/builder_queue.db`. B2–B7 done, **B8 blocked**, B9/B10 queued-behind-B8. 22 worktrees.
- PRs open: #406 `proof/two-week-builder-loop`, #391 `docs/paa-alignment-profile`.
- tmux `builder-b2-b10` alive, last pane `idle … exhausted: B8`.

## 4. Where the deliverable lands

- Produced as a permanent doc, e.g. `docs/plans/builder-trust-model-v1.md` (or `docs/reference/` per codebase conventions). **No code.** If the model implies a concrete minimal patch, list it as a recommendation with file/line references — do not implement.
- Record durable findings in `~/kb/wiki/YYYY-MM-DD-slug.md` + one INDEX line; update `~/kb/NOW.md` on close.

## 5. Execution rules for the design worker

- This is an **interactive** task, not a Builder packet (ADRs: one execution owner). Do not claim/run/drain Builder.
- Read `START_HERE.md` / `docs/ARCHITECTURE.md` / `docs/DECISIONS.md` / `docs/reference/CODEBASE_MAP.md` before writing.
- No commit/push/PR without explicit authorization.
