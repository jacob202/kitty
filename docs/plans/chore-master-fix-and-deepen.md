# Master Plan: Fix & Deepen Kitty

**Date:** 2026-07-05
**Branch:** main
**Owner:** Jacob (operator-only); opencode (implementation)

This is a sequenced plan covering the three "fix and deepen" problems in
the Kitty codebase. Each track is independent and has a clear stop
condition. You can do them in any order, but the recommended sequence is
A → B → C because:

- A makes the app actually usable day-to-day (so the rest of the work
  has a real user to design for).
- B clears the documented debt so C can deepen a stable surface instead
  of deepening a moving target.
- C is the long arc; without A and B done, you can't tell if deepening
  is making the app better or just prettier.

---

## Current state (health snapshot, 2026-07-05)

| Area            | State                                                               |
| --------------- | ------------------------------------------------------------------- |
| Packets shipped | 18 of 22                                                            |
| Active PRs      | 1 (#107, next-step navigator, awaiting your week-of-real-Bs review) |
| Local tests     | ~1010 pass, 2 fail (pass on CI — data-leak)                         |
| UI tests        | 6 failing, no CI job                                                |
| Move-in day     | Wave 4 (017) is the gate; not blocked, just queued                  |
| Personal queue  | 3 items, 5 minutes of work                                          |

### What's actually broken (verified today)

- `Icon\r` files — chronic; we just installed auto-purge on checkout/merge and a pre-commit block.
- `$HOME/` literal folder at repo root (5.6MB, leftover from a script that ran with unexpanded `$HOME`).
- `.aider.chat.history.md`, `.aider.conf.yml`, `.aider.tags.cache.v4/` (32KB cache) at root — abandoned tooling residue.
- `.kitty.log` (187KB, May 10), `.kitty.pid` (May 13, stale), `.kittybuilder_session.json` (16KB, May 7) — all stale runtime state.
- `docs/SIRI_SHORTCUT.md` — references the dead shell launcher; per PROJECT_STATUS.md it's a tombstone that should be removed.
- `npm run` exits 194 silently (per PROJECT_STATUS.md) — use direct bins instead.
- Two `openwebui/open-webui` data dirs (5.4MB) — abandoned path per LEARNINGS.md.
- `data/builds/` 43MB, `data/imports/` 182MB, `data/knowledge_db/` 228MB — storage sprawl.

### What looks healthy

- 18 packets shipped, 14 in `docs/packets/`.
- Architecture docs (`docs/ARCHITECTURE.md`) are dated, specific, and load-bearing.
- `docs/LEARNINGS.md` and `docs/AGENT_HANDOFF.md` are real (not theater).
- Pre-commit framework is now wired (added today, plus Icon blocking).
- 6 worktrees but only 1 active (`.worktrees/packet-008-expert-retrieval`); others are external.

---

## Track A — Move-in prep

**Time:** ~30 min of your time, all operator.
**Outcome:** Kitty usable on a random Tuesday, with mail + phone + capture.
**Stops when:** the 3 personal-queue items in `docs/packets/README.md:139` are done.

### A1 — Finish Wave 0 (5 min, you)

From `docs/packets/README.md:113-118`:

1. Add `PUSH_IMESSAGE_RECIPIENT=<your phone number or iMessage address>` to `.env`.
2. Run `./kitty up`.
3. Run `./kitty doctor --json` and confirm `"status": "ok"`.
4. Confirm `data/gmail_token.json` exists. If not, see A2 (Gmail OAuth is a separate step).

**Verify:** `./kitty doctor --json` returns `status: ok` and the iMessage recipient is listed.

### A2 — Gmail OAuth (10 min, you — operator only)

Per `docs/packets/005-mail-connector.md`, packet 005 is shipped but live verification
needs your OAuth setup. Skip this if you don't want mail yet —
the move-in bar (Wave 4) requires mail, so this is a soft prerequisite.

**Verify:** `./kitty doctor --json` shows `gmail_token: present`.

### A3 — Visual UI approval (10 min, you)

1. With the gateway up, open `http://127.0.0.1:4000` in your browser.
2. Per `docs/packets/004-state-home.md`, the new console layout is shipped.
3. Approve or request changes. This is the only packet that needs your eyes, not CI.

**Verify:** You sign off in `.claude/STATE.md` (or tell me to).

### A4 — 007 sign-off (5 min, you + me)

Per `docs/packets/README.md:144-147`:

1. I show you the `packet.delegate` T1 line in `config/action_tiers.json`.
2. I show you a hand-written packet (e.g. `docs/packets/014-make-the-gates-honest.md`).
3. You read the T1 line and confirm the generated packet reads as well as a
   hand-written one. If it doesn't, that's a real signal we need to fix.

**Verify:** You sign off (or file a fix request).

---

## Track B — Tech debt cleanup

**Time:** ~2-3 hours of my time, zero of yours.
**Outcome:** Clean root, working test suite, CI on the UI, no stale runtime state.
**Stops when:** `git status` shows only intentional changes, all tests pass, CI is green.

### B1 — Remove `$HOME/` literal folder (5 min, me)

The folder is from a script that ran with unexpanded `$HOME` (per
`docs/LEARNINGS.md` security learnings and `AGENTS.md:58-61`). It only contains
`$HOME/kitty-services/venv-litellm/`. Confirm nothing useful is there, then
remove it and add a guard.

**Files:**

- `[DEL]` `$HOME/` (whole tree)
- `[MOD]` `.gitignore` — add an explicit guard for any future literal `$HOME` dirs

**Verify:** `ls '$HOME' 2>&1` returns "No such file"; `git status` doesn't show it.

### B2 — Clean up `.aider*` residue (5 min, me)

Three files, all from a session that was abandoned. The repo moved on.

**Files:**

- `[DEL]` `.aider.chat.history.md`, `.aider.conf.yml`, `.aider.tags.cache.v4/`

**Verify:** `ls .aider*` returns nothing; `git status` clean.

### B3 — Remove stale runtime state (5 min, me)

`.kitty.log`, `.kitty.pid`, `.kittybuilder_session.json` are all from May.
`.kitty.pid` is in `.gitignore` (per `AGENTS.md:53`) so won't be committed, but
it's noise.

**Files:**

- `[DEL]` `.kitty.log`, `.kitty.pid`, `.kittybuilder_session.json`
- `[VERIFY]` `.gitignore` already excludes `.kitty.pid`; add `.kitty.log` and
  `.kittybuilder_session.json` if not already there.

**Verify:** None of these exist at root; `.gitignore` covers them.

### B4 — Tombstone `docs/SIRI_SHORTCUT.md` (5 min, me)

Per `PROJECT_STATUS.md:56`, this references the dead shell launcher. Either
delete it or update it to point at `./kitty` and the new architecture.

**Files:**

- `[MOD]` `docs/SIRI_SHORTCUT.md` — rewrite to use `./kitty up` / `down` /
  `doctor`, or `[DEL]` if you don't use Siri Shortcuts.

**Verify:** No mentions of the dead launcher (`scripts/up.sh`, etc.) anywhere
in the repo.

### B5 — Fix the 2 local-failing tests (30 min, me)

From `PROJECT_STATUS.md:33-36`:

- `tests/test_action_queue.py::test_t0_executes_from_proposed_and_records_result`
- `tests/test_state_composer.py::test_real_sources_compose_against_isolated_stores`

Both leak real `data/` state. The fix is to make them use a tmp_path fixture
and seed their own state. The pattern already exists in the suite — find one
that does it right and mirror it.

**Files:**

- `[MOD]` `tests/test_action_queue.py` — switch to `tmp_path`
- `[MOD]` `tests/test_state_composer.py` — switch to `tmp_path`

**Verify:** `python3.12 -m pytest tests/test_action_queue.py tests/test_state_composer.py -q` returns all pass.

### B6 — Fix the 6 UI test failures (1-2 hours, me)

Per `PROJECT_STATUS.md:54` and the test files named there:
`tests/SessionSidebar.test.tsx`, `tests/gatewayIntegration...`.

This is the hard one. The pattern is probably:

- UI tests were written against an old version of the components
- The console-home refactor (packet 004) changed the layout
- Tests didn't get updated

**Files:**

- `[MOD]` `gateway/kitty-chat/tests/*.test.tsx` — update to match current components

**Verify:** `cd gateway/kitty-chat && npm test` returns 0 failures.

### B7 — Fix `npm run` 194 (15 min, me)

Per `PROJECT_STATUS.md:53`, the suggested fix is "use direct bins" (per
`docs/AGENT_HANDOFF.md`). The 194 is a Node 26.4 / npm 11.17 issue. I can
either pin to a working version, or replace `npm run` invocations with
direct bin calls (`node_modules/.bin/next build` etc.).

**Files:**

- `[MOD]` `gateway/kitty-chat/package.json` (scripts)
- `[MOD]` any workflow / AGENTS.md that says `npm run`

**Verify:** `cd gateway/kitty-chat && npm run build` exits 0.

### B8 — Add kitty-chat CI job (30 min, me)

Per `PROJECT_STATUS.md:54`, there's no UI test job in CI. Add one that runs
`npm test` on PRs that touch `gateway/kitty-chat/`.

**Files:**

- `[MOD]` `.github/workflows/*.yml` (find the existing CI workflow)

**Verify:** Open a no-op PR; CI runs the UI test job and it reports status.

### B9 — Remove dead `openwebui/open-webui` data dirs (15 min, me)

Two parallel dirs (`data/openwebui/`, `data/open-webui/`) per
`docs/LEARNINGS.md:3` "abandoned paths." One is active (if any), the other is
abandoned. Find which and delete the other. Both are in `.gitignore` so this
is local hygiene, not repo hygiene.

**Files:**

- `[DEL]` one of `data/openwebui/` or `data/open-webui/` (whichever is
  abandoned; I'll confirm before deleting)

**Verify:** Disk usage goes down; `./kitty up` still works.

### B10 — Triage `data/builds/`, `data/imports/`, `data/knowledge_db/` (30 min, me)

These are 43MB / 182MB / 228MB respectively. The "right" answer depends on
what's in them:

- `data/builds/` — probably per-build artifacts; can be deleted unless actively used.
- `data/imports/` — chat exports (Claude, ChatGPT). 182MB is suspicious; probably has
  duplicates or you imported the same export twice.
- `data/knowledge_db/` — the heavy one. If it's reference knowledge vectors, it's load-bearing.
  If it's a ChromaDB that's been superseded by `data/chromadb/` and `data/chroma/`, it's not.

I'll inspect each, show you the breakdown, and let you decide what to keep.

**Files:** depends on findings. No deletions without your sign-off.

**Verify:** Disk usage reduced by at least 200MB without losing anything load-bearing.

### B11 — Add an ADR directory (30 min, me)

`docs/DECISIONS.md` exists but the `improve-codebase-architecture` skill says
"Kitty has no formal ADR directory yet. Treat existing docs under `docs/` as
load-bearing unless the user says otherwise." Move the decisions into proper
ADRs so they're discoverable per-decision, not as one giant file.

**Files:**

- `[NEW]` `docs/adr/` (with `0000-template.md` if one doesn't exist locally)
- `[MOD]` migrate top 10 decisions from `docs/DECISIONS.md` to `docs/adr/NNNN-*.md`
- `[MOD]` `docs/DECISIONS.md` — keep as an index, link to the ADRs

**Verify:** Each existing decision in `DECISIONS.md` has a link to an ADR.

---

## Track C — Architecture deepening

**Time:** ~1-2 days of my time, zero of yours.
**Outcome:** Modules are deep, not shallow. AI agents can navigate. Storage is one story.
**Stops when:** A `codemap/` exists that someone can read instead of grepping.

### C1 — Apply the "Removed Modules" pattern to the rest of the gateway (2-3 hours, me)

`docs/ARCHITECTURE.md:111-118` lists 6 modules that were just removed because
they were shallow (interface nearly as complex as the implementation). The skill
behind this is `improve-codebase-architecture` — it has a "deletion test" that
checks if a module concentrates or just moves complexity when removed.

I'll walk every file in `gateway/` and identify:

- **Pass-through modules** (interface as complex as implementation, no depth).
- **Orphaned modules** (no callers).
- **Single-adapter shims** (only one implementation behind a seam; the seam is hypothetical).

For each, I propose: delete, fold into caller, or find a second adapter to
justify the seam.

**Files:** varies; expect ~3-5 module removals or fold-ins.

**Verify:** `docs/ARCHITECTURE.md` "Removed Modules" section grows; `pytest tests/`
still passes.

### C2 — Audit and fix the `memory_graph.py` shims (1 hour, me)

`docs/LEARNINGS.md` L-CAND-2 calls this out: 6 module-level `_XxxAdapter` shims
are still present in `gateway/memory_graph.py:393-399` despite a "DONE 2026-06-18"
label on the related work. `_get_adapters()` falls through to `_default_adapters()`.

This is the "false DONE" problem. Either:

- The shims are needed (then remove the fall-through and make them primary).
- The shims are not needed (then remove them and rely on `_default_adapters`).

I'll figure out which and fix it.

**Files:**

- `[MOD]` `gateway/memory_graph.py`

**Verify:** Module compiles; tests pass; L-CAND-2 can be promoted to a closed lesson.

### C3 — Consolidate the 8+ subsystem SQLite DBs (2-4 hours, me)

Per `docs/ARCHITECTURE.md:72`, each subsystem manages its own connection:
cron, builds, task_queue, ingestion, web_monitors, autonomy, model_digest, signals.
Plus the main `data/kitty/kitty.db`. That's 9+ separate SQLite files.

The depth argument: each subsystem DB is a single-purpose pass-through. The
shallow alternative (consolidate into one DB with table prefixes) trades 9
file handles for 1 and makes cross-subsystem queries possible (e.g. "show me
all state related to packet 016"). It also means migrations live in one place.

**Files:**

- `[MOD]` `gateway/cron.py`, `gateway/builds.py`, `gateway/task_queue.py`,
  `gateway/ingestion.py`, `gateway/web_monitor.py`, `gateway/autonomy_state.py`,
  `gateway/model_digest.py`, `gateway/signal_store.py` — switch to the main
  `kitty.db` connection
- `[NEW]` `gateway/db.py` (if not already the shared connection module)

**Verify:** `data/*.db` is reduced to 1 file; `pytest tests/` passes; `./kitty
doctor` shows clean state.

### C4 — Generate a real codemap (2-3 hours, me)

Per the `codemap` skill, the deliverable is "a few whole-system 'lens'
documents (overview, capabilities, dataflow, codemap, domain) — read
instead of the code to understand what a system does."

This is the doc that lets you (a non-coder) read the architecture instead
of asking me. The skill is designed for AI agents but the output is human-
readable. I'll generate the five lenses and save them under `docs/codemap/`.

**Files:**

- `[NEW]` `docs/codemap/README.md` (entry point)
- `[NEW]` `docs/codemap/00-overview.md`
- `[NEW]` `docs/codemap/10-capabilities.md`
- `[NEW]` `docs/codemap/20-dataflow.md`
- `[NEW]` `docs/codemap/30-codemap.md`
- `[NEW]` `docs/codemap/40-domain.md`

**Verify:** You can open `docs/codemap/README.md` and answer "what does Kitty
do?" in 60 seconds.

### C5 — Audit `context_assembler.py` (1 hour, me)

`docs/ARCHITECTURE.md:39` calls it a "10-step prompt/context assembly pipeline."
10 steps is a lot — most pipelines that long have steps that could be merged
or removed. I'll read it end-to-end, identify any step that is shallow or
could be expressed in terms of the others, and propose either a tightening
or a doc note about why the 10 steps are earned.

**Files:**

- `[MOD]` `gateway/context_assembler.py` (if tightening helps)
- `[NEW]` `docs/adr/NNNN-context-assembler-shape.md` (if the shape is load-bearing)

**Verify:** Pipeline is shorter or documented as load-bearing; tests pass.

### C6 — Reduce doc sprawl (1 hour, me)

36 markdown files in `docs/`. Some are load-bearing (ARCHITECTURE,
LEARNINGS, DECISIONS, packets). Some are dated one-offs (CODE_SNIPING_AUDIT,
DESKTOP_PHASE_1_HARD_CRITIC_REVIEW). I'll propose:

- A "core docs" list (always load-bearing)
- A "phases" subdir for dated plans (move them out of `docs/`)
- A "retired" subdir for done-and-archived audits

**Files:** structural moves; no deletions of content, only relocation.

**Verify:** `ls docs/` returns ~10 load-bearing files at the top level.

### C7 — Add a real `tests/codemap_test.py` (30 min, me)

A "smoke test for the architecture" — a single test that imports the
public API of every gateway module and asserts it loads. Cheap insurance
against import-time breakage (which bit you in L-CAND-6 with
`mcp/imagen/server.py`).

**Files:**

- `[NEW]` `tests/codemap_test.py`

**Verify:** `pytest tests/codemap_test.py` passes; if a module's public
API breaks, this test fails fast.

---

## Operator checklist (your part)

Across all three tracks, the only things you need to do are:

- [ ] **A1** — add `PUSH_IMESSAGE_RECIPIENT` to `.env` (5 min)
- [ ] **A2** — Gmail OAuth (10 min, only if you want mail)
- [ ] **A3** — visual UI approval (10 min)
- [ ] **A4** — read `config/action_tiers.json` and a sample packet, sign off (5 min)
- [ ] **B10** — confirm what to keep in `data/builds/`, `data/imports/`,
      `data/knowledge_db/` (15 min, only if I find anything to delete)
- [ ] **B11** — name any decision you want me to skip (none if you trust me)

Total your-time: ~30 min if you skip mail, ~45 min with mail.

---

## Risks

| Risk                                                             | Likelihood | Impact | Mitigation                                                                                |
| ---------------------------------------------------------------- | ---------- | ------ | ----------------------------------------------------------------------------------------- |
| Track C reveals the codebase needs a larger refactor than 2 days | Medium     | High   | Stop at C1; write a C-prime plan; do not push past 2 days.                                |
| B6 (UI tests) turns out to require re-writing components         | Medium     | Medium | Stop and ask; the alternative is a `<skip>` flag in the test, but that hides the problem. |
| B10 (data triage) reveals you actually needed what I delete      | Low        | High   | No deletions without your sign-off.                                                       |
| C3 (DB consolidation) loses state during migration               | Low        | High   | Dry-run first; back up to `data/backups/<date>/` before each subsystem.                   |

---

## Stop conditions

Stop after Track A if:

- You want to use the app for a week before doing more work.

Stop after Track B if:

- C feels too big and you want to do it later.

Stop in the middle of Track C if:

- Any single step (C1-C7) takes more than 4 hours.
- The output doesn't feel like a deepening — if a step is making the code
  more complex rather than less, that's a signal to stop and re-plan.

---

## What gets shipped, in plain English

After all three tracks:

- **Track A:** You can text Kitty, Kitty can text you, the app boots clean, the
  new console UI has your sign-off.
- **Track B:** The repo root has no leftover tool residue, no stale runtime
  state, no dead launchers. All tests pass. CI catches UI regressions. ADRs
  are first-class.
- **Track C:** Someone can read `docs/codemap/README.md` and understand the
  app in 60 seconds. The 9 SQLite DBs are 1. The "shallow module" pattern is
  applied consistently. The `context_assembler` is either shorter or
  documented as earned complexity.
