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

## Status legend (read this, it has bitten us twice)

| Mark | Means                                                              |
| ---- | ------------------------------------------------------------------ |
| ✅    | **Built and merged.** Code exists on main. You can see it.         |
| 📋   | **Spec authored, NOT built.** A markdown file, zero shipped code.  |
| 🧭   | **Planned.** Scoped here, needs an authoring pass before hand-off. |
| ⏸    | **Parked** by Jacob's explicit call. Activates only when he says.  |
| ◐    | Partially built; the file says which items remain.                 |

📋 ≠ ✅. If Jacob asks "is X done" the answer distinguishes these words.

## The finish line: move-in day

Decided by Jacob 2026-07-04 (D12 in `docs/DECISIONS.md`). Jacob has never
used Kitty and won't until it clears this bar. H1 is **done enough to move
into** when, on a random Tuesday, all of the following are true:

1. A morning brief lands on his **iPhone** unprompted, with real mail,
   real deadlines, and what changed.
2. Every active project shows **one concrete next step** ("what's B"),
   with a line about what's already done.
3. Benefits/admin paper is watched: photograph a letter, the deadline gets
   extracted and escalates to his phone before it bites. The $600-class
   miss can't happen silently again.
4. Capture comes back: anything thrown at Kitty from the phone resurfaces
   at the right moment.
5. Everything Kitty did is an auditable queue row; nothing external ever
   sent without approval.

Everything else — experts, GitHub, job search — deepens the house after
move-in. It does not delay move-in.

## Registry

**Updated:** 2026-07-04

| #   | Packet                                                        | Best executor                        | Status                                          |
| --- | ------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------ |
| 001 | State spine: signals, snapshots, /state/now                   | Claude Code / Codex                  | ✅ shipped                                       |
| 002 | Inbox triage                                                  | Codex / Claude Code                  | ✅ shipped                                       |
| 003 | Action queue with enforced tiers                              | Claude Code                          | ✅ shipped (#65 + #67)                           |
| 004 | State home surface                                            | Claude Code                          | 📋 spec authored, not built — active            |
| 005 | Mail read-only connector (Gmail, D11)                         | Codex/Claude Code + Jacob (OAuth)    | 📋 spec authored, not built                     |
| 006 | Project resume                                                | Claude Code                          | ✅ shipped (#71)                                 |
| 007 | Delegation packet generator                                   | Codex / Claude Code (template done)  | 📋 spec authored, not built                     |
| 008 | Knowledge library + expert retrieval                          | Claude Code / Codex                  | ◐ items 1–3 shipped (#73); remainder items 4–6  |
| 009 | De-fake loops/insights (backend routes)                       | Claude Code                          | ✅ shipped (#75)                                 |
| 010 | Capture-to-knowledge (file/PDF/screenshot → inbox → pipeline) | Claude Code                          | ✅ shipped (#74)                                 |
| 011 | Brief v2 + push delivery (state-diff open + scheduler)        | Claude Code                          | ✅ shipped (#76)                                 |
| 012 | Privacy boundary in router (§17.3, D10)                       | Claude Code                          | ✅ shipped (#72)                                 |
| 013 | Nudges + web_monitor → signal emitters                        | Claude Code                          | ✅ shipped (#77)                                 |
| 014 | Make the gates honest (UI tests, CI job, isolation leaks)     | any competent model                  | ✅ shipped (#94)                                 |
| 015 | Phone channel: Kitty reaches Jacob (iMessage/Pushover)        | Claude Code / Codex                  | 📋 spec authored 2026-07-04, not built — next up |
| 016 | Next-step navigator ("just tell me what B is")                | Claude Code + strongest-model prompt | 🧭 planned                                       |
| 017 | Benefits/admin rails + urgent-thing sweep                     | Claude Code (privacy care)           | 🧭 planned                                       |
| 018 | Expert packs: car, body, proactive headlines                  | Claude Code / Codex                  | 🧭 planned — gated on 008-remainder             |
| 019 | Job search scaffold                                           | Claude Code / Codex                  | ⏸ parked — Jacob: "plan it, don't build it"     |
| 020 | GitHub read-only connector                                    | Codex / Claude Code                  | 🧭 planned — pattern rides 005                  |

## Execution order (set 2026-07-04, supersedes 2026-07-03)

**Wave 0 — Kitty gets a house (Jacob, ~1 hour, no agent).**
Progress 2026-07-04: ethernet adapter bought ✅, Tailscale already on the
phone + computer ✅. Remaining, in one sit-down at the Air: plug in
ethernet and confirm internet; sign into Messages (Apple ID) and trigger
the one-time osascript→Messages Automation permission dialog while the
screen still works (015 needs it); set `PUSH_IMESSAGE_RECIPIENT` in
`.env`; run `./kitty up` + `./kitty doctor`; confirm the Gmail token:
`ls ~/Projects/kitty/data/gmail_token.json`.

**Wave 1 — Kitty reaches the phone: 015.**
Before any more features: without a channel to a phone-first user, every
feature ships into a void. This also fixes the review loop — artifacts
(like 004's screenshot) get pushed TO Jacob.

**Wave 2 — Front door + mail: 004, then 005** (independent; parallel-ok if
capacity exists). 004's screenshot review goes through 015.

**Wave 3 — The collaborator: 016, then 007.** 020 (GitHub) is optional
here and enriches 016 for code projects.

**Wave 4 — The safety net: 017.** Needs 005's mail signals for the sweep
to have teeth. **End of Wave 4 = move-in day.**

**Wave 5 — Depth: 008-remainder → 018.**

**Parked:** 019 (until Jacob activates), recovery expert pack (until Jacob
explicitly asks — see 018).

## Jacob's personal queue (not agent tasks)

1. **Wave 0 hardware hour** (above) — the only thing between the plan and
   execution. Everything else was cleared: tier sheet signed 2026-07-02,
   Gmail OAuth done 2026-07-04 (verify with the `ls` above).
2. That's it. Reviews (004 screenshot, first Bs, sweep report) come to
   your phone; you answer them there.
