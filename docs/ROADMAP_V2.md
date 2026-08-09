# Kitty Version 2 — Master Roadmap

**Status:** Ratified target plan — accepted architecture, not execution schedule. Ratified by the Constitution v1 ratification table (2026-08-05). ARCHITECTURE_RATIFICATION_2026-08-06.md Decision 5 governs the relationship with `docs/ROADMAP.md` (active authority).
**Date:** 2026-08-05
**Owner:** Jacob (authorization); Kitty (planning); KittyBuilder (execution)
**Relation to current docs:** this is the Version 2 target plan. `docs/ROADMAP.md` remains the active execution authority (ADR 0020). This doc sequences V2 delivery as releasable milestones (M1–M6).

---

## 0. Why this roadmap

Version 1 proved the trustworthy delivery chain end to end: approved intent →
authored bounded packet → proactive Builder execution → deterministic validation
→ independent review → policy-controlled merge → durable result → concise report
(see `ROADMAP.md` Gates and Phases; the `trustworthy-kittybuilder` initiative; the
B2–B10 worktree/projection/PR/durability/recovery evidence).

Version 2 does **not** replace that chain. It fixes the five subsystem targets and
then simplifies the storage spine:

| Subsystem | Version 2 role |
|---|---|
| **Open WebUI** | Primary daily-driver shell (ADR 0027; replaceable). |
| **Kitty Gateway (FastAPI)** | Intelligence layer; owns truth, routing, memory, tools, approval. |
| **LiteLLM** | Provider abstraction under the Gateway. |
| **Next.js app** | The **Kitty Console** — operator/ops surface (Config, Builder, diagnostics, approvals), not the primary chat shell. |
| **Storage layer** | Consolidated at the end of V2; simplification is a sequenced objective, not a first move. |

### Operating principles

1. Leave the repo working after every milestone, never "we'll total it later".
2. Fail loud — a packet that can't prove an outcome reports the honest blocker, not fabricate.
3. Small packets, small PRs, one execution owner each; no two lanes on the same work.
4. The Console is a thin view over the Gateway's query/command API, not a second engine.
5. Simplification = removing/consolidating/retiring, never adding a parallel store/scheduler.
6. Evidence outranks theory — each packet lands artifacts under `docs/research/`,
   `docs/audit/`, or a proven runbook.

### Governance (already decided, not re-litigated)

- **Open WebUI as daily-driver shell is accepted** (ADR 0027).
- **Gateway stays the authority** (ADR 0003, ADR 0017).
- **LiteLLM stays the provider proxy.**
- **Image Studio / RunPod** is a dedicated authorized lane (issue #306) — not in the
  daily-driver core path; it keeps its own runbook.
- **Storage simplification is a V2 end-state**, sequenced last for user-visible-value and
  risk reasons.

### Key evidence on the current baseline

- `docs/plans/openwebui-agent-handoff-2026-08-02.md` gap #1/#2 (PYTHONPATH shadowing,
  duplicate pending admin) are **already addressed on disk**: `sanitized_env()`
  (`scripts/openwebui_tool/common.py`) drops everything not in the runtime allowlist
  (so `PYTHONPATH`/`PYTHONHOME` are stripped), and the duplicate-admin repair exists in
  `scripts/openwebui_tool/service.py`. Do **not** re-plan those; the V2 baseline is
  "prove what's merged", not "re-invent it".
- Live acceptance (`bootstrap --accept-charges` on the real Mac) was **never recorded
  run** (see `.claude/STATE.md` — PR #384 is MERGED but the paid/live gate is open).
  M1's whole job is closing that gap.

---

## 1. Milestones

Each milestone is user-visible, independently releasable, leaves the tree green, and
reduces complexity. Ordered by dependency.

### M1 — Daily-driver shell is real (Open WebUI pilot, live)

**Objective.** Replace the Next.js shell as the primary daily driver with Open WebUI,
surfacing only Kitty-verified truth, and prove a full normal day of use works.

**Acceptance criteria**
1. `openwebui_local.py bootstrap` from a clean checkout starts exactly one listener each
   for LiteLLM, Gateway, Open WebUI.
2. Login never hits the "account activation pending" trap; a single intentional user row
   exists; `kitty-default` is the deliberate default model; a normal message streams with
   `[DONE]` and a terminal event.
3. Chats and settings persist across a full service restart.
4. `status` / `doctor` / `logs` / `restart` from the canonical checkout drives/reports the
   process that is actually serving; no listener duplication across IPv4/IPv6 or competing
   checkouts (closes ROADMAP outcome 0.5).
5. The Next.js Console only runs on operator request (does not fight Open WebUI for `:3000` /
   does not become a competing chat shell).
6. Independent verifier reproduces #1–#5 from a fresh clone; Jacob confirms a real full day.

**Dependencies:** L0 (repository recovery) — much already landed; the merged Open WebUI
bootstrap (PR #384) and `scripts/openwebui_local.py`.
**Effort:** Medium-Low (largely inheritance from #384).
**Risk:** operator-specific service duplication; bounded paid endpoint cost (see Rollback).
**Rollback:** the existing Next.js UI remains a verified rollback default.
**Testing:** `doctor --json` before/during/after; `openwebui_local.py verify` with and
without `--accept-charges`; browser smoke in Jacob's real environment.
**Success metric:** one full day of real use; `doctor` 0 `fail`; reproducible from a clean
clone and the desktop.

---

### M2 — Console becomes the operator surface (Next.js re-roles)

**Objective.** Stop treating the Next.js app as a competing chat shell; relabel and harden
it as the Kitty Console: Configuration, Builder state, diagnostics, approvals.
Chat moves to Open WebUI.

**Acceptance criteria**
1. `kitty-chat` renders as the operator/console surface with a separate route/role from
   the Open WebUI chat, and no longer probes/claims `:3000` on startup.
2. All Console reads go through Gateway `/state` / Builder projection endpoints; nothing in
   the console hardcodes the model/provider catalog.
3. The console reflects Builder status/queue/leases/decisions from the shared projection,
   matching the CLI for the same queries.
4. A failed/stale subsystem renders `degraded`/`stale` with a reason, never a fabricated
   default (per the product-architecture Phase 1 honesty norm).

**Dependencies:** M1 (gateway truth endpoints).
**Effort:** Medium.
**Risk:** relabeling jobs across old bundles; `.claude` path cleanliness.
**Rollback:** the console remains a deployable surface behind the shell; reverting it
does not disturb the Open WebUI daily driver.
**Test:** `make ui-test`, `make ui-build`; the console claims source still renders improved.
**Metric:** every PR / truth load through Gateway; duplicate talk bubbles reduced to zero.

---

### M3 — Builder → Work integration (shell sees real execution)

**Goal:** the daily loop and the console surface real Builder work as product-level
"Work" and "evidence", with safe approval boundaries.
Covers the product-architecture phase-sequential intent (Bridge product Work/Run IDs to
Builder initiatives/packets/tasks/runs; product language "Plan/Work/Run/Needs approval"
instead of queue/lease/packet-only).

**Acceptance**
1. From Open WebUI chat, an approved command can create/recommend an initiative proposal
   (packet) in a bounded, reviewable form — not arbitrary code execution from chat.
2. Work panel / console surfaces the initiative graph, current packet, run status, review,
   evidence, and open approvals from durable Builder state.
3. Completion requires validated + independently reviewed receipts; a process exit code
   alone is not "complete".
4. No mutation from the shell is write-capable on Builder without explicit operator
   decision (ADR 0027 rule 7 and the approval classes in the product architecture).

**Dependencies:** M2.
**Effort:** Medium (uses Builder's existing projection and READ-only surface).
**Risk:** turning chat into a Builder write-surface; strictly scoped to
"propose → queue with approval".
**Rollback:** the chat→Builder path is additive behind a default-approval gate; disable it
and the shell falls back to read-only.
**Metrics:** operator can see the same queue decisions in Work (CLI/UI) and permission
labor: queue→run→validation→review→merge.

---

### M4 — Failure, interruption, and receipts (honest reliability)

**Objective:** after any provider/network/crash, a turn and a Builder run are
`interrupted`/`failed` with preserved partial state; retry creates a new attempt; Home/
console reports the material one entry, and evidence/receipt terms are fixed.

**Acceptance**
1. Gateway connection is distinct from provider/model health in the UI.
2. Chat/run `interrupted`, `failed`, `stopped`, `retried`, and `complete` (distinct
   durable states) — no silent overwrite on retry.
3. A partial stream preserves its content and is labeled recoverable.
4. Attachments → artifacts with an explicit ingest/receipt; the composer can't claim
   understanding without an ingesting receipt.
5. Every "complete/fixed/saved" claim has the required evidence; otherwise it is an
   explicit failure (product architecture receipt rules).

**Dependencies:** M2 (must already read Gateway truth), M3.
**Effort:** medium.
**Risk:** upstream providers not returning terminals; coverage gaps.
**Testing:** async interruption tests; seeded provider failure; real restart continuity.
**Metric:** no silent overwrite, no fabricated success, on a simulated/normal day.

---

### M5 — Storage spine consolidation (the flagged simplification)

**Goal:** after everyone relies on the Gateway authority and artifact/evidence spines,
reduce the mixed storage sprawl (Kitty SQLite + subsystem SQLite + JSON/JSONL + ChromaDB
+ mem0) to one authoritative app store plus the one derived vector index.

**Acceptance (only after M1–M4 are green):**
1. An inventory/hash count (like `scripts/` migration-health) shows an item-of-truth with
   no migration, and dual-write shadow reads show 0 mismatch over a soak window.
2. Each legacy store either is replaced by the main app DB (authority) or retired; nothing
   is left as a silent duplicate/dead write path.
3. Per-journey cutover with a documented rollback; `./kitty doctor` is green after cutover.

**Dependencies:** M1–M4 (value proven; otherwise you'd consolidate before it's worth).
**Effort:** high; risk: highest in the plan.
**Rollback:** additive migrations, shadow reads, per-journey cutover policy (product
architecture migration section).
**Testing:** dual-write reconciliation reports on seeded data; count/hash parity before/after;
soak a week; restore proof.
**Success:** each subsystem, one truth — reduced maintenance burden; fewer failure modes
from data-shape disagreements (the V2 "reduce maintenance burden" objective).

---

### M6 — Iterate the daily driver and ship the Console official

**Goal:** the Console becomes the supported operator experience (docs, onboarding,
screenshot, backup/restore) and a soft "consolidation" acceptance pass for V2.

**Acceptance**
- Rollback still a one-step to the classic UI.
- Backup/restore proven non-destructive (extended from current `backup-restore-proof`).
- Expanded onboarding docs one-command to the daily shell + console.
- End-to-end journey runbook: select a real life project → resume truthful state → one
  concrete next move → native channel delivery (ROADMAP 1.4, 2.3 wait: M6 is not the
  first shipping of that; it's making it sustainable).

**Effort:** low-medium.

---

## 2. Milestone→ Builder initiative mapping (execution entry)

The roadmap above is sequenced below into **Builder initiatives and packets** that can be
typed as JSON under `docs/initiatives/` and executed. **Packet IDs are M<n>-<NN>-<slug>.**
Each packet (a) is small, (b) has acceptance criteria, allowed_paths, validation
commands, and a policy budget, (c) is independently publishable.

Because M1 lives primarily in the shell/ops script (not the Next app), most of its
packets are operator/live-validation: they cannot be "autonomous" in the trust
sense; they need Jacob's machine, creds, or a bounded paid endpoint.

## 3. Packet catalog

### Full autonomy (Builder can run alone, fully verifiable, no pay/broaden)

- `M1-09` — Add a regression test proving the shell subprocess cannot inherit
  `PYTHONPATH`/`PYTHONHOME` (guards the existing sanitize; fully testable).
- `M2-01` — Console launch and route decouple from `:3000` chat shell; change defaults.
- `M2-04` — Console read-all from Gateway query endpoints (replace hardcoded catalog
  reads). 
- `M2-06` — Responsive/stale render (`degraded`/`stale` with a reason), snapshot pass.
- `M3-03` — Builder read projection for the console/Work panel (non-mutating; JSON).
- `M3-06` — Evidence projection: receipts bind to initiative/task/run queries; no new store.
- `M5-01` — storage inventory (read-only): count/hash of all store types per location.
- `M5-02` — dual-write shadow compare harness (reads only).
- `M6-01` — release/rollback one-step runbook (doc + verify).

### Require operator approval (write/broaden)

- `M3-01` — chat→Builder "propose/recommend" packet (provides an approval flow; goes
  beyond read-only; Jacob must green-light the surface).
- `M3-09` — allow a sandboxed write-to-branch lane RTS a few files (biggest boundary).
- `M1-04` — make bootstrap idempotent across login/unclean-shutdown, with the 
  duplicate-account behavior (already present) given a smoke test and operator sign-off.

### Require manual/live testing

- `M1-01`, `M1-02`, `M1-03` — live bootstrap, `--accept-charges`, full-day pilot
  (they are Jacob-machine live validation; the code may be done, the person must confirm).
- `M1-05` — IPv4/IPv6 listener-parity `./kitty up` / `down` from two worktrees
  (ROADMAP 0.5 verification — live nic, manual).
- `M4-03` — restart-continuity live test (vs a real full cycle).

### Require architectural review

- `M2-01` — Console surface/model-catalog ownership (design review before splitting roles).
- `M3-09` — the sandbox approved write lane (architectural boundary).
- `M5-03` through `M5-0x` — storage-retirement plan (architecture: which legacy store,
  which authority, what dies).
- `M6-xx` — checkout of the Console as official daily operator (product decision).

## 3. First 10 packets, ordered by dependency

| Order | Packet | Milestone | Class |
|---|---|---|---|
| 1 | `M1-01` prove bootstrap clean-checkout → 3 listeners → verify | M1 | live |
| 2 | `M1-02` live verification (accept-charges) bounded | M1 | live |
| 3 | `M1-09` PYTHONPATH regression test | M1 | autonomous |
| 4 | `M1-05` IPv4/IPv6 listener parity fix | M1 | live+fix |
| 5 | `M2-04` Console reads all truth from Gateway | M2 | autonomous |
| 6 | `M2-06` stale/degraded render | M2 | autonomous |
| 7 | `M1-03` Jacob full-day validation | M1 | manual |
| 8 | `M3-03` Builder read projection to console | M3 | autonomous |
| 9 | `M3-01` propose/recommend chat→Builder (approve gate) | M3 | operator |
| 10 | `M3-06` receipts bind evidence (no new store) | M3 | autonomous |

Rationale for the ten (dependency): prove the driver is live and trustworthy first
(M1), then make the console a read-only-visible ops surface (M2), only then add Builder
"propose" — so new capabilities sit on proven truth.

## 4. What is explicitly NOT in Version 2 scope

- Rewriting the Gateway or the Builder state machine.
- Building a second chat engine inside the console.
- New feature lanes (job search, expanded connector Zoo) until the M1–M4 proof passes.
- Expanding proxy/provider adapters as a goal.
- Any storage migration before M1–M4 are green.

## 5. How to advance from here

1. Jacob reviews this roadmap (M numbering/M scope, esp. M3 write-bounds).
2. A planner authors the first `docs/initiatives/v2-driver-baseline-v1.json` per
   `docs/FREE_MODEL_PACKET_STANDARD.md` and `docs/INITIATIVES_OPTIMIZED`.
3. Builder runs packet M1-01, M1-09 first (autonomous, low risk), parallel to Jacob
    recording a live `--accept-charges` run per `M1-02`.
4. Review M2 before re-purposing the Next.js app to Console.
5. Gate M5 (storage) only after M1–M4 evidence is real.