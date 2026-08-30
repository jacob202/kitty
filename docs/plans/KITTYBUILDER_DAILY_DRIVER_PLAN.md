# KittyBuilder Daily-Driver Plan — Campaigns, Prototype Gate, KB-S5 Finish

**Produced:** 2026-07-21, planning session (Fable 5) running
`docs/archive/builder-campaign-framework-2026-07/PLANNING_PROMPT.md`.
**Verified against:** `main` at `0e2f711509bcbf0e1af2faab924e1006a5e857ff`,
canonical checkout `~/Projects/kitty`. Every mechanism claim below was checked
against the cited file in this session; inferences are marked as such.
**Hand-off:** this document is the work order for Claude Code (Sonnet 5).
Read §0.5 (execution contract) first — it is binding. Execute packets
CP-01 → CP-08. CP-09 (mission ingress) is named but NOT authorized.
**Revised 2026-07-21 (same session) on Jacob's instructions:** auto-merge
replaces human merge (owner decision, §4.1), workers get skills/scripts
(CP-07), and every checkpoint that previously waited on Jacob now has an
automated owner, a default action, and a timeout. Jacob's only job is
reading reports.

---

## 0.5 Execution contract for Claude Code (binding)

### Kickoff

1. Run the cold-start bootloader from `CLAUDE.md` (verify checkout, `git
   status`, `./kitty context --agent`, read `.claude/STATE.md`).
2. Invoke Jacob's process skills if they exist in your environment:
   `/goals`, then `/design`, then `/feature-developer` per packet, `/loop`
   as the outer driver. These are global Claude Code commands (they are NOT
   in this repo — verified: repo skills are only `catchup`, `debug-fix`,
   `remember`, `second-opinion`). **If a named skill doesn't resolve, do
   not stall and do not ask — this document is the fallback operating
   procedure and is sufficient on its own.**
3. Create the task list from §2, then execute. Local commits per packet;
   run the suite after every non-trivial change and report counts
   (CLAUDE.md execution defaults).

### Pre-granted authorizations (Jacob, 2026-07-21, this session)

Assume granted — do not ask again:

- Branch pushes, PR creation, and **PR merges for work under this plan and
  for Builder campaign branches**, once the §4.1 evidence gate passes.
  This is the explicit approval CLAUDE.md non-negotiable #4 requires;
  CP-06 records it durably as ADR 0018 so it survives this session.
- Launching as many subagents as useful, in parallel, per the model policy
  below.
- Installing dev/test dependencies needed by a packet's tests.

Still excluded — these were NOT granted and stay hard gates: touching
secrets/auth/`.env`, deleting user data, external messages (email/SMS/posts),
real-money spending, force-push/history rewrites, and heavy runtime
dependencies (new DBs/services/frameworks — needs an ADR first).

### Subagent and model policy (cost-follows-need)

Route every subagent to the cheapest model that can complete its task —
same principle as ADR 0017's worker routing ("high price is not evidence
of quality"):

| Task class | Model |
|---|---|
| Search, file location, citation checking, mechanical edits, test-running, report generation | Haiku |
| Packet implementation, test writing, refactors within a stated design | Sonnet |
| Architecture judgment, `needs_decision` resolution, final cross-packet review | top paid tier, sparingly |

Parallelize what the dependency graph allows: lanes A (CP-01→02→07),
B (CP-03→04→05), and C (CP-06, once CP-03's stop classes exist) run
concurrently; only CP-08 joins them (see §2 lane table). Builder's own campaign runs stay serial
(`run_initiative` is a serial loop by design — don't parallelize inside an
initiative).

### Checkpoint policy: nothing waits on Jacob

Every decision point that previously required Jacob now has an owner, a
default, and a timeout. Apply these:

| Checkpoint | Owner | Default action | Timeout |
|---|---|---|---|
| Clarification question Jacob doesn't answer | executing session | record the assumption with disposition (ADR 0017 `assumptions[]` pattern), take the most conservative reading, proceed | ask once, proceed immediately if no answer in-session |
| Prototype direction approval | independent reviewer (paid model) judging the diff against the campaign brief | `approve` → auto-merge, continue; `reject` → one repair round, then `needs_decision` | none — synchronous |
| Routine packet merge | the evidence gate (§4.1) | merge on green, auto-revert on post-merge red | none — synchronous |
| `needs_decision` stop | Jacob, but foolproofed: one yes/no question with a recommended default, delivered in the report | take the recommended default | 24 h, then default is taken, loudly logged, revertible |
| Budgets | predefined | `max_attempts` 12/initiative, 2/prototype, 3/packet; runtime 4 h/initiative run | pause with stop class on breach, re-launch is automatic on next `/loop` pass |

The one rule that survives foolproofing: every automated decision leaves a
durable event and shows up in the CP-05 report. Jacob can always revert;
he can never be silently bypassed on the excluded list above.

---

## 0. The honest scope statement (read first)

The planning prompt framed this as "design the campaign lifecycle." The audit
found something smaller and better: **most of the campaign runtime already
exists on `main`.** Specifically:

- Budgets, pause/resume, and restart reconciliation — the core of KB-S5 —
  are implemented: `builder_run.run_initiative` enforces per-initiative
  attempt and runtime budgets and pauses with a stated reason
  (`gateway/builder_run.py`, `max_initiative_attempts` /
  `max_runtime_seconds` branches); per-packet attempt budgets come from
  `policy.max_attempts` (`builder_initiative._packet_max_attempts`,
  `_attempts_exhausted`); `initiative pause`/`initiative resume` exist in
  `gateway/builder_cli.py`; the loop starts with `recover_expired_leases` +
  `recover_interrupted_runs`.
- **The prototype gate needs zero new runtime.** In
  `builder_initiative.eligible_packets`, a dependency is satisfied only when
  the upstream task's state is `DONE` — and `done` is reached only via merge
  detection (`builder_queue.detect_merged_prs` → `_promote_merged_task`) or
  operator action. A prototype packet that every other packet `depends_on`
  is therefore already a hard gate: nothing downstream can start until the
  prototype task promotes to `done` via merge. (First draft made Jacob the
  merger; owner decision moved that to the reviewer + CP-06 auto-merge —
  the *mechanism* is unchanged, only the gatekeeper.)
- The standalone path (want #5) already exists and stays untouched:
  `queue add` + `queue run <id> -- <worker-command>` runs one bounded task
  with no initiative, no clarification, no gate (`gateway/builder_cli.py`,
  `queue-run` CommandSpec).

What is actually missing, in order of daily-use impact:

1. **The clarification round** — a repeatable procedure that turns "I want X"
   into a tight manifest, including asking Jacob questions. (Gap #2.)
2. **The prototype convention** — when to insert a prototype packet, and what
   its acceptance criteria look like. (Gap #3.)
3. **The judgment layer on stops** — today every pause looks the same.
   The archived framework's kill-switch asymmetry (real ambiguity halts loud;
   routine failure retries quiet) is not implemented anywhere. (Gap #4's
   remaining half.)
4. **A bounded result artifact** — one file Jacob reads after a run instead
   of spelunking `data/kittybuilder/`. (Gap #7, minimal cut.)
5. **Unattended merge** — the loop currently parks at `awaiting_review`
   until a human merges. Owner decision 2026-07-21: automate it behind an
   evidence gate with auto-revert (CP-06, §4.1).
6. **Skills/scripts in worker context** — workers currently get scope +
   criteria but no pointers to the repo's existing scripts and skills, so
   they burn tokens rediscovering or rewriting what exists (CP-07).
7. **Mission ingress (ADR 0017 runtime)** — deliberately deferred. See CP-09.

Total authorized work: **CP-01–CP-08, roughly 9–12 agent-days serial —
compressible to ~1 calendar week with parallel subagents (§0.5), plus one
day of unattended dogfood runtime.** The prior 4–6 week anchor covered
mission ingress and full artifact delivery; ingress stays deferred because
it doesn't block daily use.

---

## 1. Campaign lifecycle design

### 1.1 The state machine (what attaches where)

A "campaign" is not a new runtime object. It is a manifest-authoring
convention plus the existing initiative/queue machinery. No new tables, no
new states, no manifest schema change.

```
 PHASE                  RUNS IN                 EXISTING MECHANISM USED
 ─────                  ───────                 ───────────────────────
 clarify                paid-model session      none (procedure, CP-01)
   │                    (Claude Code / Kitty
   │                     chat with Jacob)
   ▼
 manifest authored      same session            docs/packets/TEMPLATE.md style,
   │                                            builder_initiative manifest schema
   ▼
 validate + apply       CLI                     initiative validate / apply
   │                                            (builder_initiative.validate_manifest,
   │                                             apply_manifest — atomic, one queued
   │                                             task per packet)
   ▼
 [prototype packet]     initiative run          builder_run.run_initiative →
   │  (only if the      (--free by default)     builder_loop.run_packet:
   │   §1.2 threshold                           worktree → worker → validation →
   │   fires)                                   review → bounded repair
   ▼
 GATE: reviewer         independent reviewer    eligible_packets: deps satisfied
   │  judges prototype   (paid model, judges     only at DONE; CP-06 merges on
   │  against campaign   direction vs brief)     approve + green gate, then
   │  brief; approve →                           detect_merged_prs promotes →
   │  auto-merge;                                downstream unlocks in the same
   │  reject → 1 repair,                         run. `--gate manual` flag keeps
   │  then needs_decision                        the old park-and-wait behavior.
   ▼
 implement packets      initiative run          same loop, continues in the same
   │  (dependency order)                        invocation once deps promote;
   │                                            re-launch is idempotent (re-apply
   │                                            no-op, recovery at loop start)
   ▼
 publish + merge        evidence gate (§4.1)    queue publish / --publish
   │                                            (KB-S4b gates) + CP-06 auto-merge,
   │                                            auto-revert on post-merge red
   ▼
 done                   automated               Jacob reads the CP-05 report;
                                                 revert is his veto, not his task
```

Task-level states are unchanged: `queued → claimed → running → pr_opened →
awaiting_review → done`, with `blocked/failed/cancelled`
(`gateway/builder_queue_db.py`, `LEGAL_TRANSITIONS`).

### 1.2 The prototype threshold (concrete, decidable from the draft manifest)

Insert a prototype packet when **any** of these hold at authoring time:

| # | Condition | How it's decided |
|---|-----------|------------------|
| T1 | Manifest has ≥ 4 implementation packets | count `packets[]` |
| T2 | `allowed_paths` span ≥ 2 subsystems (e.g. `gateway/` AND `gateway/kitty-chat/`) | prefix comparison on the union of allowed_paths |
| T3 | Any packet creates a new UI surface or new top-level module (an allowed_path whose directory has no tracked files) | `git ls-files <path>` empty |
| T4 | Any acceptance criterion cannot name a validation command that would prove it | authoring-time check — if you can't write the command, you don't understand the feature yet |

If none fire, skip the prototype and go straight to implementation. T4 firing
is also the signal that the clarification round isn't finished.

**Prototype packet shape** (convention, no schema change — uses existing
fields from `builder_initiative._PACKET_KEYS`):

- `id`: `<initiative>-proto`
- `objective`: "Working skeleton of X, end to end, fixture data allowed.
  Purpose: expose design flaws before the full build."
- `acceptance_criteria`: observable-demo criteria only ("`<command>` runs the
  happy path end to end", "UI renders with fixture data"). Explicitly NOT
  test coverage, polish, or edge cases.
- `validation_commands`: the demo command itself, plus the existing suite to
  prove nothing broke.
- `policy.max_attempts`: 2 (a prototype that needs 3+ attempts is telling you
  the clarification failed — stop, don't grind).
- Every other packet lists `depends_on: ["<initiative>-proto"]` (directly or
  transitively).

The gate mechanism still costs nothing: dependency satisfaction at `DONE`
is unchanged. What CP-06 changes is who resolves it — the independent
reviewer's `approve` verdict (judged against the campaign brief, not just
the packet contract) triggers the merge, `detect_merged_prs` promotes the
task, and the loop continues in the same invocation. Jacob is no longer in
the loop's critical path; `--gate manual` restores park-and-wait for
campaigns where he explicitly wants to eyeball the prototype.

### 1.3 Where the archived kill-switch design plugs into KB-S5

The valuable part of `BUILDER_CAMPAIGN_CONTROLLER.md` is the asymmetry, not
the machinery. Adapted to what actually exists:

**Halt loud (classify as `needs_decision`, stop the initiative):**

| Archived condition | Current-code equivalent | Touch point |
|---|---|---|
| Reviewer rejects same packet twice on architectural grounds | Two review rejections on one packet whose findings are non-fixable class | `builder_loop.run_packet` review/repair branch; rejection findings already recorded per attempt (`builder_attempt`) |
| Packet needs judgment beyond its scope | Already exists: `builder_scope.EscalationError`, `builder_identity.verify_and_escalate`, `RUN_SCOPE_VIOLATION` run state — but the loop surfaces it the same as any failure | `builder_run.run_initiative` `_decide` payloads: add `stop_class` field |
| Systemic validation regression | Validation fails on commands whose covered paths the diff didn't touch (inference — needs a baseline validation record to compare against; see CP-03 note) | `builder_loop._validation_evidence` |
| Canonical-source conflict | Drop. Assumes the frozen-doc structure (`docs/knowledge/`, `docs/builder/BUILDER_*.md`) that no longer exists. `docs/AUTHORITY_MAP.md` is the only routing map now. | — |
| Two workers colliding on one file | Drop for now. `run_initiative` is serial (one packet at a time), and branch leases (`builder_queue_branch_leases.py`) already fence concurrent branch claims. Revisit only if parallel workers ship. | — |

**Do NOT halt (classify as `routine`, retry/exhaust quietly):** test
failures, build failures, worker crashes (`crashed` is already
budget-neutral in `_attempts_exhausted`), free-endpoint timeouts, merge
conflicts, fixable review rejections. This list is already how the loop
behaves — CP-03 only adds the *classification*, so a paused initiative tells
Jacob "routine exhaustion, re-run or hand to a paid worker" vs "decision
needed: here's the question."

**Escalation thresholds, adapted:** archive said "3 workers fail the same
packet the same way = ambiguous requirement." Serial-loop equivalent:
`max_attempts` exhausted **with the same failure signature across attempts**
(same validation command failing, same review finding class) → classify
`needs_decision: requirement may be ambiguous` instead of plain exhaustion.
Different-signature failures stay routine.

**Health metrics (small, derive-only):** attempts-per-packet, first-pass
review rate, exhaustion count, stop-class counts — all derivable from
existing events/attempts tables at read time in `initiative status --json`
(`builder_initiative.initiative_status`). No new writes. The archive's
"evaluate after each phase; a control that never fires gets simplified"
discipline applies to CP-03 itself: if `needs_decision` never fires in the
first 10 campaigns, delete the classifier.

---

## 2. Roadmap to daily use, as packets

Sized the way `builder_initiative.validate_manifest` expects (objective,
acceptance criteria, allowed paths, `policy.max_attempts`). Estimates are for
one capable agent (Claude Code) per packet, including tests. These are
realistic, not optimistic — each includes reading the touched module first.

### CP-01 — Campaign playbook: clarification round + prototype convention

- **Objective:** One procedure doc, `docs/CAMPAIGN_PLAYBOOK.md`, that any
  paid-model session follows to turn "I want X" into an applied initiative:
  (1) clarification interview — restate the ask, list assumptions with
  dispositions, ask Jacob the questions that change the manifest (max one
  round unless answers contradict); (2) decide prototype via the §1.2
  threshold table; (3) author the manifest against the real schema
  (`_TOP_LEVEL_KEYS` / `_PACKET_KEYS`); (4) `initiative validate` → show
  Jacob the manifest → `initiative apply` on his go; (5) launch command
  cheat-sheet for the four shapes (§3). Includes one complete worked example
  manifest (prototype-gated, 4 packets).
- **Acceptance criteria:** playbook exists; example manifest passes
  `./kitty builder initiative validate <file>`; threshold table matches §1.2;
  explicitly documents the standalone escape hatch (`queue add`/`queue run`)
  so narrow fixes never route through clarification.
- **Allowed paths:** `docs/CAMPAIGN_PLAYBOOK.md`, `docs/packets/TEMPLATE.md`
  (link update only).
- **Estimate:** 0.5–1 day. **Depends on:** nothing. **This is the packet
  that makes everything else usable this week — do it first.**

### CP-02 — Manifest lint: structural warnings (NOT semantic judgment)

- **Objective:** Extend `initiative validate` with warnings (never
  rejections): (a) a packet has an acceptance criterion but zero
  `validation_commands`; (b) two packets with no dependency relation share an
  `allowed_paths` prefix (collision risk); (c) a prototype-shaped initiative
  (§1.2 T1–T3 computable from the manifest) has no `-proto` packet. Warnings
  print to stderr and appear in `--json` output as `warnings[]`.
- **Acceptance criteria:** `validate` exit code unchanged by warnings; the
  three warning classes each have a test; no rejection behavior changes
  (existing `validate_manifest` error list untouched).
- **Allowed paths:** `gateway/builder_initiative.py`, `gateway/builder_cli.py`,
  `tests/test_builder_initiative.py`.
- **Estimate:** 1 day. **Depends on:** CP-01 (threshold definitions).
- **Hard boundary, learned from the archive's own corpse:** the abandoned
  campaign died on P1-03 — a semantic "measurability heuristic" that needed
  architecture judgment nobody could give. Do NOT implement semantic
  acceptance-criteria scoring in code. Measurability judgment belongs in the
  CP-01 clarification round, where a human answers questions. If a warning
  class here starts requiring judgment calls, cut it.

### CP-03 — Stop classification: the KB-S5 judgment layer

- **Objective:** Every non-idle exit of `builder_run.run_initiative` and
  every packet exhaustion carries a durable `stop_class`:
  `routine` (budget/exhaustion/timeouts) or `needs_decision` (scope or
  identity escalation, `max_attempts` exhausted with identical failure
  signature across attempts, ≥2 review rejections with same finding class).
  Written via the existing `_decide` event path (`EVENT_DECISION` payloads);
  surfaced in `initiative status --json` and `pause` reasons.
- **Acceptance criteria:** scope-violation run → `needs_decision` with the
  structured findings attached; plain 3× different-failure exhaustion →
  `routine`; same-signature exhaustion → `needs_decision` with
  "requirement may be ambiguous"; all asserted by tests; no change to state
  machines or lease semantics.
- **Allowed paths:** `gateway/builder_run.py`, `gateway/builder_loop.py`,
  `gateway/builder_initiative.py` (status rollup only),
  `tests/test_builder_run.py`, `tests/test_builder_loop.py`.
- **Estimate:** 1.5–2 days. Failure-signature comparison is the fiddly part —
  start with (validation command name, exit code, review finding class) as
  the signature; do not attempt output diffing.
- **Depends on:** nothing (parallel with CP-01/CP-02).
- **Deferred from this packet:** the "systemic validation regression"
  halt condition — it needs a durable baseline validation record to compare
  against, which is new state. Flag it in `docs/LEARNINGS.md` when this
  ships; build it only if dogfooding shows repair loops chasing unrelated
  regressions.

### CP-04 — Health metrics in `initiative status`

- **Objective:** `initiative status <id> --json` gains a `health` block
  derived at read time from existing attempts/events rows: attempts per
  packet (avg/max), first-pass review approval rate, exhausted count,
  stop-class counts, wall-clock per packet. No new writes, no new tables.
- **Acceptance criteria:** numbers verified by a test that constructs a known
  history; `status` without `--json` prints a one-line health summary;
  read-only guarantee holds (no DB writes on the status path).
- **Allowed paths:** `gateway/builder_initiative.py`,
  `gateway/builder_status.py`, `gateway/builder_cli.py`,
  `tests/test_builder_initiative.py`.
- **Estimate:** 1 day. **Depends on:** CP-03 (stop-class counts; can ship
  without them if CP-03 slips — leave the field absent, not zero).

### CP-05 — Campaign report: bounded artifact delivery, minimal cut

- **Objective:** `./kitty builder initiative report <id>` writes one
  markdown file to `data/kittybuilder/reports/<initiative>-<ts>.md`:
  per-packet outcome, attempts + stop classes, changed paths + diff stat,
  validation command results (pass/fail + tail), review verdicts, PR links,
  pointers (paths, not contents) to transcripts and attempt manifests under
  `data/kittybuilder/`. Bounded: tails capped, no full transcripts inlined,
  no secrets (report reads only Builder's own durable stores, never `.env`
  or runtime personal data).
- **Acceptance criteria:** report generated for a finished and an in-flight
  initiative; caps enforced by test; command is read-only against the queue
  DB.
- **Allowed paths:** `gateway/builder_report.py` (new),
  `gateway/builder_cli.py`, `tests/test_builder_report.py`.
- **Estimate:** 1–2 days. **Depends on:** CP-03/CP-04 (reads their fields;
  degrade gracefully if absent).
- **Scope note:** this is deliberately NOT the "artifact delivery design"
  from the gap list (safe delivery into Kitty's own context). It's the
  80% version: one file Jacob opens. The full design rides with CP-09.

### CP-06 — Evidence-gated auto-merge + auto-revert (owner decision 2026-07-21)

- **Objective:** Remove the human from the merge path for campaign work.
  After a packet run ends `succeeded` (validation pass + reviewer
  `approve`), the loop publishes AND merges the PR (`gh pr merge`), calls
  `detect_merged_prs` to promote the task to `done`, and continues to the
  next eligible packet in the same invocation. Immediately after merge,
  re-run the packet's `validation_commands` against `main`; on red, revert
  the merge commit at once, classify `needs_decision`, and pause the
  initiative. Prototype packets additionally require the reviewer verdict
  to address direction-vs-campaign-brief (extend the review context —
  touch point `builder_loop._write_review_context` — to carry the brief
  pointer). Add `--gate manual` on `initiative run` to restore
  park-and-wait per campaign. **Tripwire (the foolproofing fail-safe):**
  if ≥ 2 of the last 10 auto-merges were reverted, auto-merge disables
  itself (falls back to `awaiting_review` parking) and the report says so
  — the system degrades to shadow mode, never to silent breakage.
  Ship with: ADR 0018 recording Jacob's 2026-07-21 decision + rails, a row
  in `docs/DECISIONS.md`, and the matching edit to CLAUDE.md's "pushing
  requires explicit approval" line (scoped: Builder campaign branches and
  their merges only).
- **Acceptance criteria:** green packet auto-merges and downstream unlocks
  without operator action (test with a stubbed `gh`); post-merge red
  auto-reverts and pauses with `needs_decision`; tripwire disables
  auto-merge at 2/10 reverts; `--gate manual` parks; ADR 0018 +
  DECISIONS.md + CLAUDE.md landed; excluded operations (secrets, deps,
  history rewrites) remain impossible from this path.
- **Allowed paths:** `gateway/builder_run.py`, `gateway/builder_publish.py`,
  `gateway/builder_loop.py`, `gateway/builder_cli.py`,
  `tests/test_builder_run.py`, `tests/test_builder_publish.py`,
  `docs/adr/0018-builder-campaign-auto-merge.md`, `docs/DECISIONS.md`,
  `CLAUDE.md`.
- **Estimate:** 2 days. **Depends on:** CP-03 (stop classes). The merge
  evidence gate is the archive's Section 8 list adapted to what exists:
  validation commands green, reviewer approve, scope clean — nothing more
  (the archive's docs-lint/SYSTEM_MAP rows reference tooling that no
  longer exists; drop them).
- **Auth note:** requires working `gh` credentials — preflight must check
  for the stale `GITHUB_TOKEN` shadowing issue (known, documented in
  `.claude/STATE.md`) and `unset GITHUB_TOKEN` in the merge path's
  environment before any `gh` call. Bake that into the code path, not into
  an instruction Jacob has to remember.

### CP-07 — Skills and scripts in worker context (token-efficiency layer)

- **Objective:** Workers stop rediscovering the repo. (a) The worker brief
  (`gateway/builder_brief.py`) and context bundle
  (`gateway/builder_context.py`) gain a `resources` section: repo scripts
  relevant to the packet's `allowed_paths` (from `scripts/`), applicable
  repo skills (`.claude/skills/`: `catchup`, `debug-fix`,
  `second-opinion`), and the standing instruction "prefer invoking an
  existing script over reimplementing; cite which you used in the final
  report." Mapping is mechanical — path-prefix rules in one table, not
  inference. (b) The CP-01 playbook gains the paid-session counterpart:
  invoke `/goals`, `/design`, `/feature-developer`, `/loop` when available
  (Jacob's global commands), with the explicit fallback that their absence
  never blocks. (c) Reviewer briefs point at `second-opinion` for
  borderline verdicts before burning a repair attempt.
- **Acceptance criteria:** brief for a packet touching `gateway/` lists the
  mapped scripts/skills; a packet touching an unmapped path gets an empty
  `resources` section (never a guess); worker final reports show a
  `resources_used` field; tests cover the mapping table.
- **Allowed paths:** `gateway/builder_brief.py`,
  `gateway/builder_context.py`, `docs/CAMPAIGN_PLAYBOOK.md`,
  `tests/test_builder_brief.py`.
- **Estimate:** 1–1.5 days. **Depends on:** CP-01 (playbook exists).

### CP-08 — Dogfood: two real campaigns unattended, retro, KB-S5 sign-off

- **Objective:** Operate the system on real work with Jacob doing nothing
  but reading reports. Campaign A (short/free): one real small fix via
  `run-packet --free --watch`, through auto-merge. Campaign B (long/free,
  prototype-gated): a real 3–4 packet feature through the full §1.1
  lifecycle — prototype auto-merged on reviewer approve, downstream
  continuing in the same run. Then: mark KB-S5 ✅ in
  `docs/KITTYBUILDER_SELF_BUILDING_MVP.md` with evidence, write a 10-line
  retro into `docs/LEARNINGS.md` (which controls fired, which never did),
  file follow-ups.
- **Acceptance criteria:** both campaigns reach `done` or a classified stop
  with **zero Jacob actions between launch and report**; `initiative
  report` attached for both; auto-merge/auto-revert behavior observed and
  cited; KB-S5 marked shipped with run IDs; retro names at least one thing
  to delete.
- **Allowed paths:** docs only (`docs/KITTYBUILDER_SELF_BUILDING_MVP.md`,
  `docs/LEARNINGS.md`, `docs/PROJECT_STATUS.md`).
- **Estimate:** 1 day of unattended runtime + report reading.
  **Depends on:** CP-01–CP-07.

### Deferred — named, not authorized

- **CP-09 — Mission ingress runtime (ADR 0017).** Versioned Mission schema,
  acceptance tests, approval bridge, submission through a supported Builder
  interface, result projections back into Kitty
  (`docs/adr/0017-kitty-mission-builder-control-plane.md`;
  `gateway/agent_runner.py` currently has zero Builder references —
  verified). This is the real "Kitty, build X" product loop and the bulk of
  the old 4–6 week anchor. **Estimate: 2–3 weeks.** Requires its own
  approved mission per `docs/PROJECT_STATUS.md` ("separately approved
  packet"). CP-01's playbook is the manual stand-in until then — same
  clarify → manifest → apply flow, human-driven.
  (Merge automation is no longer deferred — it moved into CP-06 by owner
  decision, with the tripwire replacing the old "re-litigate later" plan.)

### Total

| Packet | Estimate | Parallel lane |
|---|---|---|
| CP-01 | 0.5–1 d | A |
| CP-02 | 1 d | A (after CP-01) |
| CP-03 | 1.5–2 d | B |
| CP-04 | 1 d | B (after CP-03) |
| CP-05 | 1–2 d | B (after CP-04) |
| CP-06 | 2 d | C (after CP-03) |
| CP-07 | 1–1.5 d | A (after CP-01) |
| CP-08 | 1 d unattended runtime | after all |
| **Authorized total** | **9–12 agent-days serial; ~1 calendar week with lanes A/B/C in parallel subagents** | |
| CP-09 (deferred) | 2–3 weeks | separate approval |

Ordering: lanes A (playbook/lint/skills), B (classification/metrics/report),
and C (auto-merge) are independent until CP-08 joins them. If time pressure
hits, the load-bearing minimum is CP-01 + CP-03 + CP-06 + CP-08 —
CP-02/CP-04/CP-05/CP-07 improve quality-per-token but don't gate daily use.

---

## 3. Test plan: the four campaign shapes

### 3.1 Corrected mapping (the prompt's mapping was right, with one fix)

- **short** = one packet. Two flavors: single-packet initiative
  (`initiative run-packet`) when you want the full attempt/review/report
  trail, or bare `queue add` + `queue run <id> -- <cmd>` for a standalone
  narrow fix (want #5 — no clarify, no gate, no initiative).
- **long** = multi-packet initiative via `initiative run`, prototype-gated
  when §1.2 fires.
- **free** = `--free` (wires `scripts/kittybuilder_opencode_worker.sh` +
  `_reviewer.sh`, the OpenCode ladder — `docs/FREE_WORKERS.md`). Available
  on `initiative run-packet` and `initiative run` only (verified in
  `builder_cli.py`).
- **paid** = explicit `--worker-command` / `--review-command` pointing at a
  paid-model adapter. **Fix to the prompt's framing:** `queue run` has no
  `--free` flag — the standalone path takes an explicit worker command
  either way. So "free vs paid" is an initiative-level choice; standalone
  tasks pass whatever command you give them.

The axes are orthogonal; all four combos below are real invocations.

### 3.2 What Jacob actually runs

Precondition for every shape: `bash scripts/preflight.sh`, then
`./kitty builder initiative doctor` (2026-07-17 audit baseline per
`docs/PROJECT_STATUS.md`: 13 pass / 1 warning; the warning is the uncreated
worktree root, which the first run creates).

**Shape 1 — short / free** (the daily workhorse; part of CP-08 Campaign A):

```bash
./kitty builder initiative validate <manifest.json>   # 1 packet, no proto
./kitty builder initiative apply <manifest.json>
./kitty builder initiative run-packet <init> <packet> --free --watch
./kitty builder initiative status <init> --json        # health block (CP-04)
./kitty builder initiative report <init>               # CP-05
```

Look at: outcome `succeeded`; PR opened, NOT merged (shadow mode holds);
report shows validation pass + review verdict; free-ladder handoffs (if any)
visible in the attempt manifest under `data/kittybuilder/`.

**Shape 2 — short / paid** (same manifest shape, paid worker):

```bash
./kitty builder initiative run-packet <init> <packet> \
  --worker-command "<paid worker cmd>" --review-command "<paid reviewer cmd>" --watch
```

Look at: identical trail shape to Shape 1 — the point of this test is that
NOTHING differs except the worker; if the paid path produces a different
evidence shape, that's a bug. Compare attempts-to-success against Shape 1 on
a comparable packet.

**Shape 3 — long / free, prototype-gated** (CP-08 Campaign B; the shape that
proves the design):

```bash
./kitty builder initiative apply <manifest.json>       # 3-4 packets + proto
./kitty builder initiative run <init> --free --max-attempts 12
# EXPECT (with CP-06): proto runs → reviewer approves direction → auto-merge
# → detect_merged_prs promotes → downstream packets run in the SAME
# invocation → each auto-merges on green → loop exits idle with all done.
./kitty builder initiative report <init>               # the only human step
```

(Pre-CP-06, or with `--gate manual`: the run exits idle after the proto PR
opens; promotion needs `queue reconcile-merges` after a manual merge —
`queue sync-pr` only refreshes PR metadata, it never mutates task state.)

Look at, in the report: (a) the gate held — zero downstream attempts
timestamped before the proto merge (attempts table via `initiative
attempts`); (b) the proto review verdict actually addressed direction vs
the campaign brief, not just "tests pass"; (c) mid-run `initiative pause`
then `resume` works; (d) killing one attempt (`queue cancel-run`)
classifies routine, not `needs_decision`; (e) every merge has its
post-merge validation record.

**Shape 4 — long / paid:** Shape 3's command shape with paid
worker/review commands. Run this LAST and only if a free run exhausted —
that's the cost policy from `docs/FREE_WORKERS.md` (paid re-enters only on
honest `exhausted` evidence). Look at: the exhausted packet's stop class and
failure signature from the free run were enough to brief the paid worker
without re-diagnosis.

### 3.3 Negative tests (the gate is only real if it refuses)

1. Author a manifest where a downstream packet omits `depends_on` the proto
   → CP-02 warning fires; if ignored, downstream runs before the gate —
   which is why CP-02's warning (c) exists. This is the one place the
   convention can silently fail; the warning is the fence.
2. Feed the worker a packet whose scope excludes a file it must touch →
   scope enforcement stops it (`builder_scope.find_changed_path_violations`),
   CP-03 classifies `needs_decision`, structured findings name the path.
3. Set `policy.max_attempts: 1` on a deliberately-vague packet → exhaustion
   with same-signature classification → `needs_decision:
   requirement may be ambiguous`, not a silent retry loop.
4. **Auto-revert drill (CP-06):** merge a packet whose validation was
   green in the worktree, then make main's re-validation fail (inject a
   conflicting commit between review and merge) → the merge reverts
   immediately, the initiative pauses `needs_decision`, and the report
   names the revert commit. Run this once deliberately before trusting
   unattended runs.
5. **Tripwire drill:** force 2 reverts within 10 merges (stubbed `gh`) →
   auto-merge disables itself and subsequent packets park at
   `awaiting_review` with the reason in the report.

---

## 4. Audit / challenge

### 4.1 Shadow mode: overturned by owner decision (2026-07-21) — the rails that replace it

The first draft of this plan argued to keep human merge. Jacob overruled
it, with the correct observation that a gate whose gatekeeper is
"unreliable at best" isn't a gate — it's a stall. His call to make (this
plan's earlier objection #3 — pushing requires his explicit approval — is
answered: this instruction IS that approval, scoped to campaign work and
recorded durably as ADR 0018 in CP-06).

What replaces the human is not trust — it's the archive's own merge
evidence gate (Section 8, adapted) plus two mechanisms the archive already
prescribed but nobody built:

1. **Evidence gate before merge:** declared validation commands green +
   independent reviewer `approve` + scope clean. Miss any → no merge.
2. **Auto-revert after merge:** the archive's rule verbatim — "if CI fails
   after merge: immediately revert; do not hotfix on main." Post-merge
   re-validation on `main`, revert on red, `needs_decision` stop.
3. **The tripwire:** ≥ 2 reverts in the last 10 merges → auto-merge
   disables itself and the system degrades to park-at-review. This is the
   draft's old "re-litigate after 10 packets with data" exit ramp, made
   automatic — it re-litigates itself, in the safe direction, without
   anyone remembering to.

What did NOT get loosened: the excluded list (§0.5) — secrets, data
deletion, external messages, spending, history rewrites, heavy deps. The
prototype gate's protection also survives, relocated: the reviewer must
judge direction against the campaign brief, and a direction rejection
after one repair round is a `needs_decision` stop, not a grind.

One honest residual risk to state plainly: an evidence gate only proves
what the validation commands test. A green-but-wrong feature now lands on
main instead of parking in a PR. Mitigations: it's local-first single-user
(blast radius = Jacob's repo, fully revertible), the CP-05 report makes
every merge visible same-day, and the prototype round exists precisely to
catch wrong-direction early. Accepted trade, per owner.

### 4.2 Clarification inside Builder, or in Kitty's agent loop?

**Neither, for now — it lives in the paid-model session, as a procedure
(CP-01).** ADR 0017 already settled the architecture: Kitty is the intent
compiler, Builder validates and executes; planning is Kitty-side. But
Kitty's agent loop has zero Builder integration today
(`gateway/agent_runner.py` — verified, no references), and building mission
ingress just to host a clarification round is the tail wagging the dog.
The playbook gives the identical flow (clarify → manifest → approve →
apply) with a human carrying the artifacts. When CP-09 ships, the playbook
becomes the Mission-preparation spec — the work isn't thrown away, it's the
requirements doc. Putting clarification inside Builder would violate
ADR 0017's boundary ("Builder does not own Jacob's conversational intent")
and is rejected outright.

### 4.3 Is the manifest format expressive enough for the prototype gate?

**Yes, with zero schema changes — by design, after checking the
alternative.** `_PACKET_KEYS` has no `kind`/`gate` field and
`validate_manifest` rejects unknown keys. Two options were considered:

- (a) add `kind: "prototype"` to the schema;
- (b) express the gate as a dependency convention (§1.2).

(b) wins: the gate semantics (block downstream until human approves) are
*already* the dependency-satisfaction semantics (`eligible_packets`
requires `DONE`), so (a) would add a schema version bump, migration
handling, and a second gating mechanism for zero new behavior.
Prototype-grade acceptance criteria fit the existing
`acceptance_criteria`/`validation_commands` fields (§1.2). Revisit only if
CP-09's Mission schema needs machine-readable prototype identification —
and even then, `id: *-proto` is parseable.

One real gap found instead: nothing prevents authoring the gate wrong
(missing `depends_on`). That's CP-02 warning (c) — a lint, not a schema
change.

### 4.4 Where does this risk recreating the archived campaign's failure mode?

The archive stalled on P1-03: a packet needing an architectural judgment
("measurability heuristic boundary") with no path to resolution except
asking Jacob — and no mechanism that actually asked him. Recreation risks
in this plan, in descending order:

1. **CP-02, if it drifts semantic.** Explicitly fenced: warnings-only,
   structural checks only, kill any warning class that needs judgment.
2. **CP-03's failure-signature comparison.** "Same failure" is a judgment
   spectrum. Fenced by fixing the signature to three mechanical fields
   (command, exit code, finding class) — crude but decidable. If it
   misclassifies, it errs toward `needs_decision`, which asks Jacob — the
   correct failure direction.
3. **The prototype gate itself pauses campaigns by design** — that's the
   feature. The difference from P1-03: the pause has an owner (the
   independent reviewer, with Jacob as 24h-default backstop), a concrete
   artifact to judge (a PR against a campaign brief), and an automated
   resolution (approve → merge → continue). P1-03 stalled with none of
   those.

The structural fix the archive lacked and this plan has: every stop now
terminates at an owner with an artifact and a default action, never at an
unowned open question. Post-foolproofing, even the Jacob-owned stops
(`needs_decision`) carry a recommended default that takes effect at 24 h —
nothing can wait on him indefinitely.

### 4.5 Process weight without proven payoff — flagged honestly

- **Dropped from the archive:** GOVERNANCE.md doc-governance (assumes a doc
  tree that no longer exists; `docs/AUTHORITY_MAP.md` owns routing now);
  worker-rotation rules (serial loop, no worker pool); the 31-packet
  phase/retrospective cadence (per-phase retros for a 4-packet campaign is
  ceremony — CP-08 does ONE 10-line retro).
- **Kept but on probation:** CP-03's classifier and CP-04's metrics carry
  their own sunset clause — any control that never fires across the first
  ~10 campaigns gets deleted, per the archive's own Section 16 discipline.
- **The campaign_state.json pattern is NOT reproduced.** The queue DB is
  already the durable state machine with recovery
  (`builder_queue_runs.recover_interrupted_runs`); a second state file
  would be a second source of truth — the exact disease the archive's own
  One Rule warns about.

---

## 5. How much longer for Kitty (planning-grade, with honest error bars)

What Jacob actually asked: when can he plan around Kitty working. Three
milestones, each independently useful:

**Milestone 1 — Builder is the daily driver (this plan, CP-01–CP-08).**
~9–12 agent-days serial, ~**1–1.5 calendar weeks** with parallel subagent
lanes. After this: Jacob describes a feature to a paid session, the
playbook turns it into a campaign, free workers build it, it merges itself
or stops with a classified question. Confidence: high — every mechanism
was verified against code this session; the only new machinery is CP-06.

**Milestone 2 — Kitty-builds-Kitty loop closes (CP-09, mission ingress).**
+**2–3 weeks** after Milestone 1 (ADR 0017 runtime: Mission schema,
acceptance tests, submission bridge, result projections). After this: the
paid-session middleman disappears — Jacob tells Kitty in chat, Builder
executes. Confidence: medium — the contract is written (ADR 0017) but
none of the runtime exists, and schema/acceptance-test work historically
runs long. Can overlap with Milestone 3 campaigns.

**Milestone 3 — Kitty feels like one product (the KX program).**
The active mission (`docs/ACTIVE_MISSION.md`, KFX-001) is still deriving
the KX initiative manifests, so this is honestly unsized — the program's
packet count doesn't exist yet. Planning band, stated as inference: once
Milestone 1 lands, KX initiatives run as campaigns on free workers at
roughly one initiative per 2–4 days of unattended runtime; a
nine-lane product surface plausibly means **6–10 weeks of campaign
cadence** after the manifests land. Revise this number the day KFX-001
delivers its manifests — that's the real unlock date.

**Bottom line for planning:** working daily-driver Builder ≈ 1.5 weeks
out. Chat-to-merged-code ≈ 4–6 weeks out. Product-coherent Kitty ≈ 2–3
months out at free-worker cadence — dominated by Milestone 3's unknown
size, not by Builder. The compounding effect is real but only after
Milestone 1: every week of Milestones 2–3 is executed BY the thing
Milestone 1 builds, which is why this plan front-loads it.

---

## Appendix: worked example — prototype-gated manifest skeleton

Passes the current schema (`_TOP_LEVEL_KEYS`/`_PACKET_KEYS`,
`manifest_version: 1`). CP-01 ships a fully fleshed version.

```json
{
  "manifest_version": 1,
  "initiative_id": "cp-example",
  "title": "Example feature, prototype-gated",
  "description": "Clarified 2026-07-XX; assumptions and Jacob's answers in the campaign brief.",
  "packets": [
    {
      "id": "cp-example-proto",
      "title": "Working skeleton, fixture data",
      "objective": "Prove the shape end to end so design flaws surface before the full build.",
      "acceptance_criteria": [
        "demo command runs the happy path end to end against fixture data",
        "existing test suite still passes"
      ],
      "allowed_paths": ["gateway/example_feature.py", "tests/test_example_feature.py"],
      "validation_commands": ["python3.12 -m pytest tests/ -q --tb=short"],
      "policy": {"max_attempts": 2}
    },
    {
      "id": "cp-example-impl",
      "title": "Full implementation",
      "objective": "Production-quality build of the approved prototype direction.",
      "depends_on": ["cp-example-proto"],
      "acceptance_criteria": ["...concrete, command-provable criteria..."],
      "allowed_paths": ["gateway/example_feature.py", "tests/test_example_feature.py"],
      "validation_commands": ["python3.12 -m pytest tests/ -q --tb=short"],
      "policy": {"max_attempts": 3}
    }
  ]
}
```

The gate: after `cp-example-proto` reaches `pr_opened`,
`initiative run` exits idle; `cp-example-impl` stays `waiting` until the
prototype PR is merged and `queue reconcile-merges` promotes the task to
`done`. (This appendix manifest was run through
`builder_initiative.validate_manifest` on 2026-07-21: zero errors.)
