# STATE — Kitty

> Live packet coordination. Read before picking up work. Update when claiming or finishing.

## Goal

Ship open implementation packets and keep gateway/docs clean as the codebase evolves.

## Branch

main

## Sessions (2026-07-06)

- opencode — reviewed/merged 016 (#107), authored 017 executor-ready spec, built 017 (deadline rails + sweep), opened PR #112.

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
- Stale worktrees cleaned: `kitty-packet-014`, `feat-packet-005-mail-connector`.

## In flight

- **017 (PR #112 open)** — benefits/admin deadline rails, extractor, watch cron, sweep, routes. Awaiting review + merge. Build branch in `.worktrees/packet-017`.

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

1. Review and merge PR #112 (017 — benefits rails) when CI green.
2. Packet 018 (expert packs) or 020 (GitHub connector) — next planned active packets after 017 lands.
