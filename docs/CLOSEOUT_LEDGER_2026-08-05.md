# Closeout Ledger — 2026-08-05 architecture research phase

**Date:** 2026-08-05 (verified live 2026-08-05 19:xx CST)
**Scope:** Every artifact produced by the recent parallel research/architecture
workers — recovered, verified, and dispositioned. This ledger is the map of
what exists, where it lives, and what must happen next. It does not invent
completeness; anything described in a worker report that cannot be found is
explicitly listed in §9.

**Verification method:** every file below was confirmed on disk (path + content)
or in Git (commit SHA) during this closeout, not taken from a worker summary.

---

## 0. Live-state baseline (re-verified this closeout)

| Fact | Value | Evidence |
|---|---|---|
| Canonical checkout | `/Users/jacobbrizinski/Projects/kitty` | `git worktree list` |
| Canonical branch / HEAD | `main` @ `d3c82748` | `git rev-parse HEAD` |
| Local main vs origin/main | ahead 3 / behind 72 | `git rev-list --count` |
| origin/main | `6a6d6256` (Merge PR #396) | `git rev-parse origin/main` |
| Local-only commits on main | `4c0bf06b` (archival), `5dd1e881` (ADRs 0028-36), `d3c82748` (checkpoint) | `git log`, not ancestors of origin/main |
| Closeout branch | `closeout/2026-08-05-architecture-reconciliation` (base: origin/main) | created this closeout |
| Builder DB | `data/kittybuilder/builder_queue.db` — B2–B7 done, **B8 blocked** (`shadow_run_complete`), B9/B10 queued | live DB + `initiative doctor` |
| Active Builder initiative | `trustworthy-kittybuilder-b2-b10-v1` — active, ✅ paused, stop_class `needs_decision` | `initiative list --json` |
| Open PRs | #406 `proof/two-week-builder-loop` (DRAFT), #391 `docs/paa-alignment-profile` (DRAFT) | `gh pr list` |
| Parallel interactive lane | active this session (opencode PIDs; cap-manifest-set docs written ~18:47–18:52) | live survey |

---

## 1. Recovered recent architecture deliverables (all verified)

### Open WebUI family

| # | Artifact | Path | Branch/ref | Commit/status | Status |
|---|---|---|---|---|---|
| 1 | Open WebUI ecosystem survey | `docs/reference/OPENWEBUI_ECOSYSTEM_SURVEY.md` | pomfret worktree (`jacob202/openwebui-product-discovery`) | **UNCOMMITTED** (untracked there) | accepted research |
| 2 | Open WebUI OS architecture | `docs/OPENWEBUI_OS_ARCHITECTURE.md` | pomfret worktree | **UNCOMMITTED** (untracked) | proposed (explicitly "not yet an ADR") |
| 3 | Open WebUI product plan | `docs/OPENWEBUI_PRODUCT_PLAN.md` | `main` working tree | **UNCOMMITTED** (untracked) | needs review |
| 4 | Open WebUI extension backlog | `docs/OPENWEBUI_EXTENSION_BACKLOG.md` | `main` working tree | **UNCOMMITTED** (untracked) | needs review |

**Carried onto closeout branch:** yes — all four (files copied from pomfret +
canonical working tree, byte-verified identical to source).

### Builder family

| # | Artifact | Path | Branch/ref | Commit/status | Status |
|---|---|---|---|---|---|
| 5 | Builder organization architecture | `docs/BUILDER_ORGANIZATION.md` | `main` working tree | **UNCOMMITTED** | design (not implemented) |
| 6 | Builder trust-hole forensic report | `artifacts/forensic-b8-wrong-assignment-2026-08-05.md` | `main` working tree | **UNCOMMITTED** | needs review (evidence) |
| 7 | Builder Trust Model design brief | `artifacts/handoff-builder-trust-model-v1.md` | `main` working tree | **UNCOMMITTED** | **task brief only — deliverable NOT yet produced** |
| 8 | Builder V2 engine redesign | `docs/BUILDER_V2.md` (parallel lane) | `main` working tree | **UNCOMMITTED** | replacement blueprint (not implemented) |

**Carried onto closeout branch:** yes — all four. Note #7 is the *brief* for the
next worker; the actual `builder-trust-model-v1` document does not exist yet.

### V2 / roadmap / planning family

| # | Artifact | Path | Branch/ref | Commit/status | Status |
|---|---|---|---|---|---|
| 9 | Roadmap V2 | `docs/ROADMAP_V2.md` | `main` working tree | **UNCOMMITTED** | proposed |
| 10 | V2 Builder initiative manifest | `docs/initiatives/v2-driver-baseline-v1.json` | `main` working tree | **UNCOMMITTED, NOT APPLIED** | proposed |
| 11 | Kitty Master Program | `docs/KITTY_MASTER_PROGRAM.md` (parallel lane) | `main` working tree | **UNCOMMITTED** | proposed (claims supersede ROADMAP) |
| 12 | Capability Manifest v2 spec | `docs/CAPABILITY_MANIFEST.md` (parallel lane) | `main` working tree | **UNCOMMITTED** | core spec (implements ADR 0029) |

**Carried onto closeout branch:** yes — all four. V2 initiative is recorded but
is **not** approved to apply until ADR 0024/needs_decision fail-closed is
repaired (see LOOSE_ENDS P0-1).

### ADRs / decisions

| # | Artifact | Path | Branch/ref | Commit/status | Status |
|---|---|---|---|---|---|
| 13 | ADRs 0028–0036 (9 files) | `docs/adr/0028-*.md` … `0036-*.md` | local `main` commit `5dd1e881` | committed locally, **NOT on origin/main** | accepted |
| 14 | ADR index (README.md updated for 0027–0036) | `docs/adr/README.md` | commit `5dd1e881` | committed locally, not on origin | accepted |
| 15 | Architecture decision summary | `docs/research/architecture-decision-summary-2026-08-05.md` | `main` working tree | **UNCOMMITTED** | needs review |

**Carried onto closeout branch:** yes. The ADR family was ratified in commit
`5dd1e881` (local main only) and re-created as files on the closeout branch so a
PR against current origin/main is reviewable. **DECISIONS.md was NOT updated by
the worker** — the summary's "Updated (2026-08-05)" claim was false; I added
rows D27–D35 on the closeout branch (see §3, contradiction C-3).

### Other research/continuity

| # | Artifact | Path | Branch/ref | Commit/status | Status |
|---|---|---|---|---|---|
| 16 | Knowledge graph | `docs/KNOWLEDGE_GRAPH.md` | `main` working tree | **UNCOMMITTED** | analysis |
| 17 | Continuity recovery | `docs/CONTINUITY_RECOVERY.md` | `main` working tree | **UNCOMMITTED** | needs review |
| 18 | Architecture migration analysis (Open Brain/Ringer/Open Engine) | `docs/research/architecture-migration-analysis-2026-08-05.md` | local branch `research/architecture-migration-analysis-cec062f` @ `4d3739ae` | committed there, **NOT pushed, NOT on any main** | draft analysis |
| 19 | Constitution v1 (rewrite) | `docs/CONSTITUTION.md` | `main` working tree | **UNCOMMITTED** (444-line diff) | proposed |
| 20 | Dead-code archival (43 files) | deletion commit | local `main` commit `4c0bf06b` | committed locally, **NOT on origin/main** | done (code, not docs) |
| 21 | State/handoff corrections | `.claude/STATE.md`, `.claude/HANDOFF.md` | `main` working tree | **UNCOMMITTED**, now stale-vs-live | repair (this closeout) |

**Carried onto closeout branch:** 16, 17, 18, 19. **Not carried:** 20 (code
change, preserved in Git history on local main — record only), 21 (continuity
files describe the canonical checkout; repaired in place, not in the doc branch).

### Two-week proof evidence (separate lane)

| # | Artifact | Path | Branch/ref | Commit/status | Status |
|---|---|---|---|---|---|
| 22 | Live Mac audit evidence | `artifacts/proof/live-audit/20260804-202052/`, `...-202624/` (5 MB) | `main` working tree untracked | **UNCOMMITTED** | evidence (belongs to proof lane) |
| 23 | Two-week audit text (docs) | `docs/proof/LIVE_MAC_AUDIT_2026-08-04.md`, `TWO_WEEK_PROOF_AUDIT.md` | branch `proof/live-current-20260804-212614` @ `98db9600` | committed there | evidence |

**Not carried onto doc closeout branch:** 22 (5 MB of raw screenshots/rc dumps;
the text audits are committed at 23). Recorded here so nothing is lost.

---

## 2. Disposition summary by status

| Status | Items |
|---|---|
| accepted (ADR) | ADRs 0028–0036 + index (13, 14) |
| accepted research | ecosystem survey (1) |
| needs review | OS architecture (2), product plan (3), extension backlog (4) |
| proposed / not implemented | Builder org (5), Builder V2 (8), ROADMAP_V2 (9), V2 init (10), Master Program (11), Capability Manifest (12), Constitution v1 (19), migration analysis (18) |
| needs review (evidence) | forensic (6), decision summary (15), knowledge graph (16), continuity recovery (17) |
| task brief, deliverable missing | Builder Trust Model (7) |
| done | dead-code archival (20) |
| existing/repair | state/handoff (21) |

---

## 3. Contradictions reconciled or still requiring Jacob

Recorded in full in `docs/LOOSE_ENDS_2026-08-05.md`. Summary here:

| C | Contradiction | Resolution taken | Jacob decision |
|---|---|---|---|
| C-1 | Open WebUI: replaceable shell (ADR 0027/0033, ROADMAP_V2, Constitution) vs **permanent UI layer** (OS architecture "supersedes guidance in ADR 0027") | preserved as proposed doc; ADR authority unchanged | **YES** — adopt permanent-UI ADR or keep replaceable |
| C-2 | Open Brain: adopt / investigate / reject | migration **deferred** (ADR 0031); fitness open | **YES** — decide investigate budget before any V2 migration work |
| C-3 | KB preservation (Constitution, ADR 0026) vs future storage simplification (ADR 0030, ROADMAP_V2 M5) | ADR 0034 keeps storage open; KB stays filesystem truth; M5 sequenced last | **YES** — confirm ~/kb stays out of storage consolidation |
| C-4 | Builder: execution control plane (ADR 0017) vs engineering organization (BUILDER_ORGANIZATION) vs workspace operator (OS arch) vs coordination kernel (BUILDER_V2) | preserved all as designs; no engine change | **YES** — choose the target model before any Builder V2 refactor |
| C-5 | ROADMAP.md (sole active) vs ROADMAP_V2 vs KITTY_MASTER_PROGRAM (claims "supersedes ROADMAP.md and ROADMAP_V2.md") | all preserved as proposed; ROADMAP.md remains authority until Jacob ratifies | **YES** — pick the one delivery sequence |
| C-6 | Constitution authority: v1 claims "no other document may contradict it" but is not in AUTHORITY_MAP / DECISIONS / reading order | not promoted unilaterally; flagged in ledger | **YES** — ratify Constitution into AUTHORITY_MAP or demote its supremacy claim |
| C-7 | Phase numbering: ROADMAP Gate/Phase vs ROADMAP_V2 M1–M6 vs master P0–P8 vs product Phase 0–6 | no silent renumber; master program maps them (§header) | **YES** — one numbering system |
| C-8 | Is the V2 initiative safe to apply? | **NO** until needs_decision fail-closed repaired (P0-1) | not yet |
| C-9 | Must Builder trust repair precede other Builder execution? | **YES** — B8 blocked, needs_decision doesn't park work (`builder_run.py:574-591`) | confirm |
| C-10 | Capability Manifest required before Open WebUI Home? | ADR 0029 + spec exist; Home reads runtime truth → manifest is a prerequisite | **YES** |
| C-11 | DECISIONS.md index: summary claimed "Updated 2026-08-05" but file stopped at D25/D26 | **fixed** — D27–D35 added on closeout branch | none |
| C-12 | Suspicious wired modules audit | defined but not started | P1 |

---

## 4. Continuity check results (this closeout)

Run live after repair on the canonical checkout:

- `./kitty context --agent` → **PASS 27 / WARN 0 / FAIL 0** (post-repair).
- `./kitty doctor --json` → **PASS 36 / WARN 6 / FAIL 2**. The two FAILs are
  `service:gateway` and `service:litellm` unreachable — services were not
  started this session (expected; `./kitty up` required for a live run), not a
  continuity defect. WARNs are environment-only (no mail token, no Telegram,
  codegraph daemon dead, mem0 env).

Pre-repair failures (confirmed and then fixed):

| Check | Level | Detail | Fix |
|---|---|---|---|
| `handoff:active_action` / `state:active_action` | FAIL | status `complete` (terminal) still declares a next_action | status → `in_progress`; next_action retained ⚠ schema-valid |
| `state:metadata` | FAIL (transient) | recommendations class `governance` not in schema; missing `deferred_count`/`first_deferred` | rec class → `code`, added missing v2 keys |
| `checkpoint:agreement` | FAIL (transient) | STATE/HANDOFF disagreed on `parallel_work`/`recommendations`/`next_action` | aligned metadata blocks |

Results recorded in the repaired `.claude/STATE.md` / `.claude/HANDOFF.md`.

---

## 5. Files deliberately excluded from the closeout branch

| Path | Reason |
|---|---|
| `.claude/HANDOFF.md`, `.claude/STATE.md` | continuity metadata belongs to the canonical checkout; repaired there, not duplicated into a doc branch |
| `4c0bf06b` dead-code archival | code change, not documentation; preserved in Git history on local main |
| `artifacts/proof/` (5 MB evidence dump) | raw evidence from the proof lane; text audits already committed on `proof/live-current-20260804-212614` |
| `docs/profile`, runtime files under `data/`, `logs/` | local/untracked by design |
| pomfret HANDOFF/STATE modifications | continue to describe the pomfret lane, not the doc branch |

---

## 6. Index updates performed

| Index | Change |
|---|---|
| `docs/DECISIONS.md` | added ADR rows D27–D35 (0028–0036); D26/0027 already present on origin/main |
| `docs/adr/README.md` | carried worker's index for 0027–0036 onto branch |
| `docs/README.md` (research index) | see §8 follow-ups — added reference to new research docs |
| `docs/AUTHORITY_MAP.md` | **not rewritten** — Constitution/authority conflict (C-6) left for Jacob; follow-up created |
| `docs/DISPOSITION_LEDGER.md` | follow-up created (new docs not yet in 2026-07-31 ledger) |
| `~/kb/INDEX.md` | updated (wiki entries + corrections; see §7) |
| `~/kb/NOW.md` | updated to this closeout |

---

## 7. KB artifacts verified

- `~/kb/wiki/2026-08-05-builder-packet-resurrection-trust-hole.md`
- `~/kb/wiki/2026-08-05-capability-manifest-v2-spec.md`
- `~/kb/wiki/2026-08-05-openwebui-product-plan-architecture.md`
- `~/kb/corrections/2026-08-05-rg-import-pattern.md`
- receipts referenced: `kbr_3f771b3e17b2bfd41a00`, `kbr_cf9daa5e71cd0eda4dcb`

---

## 8. Next required action per item (owners)

1. **Jacob (highest priority):** review this ledger + `LOOSE_ENDS_2026-08-05.md`
   and the recovered docs (product plan, OS architecture, 9 ADRs, forensic,
   Capability Manifest). Resolve the C-item decisions in *§3* (each is a $YES
   decision).
2. **Interactive closeout → PR:** open a PR for `closeout/2026-08-05-architecture-reconciliation`.
3. **P0 (before any Builder run):** repair + test `needs_decision` fail-closed
   (`builder_run.py:574-591` → must stop/exit non-zero on `needs_decision`).
4. **P0:** reconcile leaked open attempt `KTF-DP-03-unified-evidence-capture-proto`
   (`packet_attempts` id 68, outcome NULL, since 2026-07-30).
5. **P0:** reify the operator-approved onboarding/Work repair as a durable
   Builder task, or formally park it.
6. **Follow-ups (no code):** `docs/AUTHORITY_MAP.md` (Constitution row + reading
   order), `docs/DISPOSITION_LEDGER.md` (new files), `docs/ARCHITECTURE.md`,
   `docs/reference/CODEBASE_MAP.md`, `docs/BLUEPRINT.md`, `docs/ROADMAP.md`
   (add ADR 0030/0036 outcomes), `docs/FEATURE_REALITY_2026-07-28.md`.

---

## 9. Reported-but-not-found

| Reported artifact | Finding |
|---|---|
| "repository simplification audit" (as a standalone document) | **NOT FOUND as a file/branch anywhere.** Its findings are embodied by ADR 0030 + the dead-code archival commit `4c0bf06b`. The `docs/reference/DOCUMENTATION_AUDIT.md` (2026-07-30) is adjacent but different. No further standalone doc exists in any branch or stash. |
| "Builder Trust Model v1" (the deliverable the brief asks for) | **NOT PRODUCED.** Only the brief `artifacts/handoff-builder-trust-model-v1.md` exists. P2 design task, owner: next interactive/Builder worker after P0 gating is fixed. |

---

*Ledger produced by Continuity & Closeout. Every claim above was verified from
live Git/disk/DB during the closeout session.*
