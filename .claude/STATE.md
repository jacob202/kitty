# STATE — Kitty

> Live packet coordination. Read before picking up work. Update when claiming or finishing.

## Goal

Ship open implementation packets and keep gateway/docs clean as the codebase evolves.

## Branch

main

## Sessions (2026-07-06)

- opencode — cleaned stale worktrees, shipped packet 008 (#111), applied Track C C1/C5/C6.
- opencode (close-out, ~13:30–13:55) — committed pre-commit cleanup (1abfcef, drops ruff-format/ruff --fix/prettier auto-fix hooks that were corrupting the index during salvage); deleted 5 unreferenced cat PNGs; wrote session log to `.agent/session_logs/20260706T195358Z-handoff.md`. Bundled C6 renames into 7f5036c by accident; recovered with `git reset --soft HEAD~1 && git commit --only .pre-commit-config.yaml`.

## Packet claims

| Packet        | Claimed by          | Status                                                             |
| ------------- | ------------------- | ------------------------------------------------------------------ |
| 005           | opencode 2026-07-04 | ✅ shipped (#99)                                                   |
| 007           | Jacob (eb3afad)     | ✅ done                                                            |
| 008-remainder | Codex / opencode    | ✅ shipped (#111) — claim released                                 |
| 015           | —                   | ✅ shipped (#103) — Jacob live-verified                          |

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
- C3 prep shipped (593c846) — `gateway/migrations/012_cron_schedules.sql` + `scripts/dry_run_c3.py`. Plan in `docs/phases/PHASE_C3_PLAN.md`.
- Pre-commit cleanup (1abfcef) — drops ruff-format, ruff --fix, and prettier auto-fix hooks. Keeps check-only pre-commit-hooks + the local no-macos-metadata block.
- 5 unreferenced cat PNGs deleted from `design-system/v2-reference/cat-assets/` (~4.4MB).
- Stale worktrees cleaned: `kitty-packet-014`, `feat-packet-005-mail-connector`.
- Stash `stash@{0}` (WIP-before-salvage-integration-20260705) dropped after the salvage commit landed.

## In flight

- **C3 DB consolidation** — Jacob is mid-edit on `gateway/cron.py` (+134/-?) and `tests/test_cron.py` (+245/-?). The changes replace the standalone `data/cron_schedules.db` with the shared `data/kitty/kitty.db` table `cron_schedules`; legacy DB is imported once on first `init_db()` if destination is empty, never deleted (rollback is a one-liner). When the edits are done: run `python scripts/dry_run_c3.py` to verify the stop-migrate-restart protocol, then `pytest tests/test_cron.py -q`, then commit (suggested: `feat(c3): migrate cron schedules to kitty.db` with a body citing 012_cron_schedules.sql and the plan in `docs/phases/PHASE_C3_PLAN.md`).

## Blocked on Jacob

- Nothing.

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

1. Complete C3: finish `gateway/cron.py` + `tests/test_cron.py`, dry-run, test, commit.
2. First free executor: claim and build packet 015 (phone-first delivery / move-in bar). Update this table before starting.
