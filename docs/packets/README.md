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
- **Claims:** check `.claude/STATE.md` before picking up a packet — it is
  the live claim board. Claim before you build.

## Status legend (read this, it has bitten us twice)

| Mark | Means                                                              |
| ---- | ------------------------------------------------------------------ |
| ✅    | **Built and merged.** Code exists on main. You can see it.         |
| 🔎   | **PR open.** Built, awaiting review/merge.                         |
| 🚧   | **In progress.** An agent has claimed it and is building now.      |
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

**Updated:** 2026-07-04 (night — 015 merged (#103), 016 split off 021, registry corrected)

| #   | Packet                                                        | Best executor                        | Status                                                              |
| --- | ------------------------------------------------------------- | ------------------------------------ | -------------------------------------------------------------------- |
| 001 | State spine: signals, snapshots, /state/now                   | Claude Code / Codex                  | ✅ shipped                                                           |
| 002 | Inbox triage                                                  | Codex / Claude Code                  | ✅ shipped                                                           |
| 003 | Action queue with enforced tiers                              | Claude Code                          | ✅ shipped (#65 + #67)                                               |
| 004 | State home surface                                            | Claude Code                          | ✅ shipped (#98, gaps closed in #100)                                |
| 005 | Mail read-only connector (Gmail, D11)                         | Codex/Claude Code + Jacob (OAuth)    | ✅ shipped (#99) — live poll pending Jacob's OAuth setup             |
| 006 | Dev-session resume (`./kitty resume` — **not** Jacob's real-world projects; see 021) | Claude Code            | ✅ shipped (#71)                                                     |
| 007 | Delegation packet generator                                   | —                                    | ✅ shipped (eb3afad, Jacob direct to main)                           |
| 008 | Knowledge library + expert retrieval                          | Claude Code / Codex                  | ◐ items 1–3 shipped (#73); remainder 🚧 Codex (worktree)             |
| 009 | De-fake loops/insights (backend routes)                       | Claude Code                          | ✅ shipped (#75)                                                     |
| 010 | Capture-to-knowledge (file/PDF/screenshot → inbox → pipeline) | Claude Code                          | ✅ shipped (#74)                                                     |
| 011 | Brief v2 + push delivery (state-diff open + scheduler)        | Claude Code                          | ✅ shipped (#76)                                                     |
| 012 | Privacy boundary in router (§17.3, D10)                       | Claude Code                          | ✅ shipped (#72)                                                     |
| 013 | Nudges + web_monitor → signal emitters                        | Claude Code                          | ✅ shipped (#77)                                                     |
| 014 | Make the gates honest (UI tests, CI job, isolation leaks)     | any competent model                  | ✅ shipped (#94)                                                     |
| 015 | Phone channel: Kitty reaches Jacob (iMessage/Pushover)        | Claude Code / Codex                  | ✅ shipped (#103) — Jacob live-verified and merged                   |
| 016 | Next-step navigator ("just tell me what B is")                | Claude Code + strongest-model prompt | 🧭 planned — **blocked on 021** (its premise was wrong; see that packet's correction) |
| 017 | Benefits/admin rails + urgent-thing sweep                     | Claude Code (privacy care)           | 🧭 planned                                                           |
| 018 | Expert packs: car, body, proactive headlines                  | Claude Code / Codex                  | 🧭 planned — gated on 008-remainder (🚧)                             |
| 019 | Job search scaffold                                           | Claude Code / Codex                  | ⏸ parked — Jacob: "plan it, don't build it"                          |
| 020 | GitHub read-only connector                                    | Codex / Claude Code                  | 🧭 planned — pattern rides 005                                       |
| 021 | Project registry + resume (the real P6 — projects table, git/memory/signal composer) | Claude Code          | 📋 spec authored 2026-07-04 — foundation for 016, unblocks Wave 3    |

## Execution order (set 2026-07-04, supersedes 2026-07-03)

**Wave 0 — Kitty gets a house (Jacob, nearly done 2026-07-04).**
Ethernet in and verified (0% packet loss) ✅. Tailscale on phone + Mac ✅.
osascript→Messages Automation permission granted ✅. **iMessage-to-self
verified live end-to-end** (the `participant` form; see 015) ✅.
Remaining: `PUSH_IMESSAGE_RECIPIENT` line in `.env`, `./kitty up` +
`./kitty doctor`, confirm `data/gmail_token.json` exists.

**Wave 1 — Kitty reaches the phone: ~~015~~ ✅ (#103, Jacob live-verified).**

**Wave 2 — Front door + mail: ~~004~~ ✅ (#98, gaps closed in #100),
~~005~~ ✅ (#99) — live-verify on the Air pending Jacob's OAuth setup.**

**Wave 3 — The collaborator: 021 (new — build first) → 016.**
016 assumed the project registry/composer from `OPERATOR_STRATEGY.md`
§10/P6 already existed; it doesn't. 021 builds it (projects table,
`refresh()`/`resume()`); 016 is its consumer, unchanged otherwise
(~~007~~ ✅ shipped). 020 (GitHub) is optional here and enriches 016 for
code projects once both land.

**Wave 4 — The safety net: 017.** Needs 005's mail signals for the sweep
to have teeth. **End of Wave 4 = move-in day.**

**Wave 5 — Depth: 008-remainder (🚧 Codex) → 018.**

**Parked:** 019 (until Jacob activates), recovery expert pack (until Jacob
explicitly asks — see 018).

## Jacob's personal queue (not agent tasks)

1. **Finish Wave 0** (three commands, listed above — five minutes).
2. **Look at the new console** (004 shipped): with the gateway up on the
   Air, open the UI once — that's the layout-approval round, and the first
   time the front door has been real.
3. **007 sign-off:** the `packet.delegate` T1 line now in
   `config/action_tiers.json`, and the first generated packet reviewed
   against a hand-written one.
