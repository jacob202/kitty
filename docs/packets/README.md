# Implementation Packets

Executor-ready work units for the state + action spine (D9,
`docs/OPERATOR_STRATEGY.md` §15). One packet = one branch = one PR.

Rules for executors (any model or human):

- Read the packet, not the whole repo. The packet carries all context you
  need; if it doesn't, the packet is defective — say so, don't improvise.
- Stay inside "files likely touched." "Files not to touch" is a hard no.
- Every acceptance criterion must be verified by a command you actually ran.
- If the packet turns out too broad mid-flight, stop and split it — do not
  keep going.
- Before merge: full CI green on check runs (not combined status), reviewer
  pass on the diff, Jacob's review where the packet names it.

## Registry

**Updated:** 2026-07-03

| #   | Packet                                                        | Best executor                                 | Status                                                 |
| --- | ------------------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------ |
| 001 | State spine: signals, snapshots, /state/now                   | Claude Code / Codex                           | ✓ shipped                                              |
| 002 | Inbox triage                                                  | Codex / Claude Code                           | ✓ shipped                                              |
| 003 | Action queue with enforced tiers                              | Claude Code                                   | ✓ shipped (#65 + #67)                                  |
| 004 | State home surface                                            | Claude Code                                   | ✓ shipped (#98)                                        |
| 005 | Mail read-only connector                                      | Codex/Claude Code + Jacob (credentials)       | 📋 ready — packet authored 2026-07-03 (Gmail API, D11) |
| 006 | Project resume                                                | Claude Code                                   | ✓ shipped (#71)                                        |
| 007 | Delegation packet generator                                   | strongest model (template) + Codex (plumbing) | 📋 ready — packet + template authored 2026-07-03       |
| 008 | Knowledge library + expert retrieval                          | Claude Code / Codex                           | ◐ items 1–3 shipped (#73); remainder = items 4–6       |
| 009 | De-fake loops/insights (backend routes)                       | Claude Code                                   | ✓ shipped (#75)                                        |
| 010 | Capture-to-knowledge (file/PDF/screenshot → inbox → pipeline) | Claude Code                                   | ✓ shipped (#74)                                        |
| 011 | Brief v2 + push delivery (state-diff open + scheduler)        | Claude Code                                   | ✓ shipped (#76)                                        |
| 012 | Privacy boundary in router (§17.3)                            | Claude Code                                   | ✓ shipped (#72)                                        |
| 013 | Nudges + web_monitor → signal emitters                        | Claude Code                                   | ✓ shipped (#77)                                        |
| 014 | Make the gates honest (UI tests, CI job, isolation leaks)     | any competent model — mechanical              | ✓ shipped (#94)                                        |

Every open packet now has an authored file in this directory; nothing remains spec-only.

## Execution order (set 2026-07-03)

**014 → 004 → 005 → 007 → 008-remainder.**

- **014 first, non-negotiable:** 004's acceptance criteria are unverifiable
  while the UI suite is red and no CI job runs it. 014 is mechanical —
  cheapest available executor.
- **004 (console home)** is the active phase; execution plan at
  `docs/superpowers/specs/2026-07-02-console-home-phase-design.md`.
- **005 and 007** are independent of each other and of 004 — either can run
  in parallel with 004 if capacity exists. Between them, 005 first: mail
  signals give the console real data (the phase plan's "dead console on day
  one" risk).
- **008-remainder** last: expert retrieval deepens knowledge, but the spine
  and front door come first (OPERATOR_STRATEGY §19).

## Jacob's personal queue (not agent tasks)

1. **Gmail OAuth setup** (packet 005): Google Cloud project + consent screen,
   client secret path into `.env` as `GMAIL_CLIENT_SECRET_FILE`, run the
   one-time `--auth` flow. Blocks 005's live verification only, not its PR.
2. **004 screenshot review:** one layout approval round before polish.
3. **007 sign-offs:** the `packet.delegate` T1 line on the signed tier
   sheet, and the first generated packet reviewed side by side with a
   hand-written one.
