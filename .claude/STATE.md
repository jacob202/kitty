# STATE — Kitty

> Live packet coordination. Read before picking up work. Update when claiming or finishing.

## Goal

Ship open implementation packets and keep gateway/docs clean as the codebase evolves.

## Branch

main

## Sessions (2026-07-06)

- opencode — reviewed/merged 016 (#107), authored 017 executor-ready spec, built 017 (deadline rails + sweep), opened PR #112.
- opencode (long salvage+Track-B+C session, ~early–mid) —
  - Track B landed: `docs/adr/` (14 ADRs, D1–D13 + pre-existing 0001-db-scope), `docs/codemap/` (5 lens docs), `docs/plans/`, npm ELOOP fix (`gateway/kitty-chat/.npmrc`), `.pre-commit-config.yaml` Icon block, repair_gateway_envs.sh `${HOME}` fix, DECISIONS.md slimmed to index, SIRI_SHORCUT.md rewritten.
  - C3 cron DB consolidation completed: dry run green, plan committed at `docs/phases/PHASE_C3_PLAN.md`, migration 012 (`gateway/migrations/012_cron_schedules.sql`), `scripts/dry_run_c3.py`, `gateway/cron.py` rewritten to use `kitty.db` (table `cron_schedules`) with one-shot legacy import. Live run verified: cron_schedules in `data/kitty/kitty.db`, backup contains it, legacy `data/cron_schedules.db` kept as rollback source. **Direct push to main, no PR** (per Jacob's "leave it" call).
  - Prefetcher (other model): `gateway/prefetcher.py` (188 LOC, 8 tests), wrapper in `memory_graph.unified_context`, `prefetch.warm` cron action.
  - Memory Weave port from `~/Projects/kitty-salvage/memory/memory_weave.py`: migration 013 (`gateway/migrations/013_memory_weave.sql`), `gateway/memory_weave.py` (all 11 public methods + 4 private helpers), `tests/test_memory_weave.py` (17 tests).
  - C3-4 (delete legacy `cron_schedules.db`, drop legacy import shim) is **deferred ~1 week** per `docs/phases/PHASE_C3_PLAN.md` C3-4.

## Packet claims

| Packet        | Claimed by          | Status                                                             |
| ------------- | ------------------- | ------------------------------------------------------------------ |
| 005           | opencode 2026-07-04 | ✅ shipped (#99)                                                   |
| 007           | Jacob (eb3afad)     | ✅ done                                                            |
| 008-remainder | Codex / opencode    | ✅ shipped (#111) — claim released                                 |
| 015           | —                   | ✅ shipped (#103) — Jacob live-verified                          |
| 016           | —                   | ✅ merged (#107) — awaiting Jacob's review of real Bs            |
| 017           | opencode 2026-07-06 | 🔎 PR #112 open — benefits/admin rails + urgent-thing sweep      |

**Rule for other agents:** if the status above is anything other than
`available`, the packet is taken. Pick another. If you need to release a
claim, edit this row to `available` and commit to `main`.

## Done recently

- 004 shipped (#98) — HomeState console replaces DashboardHome.
- 005 shipped (#99).
- 007 shipped (eb3afad, Jacob) — packet.delegate generator.
- 008 shipped (#111) — expert retrieval; worktree cleaned.
- Track C C1 — Removed Modules pattern applied to 6 gateway modules.
- Track C C5 — `context_assembler.py` tightened; folded `parts.py`.
- Track C C6 — doc sprawl reduced; docs reorganized into `docs/phases/`, `docs/retired/`, and `docs/plans/`.
- Track B (full) — codemap, ADRs, npm fix, repo cleanup, pre-commit Icon block. Committed on main.
- C3 cron DB consolidation (live) — `data/cron_schedules.db` → `data/kitty/kitty.db:cron_schedules`. 1242 tests pass, backup verified. Direct push to main.
- Prefetcher — `gateway/prefetcher.py` (predictive cache + cron warm action). 8 tests.
- Memory Weave port (from salvage) — migration 013 + all 11 public methods + 17 tests.
- Stale worktrees cleaned: `kitty-packet-014`, `feat-packet-005-mail-connector`.

## In flight

- **017 (PR #112 open)** — benefits/admin deadline rails, extractor, watch cron, sweep, routes. Awaiting review + merge. Build branch in `.worktrees/packet-017`.
- **C3-4 cleanup** — delete `data/cron_schedules.db`, drop `_import_legacy_cron_once` shim. Per `docs/phases/PHASE_C3_PLAN.md` C3-4: defer ~1 week from C3-3 (2026-07-06). Target window: 2026-07-13+.
- **MemoryWeave integration** — module is landed and tested but not yet wired into `unified_context`/`context_assembler` call paths. Catches the prefetcher's predictive layer a "fabric to build on" (per salvage dig).
- **Salvage port queue** (per `~/Projects/kitty-salvage/README.md` dig verdict):
  - `correction_memory.py` (931) — "highest long-term value", self-correcting memory.
  - `context_hierarchy.py` (284) — hierarchical context assembly.
  - `kitty_builder.py` (3,678) — old tool, would need re-homing onto `gateway/builder.py` + cron store.

## Blocked on Jacob

- None right now. Next time Jacob opens Kitty, the work is in good shape: Track B + Track C done, prefetcher + memory-weave landed, suite at 1269/1269. The Move-in bar (`docs/packets/README.md`) is the long pole.

## Facts from Jacob (2026-07-04, load-bearing — read before talking to him)

- He has **never used Kitty** and won't before the move-in bar
  (`docs/packets/README.md`) is met. He is phone-first; iOS pushes are
  the only channel that works (D12). Telegram and email are dead ends.
- All review artifacts must be PUSHED to his phone — "show me, I'm not
  gonna go looking for this." Never assume he opens an app unprompted.
- He conflates "spec exists" with "built" — answer status questions with
  the registry legend's words. The tier sheet = "the permission slip,"
  signed 2026-07-02.
- Missed the student-loan repayment-assistance deadline in June (~$600) —
  the trigger for packet 017. When asked what's urgent in the next 60
  days: "there's something urgent. I don't know what it is."
- Disability (SAID/CDB/DTC) is the income track; job search parked (019).
  No résumé, 10 years out of work. Personal context is rough (housing
  precarity mentioned, substance use disclosed). Stance: operator's
  situational awareness, zero lecturing, per SOUL + D9. Recovery expert
  pack is strictly opt-in and Kitty does not raise it.
- Kitty's house: the broken-screen MacBook Air, headless, on ethernet.

## Next actions

1. Review and merge PR #112 (017 — benefits rails) when CI green.
2. Packet 018 (expert packs) or 020 (GitHub connector) — next planned active packets after 017 lands.
3. C3-4 cleanup after 2026-07-13 (one-week stable window per C3 plan).
4. Wire `MemoryWeave` into `unified_context`/`context_assembler` call paths (next session, or as a small packet).
5. Salvage port queue: pick one (recommend `context_hierarchy.py` first — smallest, 284 LOC) when fresh session energy is available.
