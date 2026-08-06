# Loose Ends Register — 2026-08-05 (post-architecture-research closeout)

**Companion to:** `docs/CLOSEOUT_LEDGER_2026-08-05.md`
**Purpose:** every remaining open item, classified P0–P3, with evidence, owner,
blocking relationship, exact next action, and whether Jacob's approval is
required. Nothing here is invented; each item is tied to a live fact.

---

## P0 — Must resolve before Builder runs

| # | Item | Evidence | Owner | Blocks | Exact next action | Jacob approval? |
|---|---|---|---|---|---|---|
| P0-1 | **needs_decision must fail closed.** `run_initiative` records `stop_class=needs_decision` then `continue`s and exits 0 (`builder_run.py:574-591`, `builder_cli.py:1521`) → an escalation never parks work; the two-week campaign re-selects the same packet | forensic report §2D; events 1781/1782 (`continued_after_packet_failure` with `stop_class=needs_decision`); live DB shows initiative paused only because it was operator-paused | interactive (closeout) → implementation; code change | everything Builder (V2 apply, B9/B10) | Add a real stop: on `stop_class==needs_decision`, pause initiative durably + exit non-zero; add a test that asserts `needs_decision` prevents re-selection | No (authorized improvement, T0/T1) |
| P0-2 | **Leaked open attempt:** `packet_attempts` id 68 `KTF-DP-03-unified-evidence-capture-proto` (task `kb_ms7q2qcp_06ca`) outcome NULL since 2026-07-30 — re-arms recovery per forensics §2B | live DB query this closeout | interactive (operator) | builder-loop recovery correctness | Close/reconcile the attempt via supported `builder queue` ops; verify events trail; add liveness assertion to close stale attempts | No |
| P0-3 | **B8 task permanently selectable:** `trustworthy-kittybuilder-b2-b10-v1` — B3–B7 done, **B8 blocked** (`shadow_run_complete`) with B9/B10 queued behind it; budget never exhausts (crashes budget-neutral, `_attempts_exhausted` counts only failed/aborted) | live DB; forensics §2C | interactive (operator) + helper | B9/B10, all subsequent runs of that initiative | Operator decision on B8: mark exhausted / replace with the real approved onboarding/Work repair (P0-4); do not keep re-selecting B8 | **Yes** (task disposition) |
| P0-4 | **Operator-approved work never reified:** "Repair first-run onboarding and Work navigation" has no task/packet in `builder_queue.db`; it existed only as interactive intent | forensics §2E; DB has no matching initiative | Jacob → interactive | the actual product work the operator wanted | Author a bounded packet/manifest for onboarding+Work repair, approve, and let it replace B8 as the selectable work | **Yes** (scope + approval) |
| P0-5 | **Cannot safely run Builder while `.claude` continuity describes a completing session with a live next_action** — repaired in this closeout, but only on `main` working tree; a `git reset --hard`/clean would re-breach it | receipt pre-repair failures `handoff:active_action`, `state:active_action` | interactive (closeout) | any Builder launch gated on receipt pride | Ensure repaired STATE/HANDOFF are committed (PR) before any unattended run | No |
| P0-6 | **Uncommitted architecture authority:** 9 ADRs (0028–0036), Constitution v1, Capability Manifest, ROADMAP_V2, product plan, OS architecture, decision summary — none on origin/main; a clean checkout or merge-to-origin without the closeout branch loses them from visibility | this ledger §1 (all UNCOMMITTED or local-only) | interactive (closeout) | anyone doing clean-checkout work | Merge/push the `closeout/2026-08-05-architecture-reconciliation` branch as a reviewable PR | **Yes** (push/merge = T2) |
| P0-7 | **V2 initiative must NOT be applied yet** — its manifest contains live/operator-class packets that must not run autonomously, and P0-1/P0-3 are unsolved | `docs/initiatives/v2-driver-baseline-v1.json` packet classes; forensics | Jacob | V2 start | Do not apply until P0-1 done + Jacob approves ROADMAP_V2 (C-5/C-10) | **Yes** |

## P1 — Must resolve before V2 implementation

| # | Item | Evidence | Owner | Blocks | Exact next action | Jacob approval? |
|---|---|---|---|---|---|---|
| P1-1 | **Ratify the Open WebUI boundary:** replaceable shell (ADR 0027/0033) vs permanent UI (OS architecture C-1) | ADR 0027/0033; `docs/OPENWEBUI_OS_ARCHITECTURE.md` "supersedes guidance in ADR 0027" | Jacob | M1/M2 shell re-role | Accept a permanent-UI ADR or keep replaceable; then update Constitution/ROADMAP_V2/Master consistently | **Yes** |
| P1-2 | **Reconcile roadmap authority:** ROADMAP.md vs ROADMAP_V2 vs KITTY_MASTER_PROGRAM (C-5) | all three documents (ledger §1) | Jacob | V2 sequencing | Choose one active sequence; archive/supersede the other two | **Yes** |
| P1-3 | **Capability Manifest spec sign-off** before Home/Open WebUI work (C-10) | `docs/CAPABILITY_MANIFEST.md`; ADR 0029 | Jacob | M1 Home, M2 console, shell truth | Review + accept the spec (or note gaps) as the runtime-truth contract | **Yes** |
| P1-4 | **Gate 0.7 branch protection** (6 required CI checks on main) — defined, unenforced | decision summary §"Open Decisions"; needs GitHub admin | Jacob (repo admin) | trustworthy main | Enable branch protection on main | **Yes** (admin/mutation can't be done by agents) |
| P1-5 | **Competing launcher/listener issue** (PR #406 proof lane vs kitty-chat) | `proof/two-week-builder-loop` PR + boundary docs | Jacob + interactive | clean-lean main | Decide the reconcile scope for the proof lane before V2 M1 | **Yes** |
| P1-6 | **Suspicious wired-modules audit** (`prefetcher`, `inbox_watcher`, `insight_loop`, `life_awareness`, `telegram_bot`, `antigravity_tools`, `web_tracker`, `self_review`) | decision summary "Open Decisions"; `test -f gateway/prefetcher.py` | interactive (deferred) | simplification truth | Audit value vs delete; report | No |
| P1-7 | **DECISIONS.md authoring discipline:** the summary claimed "Updated" but the file was not → add an ADR-index "requires index row" check / convention | this closeout contradiction C-3/C-11 | interactive (docs) | doc trust | Add a CI-ish or review rule: ADR writes must update `docs/DECISIONS.md` | No |

## P2 — Implementation backlog (activates on P0 clearance + Jacob decisions)

| # | Item | Evidence | Owner | Next action |
|---|---|---|---|---|
| P2-1 | Open WebUI Home page (Event Function) + extensions | OS arch; product plan; backlog | interactive | Implement after P1-3 |
| P2-2 | Continuity preset / resume-loop events | Constitution v1 §V/§I | interactive | Wire after shell boundary ratified |
| P2-3 | Builder ↔ chat "propose/recommend" bridge (M3-01) | ROADMAP_V2 M3 | interactive | after P0 set |
| P2-4 | Storage spine consolidation (M5) — keep `~/kb` out | ADR 0030/0034; ROADMAP_V2 M5 | interactive | after M1–M4 evidence |
| P2-5 | Console repositioning (Next.js → operator surface) | ROADMAP_V2 M2 | interactive | after P1-1 |
| P2-6 | Builder organization role semantics (org chart / escalation) | BUILDER_ORGANIZATION.md | interactive | depends C-4 decision |

## P3 — Archival and cleanup

| # | Item | Evidence | Next action |
|---|---|---|---|
| P3-1 | Zombie/orphan docs: `docs/phases/*` (legacy Phase B/C), `docs/planning/*`, stale `docs/DECISIONS` claims | docs/README maintenance note; DOCUMENTATION_AUDIT | archive via documented index; don't rewrite |
| P3-2 | Superseded manifests: `docs/initiatives/` retired dir + old KTF manifests | initiative ledger / DB state | disposition to ledger |
| P3-3 | Orphan documents (e.g. `docs/audit/PROGRESS_REVIEW_2026-07-31.md` recency) | survey | disposition |
| P3-4 | Dead modules / stale worktrees — 9+ `.claude/worktrees/*` from earlier sessions | `git worktree list` | clean after PRs merged |
| P3-5 | Abandoned branches (origin ·refs not merged, 87 refs) | `git branch -r --no-merge` | triage: merge/delete listener |
| P3-6 | `docs/reference/DOCUMENTATION_AUDIT.md` refresh vs new docs | audit dated 07-30 | refresh |
| P3-7 | `docs/skill-improvement-queue.md`, `docs/memory-stale.md` already updated this closeout (kept in sync) | working tree | keep |

---

## Recommendation

One next move only: **repair and test the Builder `needs_decision` fail-closed
behavior (P0-1) before applying the V2 initiative or running any further Builder
packet.** The B8 forensics are the highest-severity uncorrected control defect;
everything downstream — B9/B10, V2, unattended trust — depends on it.
