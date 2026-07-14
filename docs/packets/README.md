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

## Packet intake gate

Packets are for executor-ready work, not raw excitement. A new idea does not
become active work just because it sounds good in a planning chat.

Before authoring or activating a packet, classify it as exactly one of:

| Class            | Meaning                                                  | Allowed next move                                    |
| ---------------- | -------------------------------------------------------- | ---------------------------------------------------- |
| `idea_seed`      | Interesting spark, not scoped yet                        | Capture in notes / idea mine only                    |
| `decision`       | A choice Jacob made that future work should respect      | Record in `docs/DECISIONS.md` or the relevant packet |
| `spec_candidate` | Could become a packet after shaping                      | Author a draft/spec PR, keep out of execution order  |
| `active_packet`  | Executor-ready and approved to compete for build time    | Add to registry + execution order                    |
| `after_move_in`  | Valuable, but not needed before H1 move-in               | Park behind move-in bar                              |
| `parked`         | Explicitly not active until Jacob says the trigger words | Mark ⏸ and name the activation trigger               |
| `reject`         | Cool maybe, but not worth carrying                       | Do not preserve as work                              |

A packet may enter the execution order only when it has:

1. A clear activation class (`active_packet`, `after_move_in`, or `parked`).
2. A visible demo contract: what Jacob can see or run after it lands.
3. A scope budget: expected diff size and stop/split conditions.
4. Privacy/sensitivity notes when touching mail, journal, health/admin,
   benefits, recovery/support, memory, or chat logs.
5. Acceptance criteria with concrete verification commands or review artifacts.

Default bias: protect the move-in bar. New packets serve H1 or wait their turn.

**Numbering:** this registry table owns packet numbers. Take max(number)+1
from the table and add your row in the same commit that creates the file —
a spec file with no registry row is a stray file, not work (see L-CAND-12;
it has already happened twice in one day). This applies on **main's** copy
of the table: a spec authored on a side branch does not own its number until
it merges, and a file that lands without a row gets its row added the moment
anyone notices (that's how 026 collided a third time — L-CAND-13).

## Status legend (read this, it has bitten us twice)

| Mark | Means                                                              |
| ---- | ------------------------------------------------------------------ |
| ✅   | **Built and merged.** Code exists on main. You can see it.         |
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

**Updated:** 2026-07-14 (registry de-duplicated — two drifted copies of this
table merged back into one; missing 026/027 rows added; 028 reasoning engine
authored)

| #   | Packet                                                                               | Best executor                        | Status                                                                                                                            |
| --- | ------------------------------------------------------------------------------------ | ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| 001 | State spine: signals, snapshots, /state/now                                          | Claude Code / Codex                  | ✅ shipped                                                                                                                        |
| 002 | Inbox triage                                                                         | Codex / Claude Code                  | ✅ shipped                                                                                                                        |
| 003 | Action queue with enforced tiers                                                     | Claude Code                          | ✅ shipped (#65 + #67)                                                                                                            |
| 004 | State home surface                                                                   | Claude Code                          | ✅ shipped (#98, gaps closed in #100)                                                                                             |
| 005 | Mail read-only connector (Gmail, D11)                                                | Codex/Claude Code + Jacob (OAuth)    | ✅ shipped (#99) — OAuth done, live on the Air 2026-07-05                                                                         |
| 006 | Dev-session resume (`./kitty resume` — **not** Jacob's real-world projects; see 021) | Claude Code                          | ✅ shipped (#71)                                                                                                                  |
| 007 | Delegation packet generator                                                          | —                                    | ✅ shipped (eb3afad, Jacob direct to main)                                                                                        |
| 008 | Knowledge library + expert retrieval                                                 | Claude Code / Codex                  | ✅ shipped — items 1–3 (#73), remainder (#111)                                                                                    |
| 009 | De-fake loops/insights (backend routes)                                              | Claude Code                          | ✅ shipped (#75)                                                                                                                  |
| 010 | Capture-to-knowledge (file/PDF/screenshot → inbox → pipeline)                        | Claude Code                          | ✅ shipped (#74)                                                                                                                  |
| 011 | Brief v2 + push delivery (state-diff open + scheduler)                               | Claude Code                          | ✅ shipped (#76)                                                                                                                  |
| 012 | Privacy boundary in router (§17.3, D10)                                              | Claude Code                          | ✅ shipped (#72)                                                                                                                  |
| 013 | Nudges + web_monitor → signal emitters                                               | Claude Code                          | ✅ shipped (#77)                                                                                                                  |
| 014 | Make the gates honest (UI tests, CI job, isolation leaks)                            | any competent model                  | ✅ shipped (#94)                                                                                                                  |
| 015 | Phone channel: Kitty reaches Jacob (iMessage/Pushover)                               | Claude Code / Codex                  | ✅ shipped (#103) — Jacob live-verified and merged                                                                                |
| 016 | Next-step navigator ("just tell me what B is")                                       | Claude Code + strongest-model prompt | ✅ shipped (#107, hardened #109) — closes out after a week of Jacob judging real Bs, not on merge alone                           |
| 017 | Benefits/admin rails + urgent-thing sweep                                            | Claude Code (privacy care)           | ✅ shipped (#112)                                                                                                                 |
| 018 | Expert packs: car, body, proactive headlines                                         | Claude Code / Codex                  | ✅ shipped (#119)                                                                                                                 |
| 019 | Job search scaffold                                                                  | Claude Code / Codex                  | ⏸ parked — Jacob: "plan it, don't build it"                                                                                       |
| 020 | GitHub read-only connector                                                           | Codex / Claude Code                  | 🧭 planned — pattern rides 005                                                                                                    |
| 021 | Project registry + resume (the real P6 — projects table, git/memory/signal composer) | Claude Code                          | ✅ shipped (#106)                                                                                                                 |
| 022 | Magic Kitty: cross-project insight synthesis (D13)                                   | strongest-model prompt + Claude Code | 🚧 in progress — packet authored 2026-07-12; route/module/tests on main (#153); executor contract + privacy hardening remain      |
| 023 | Memory taste + creative continuity (renumbered from 021, #101)                       | Claude Code / Codex + Jacob review   | ✅ shipped (#119 backend + #123 UI)                                                                                               |
| 024 | Chat log idea mine (renumbered from 022, #102)                                       | strongest-model prompt + Claude Code | 📋 spec authored — `after_move_in`: obeys 023's taste rules either way                                                            |
| 025 | Imagegen pipeline v2: local-first, criteria-verified loop                            | Claude Code + Jacob (installs/taste) | 📋 spec authored 2026-07-05 — replaces fal (cost); Draw Things + ComfyUI                                                          |
| 026 | Builder reliability and truthful state                                               | Codex / Claude Code + independent reviewer | ◐ rails landed; restart/recovery closeout runs as 027 (row added late — file predates it; see L-CAND-13)                    |
| 027 | Builder restart/recovery proof                                                       | Builder free worker (KittyBuilder)   | 🚧 in Builder queue — spec is the initiative manifest `docs/initiatives/packet-027-v1.json` (#174/#175), not a packets/ file      |
| 028 | Reasoning engine: visible thinking traces, reasoning-level knob, token optimizer     | Claude Code / Codex                  | 📋 spec authored 2026-07-14 — wave 4 of the chat cutting-edge plan (PR #164, closed), renumbered from that branch's 026           |

## Execution order (set 2026-07-04, supersedes 2026-07-03)

**Wave 0 — Kitty gets a house: ✅ complete 2026-07-05.**
Ethernet ✅. Tailscale ✅. iMessage-to-self live ✅. `PUSH_IMESSAGE_RECIPIENT`
set ✅. Gmail OAuth done — `data/gmail_token.json` present ✅. Doctor:
`pass=11 warn=1 fail=0` (only Telegram, which is optional) — verified live
on the Air. Known cosmetic debt: a stray quote on `.env` line 1 (doctor's
new `env:parse` check names it; #109).

**Wave 1 — Kitty reaches the phone: ~~015~~ ✅ (#103, Jacob live-verified).**

**Wave 2 — Front door + mail: ~~004~~ ✅ (#98, gaps closed in #100),
~~005~~ ✅ (#99) — live-verify on the Air pending Jacob's OAuth setup.**

**Wave 3 — The collaborator: ~~021~~ ✅ (#106) → ~~016~~ ✅ (#107, #109).**
Live on Jacob's Air 2026-07-05: doctor fully green (mail token, push
channel, litellm, chromadb), first real B generated. The review loop (a
week of real Bs) is what actually closes 016 out, not the merge.
020 (GitHub) is optional here and enriches 016 for code projects.

**Wave 4 — The safety net: ~~017~~ ✅ (#112).** Needs
005's mail signals for the sweep to have teeth — those are live as of
2026-07-05. **End of Wave 4 = move-in day. (Move-in day reached)**

**Wave 5 — Depth: 008-remainder ✅ (#111) → 018 ✅ (#119) → 022 (Magic Kitty).**

**Side track (Jacob-driven, parallel to any wave): 025 imagegen pipeline.**
Explicitly requested 2026-07-05; doesn't gate move-in, doesn't wait for it.

**Depth track (post-move-in, added 2026-07-14): 026 → 027 → 028.**
Builder reliability closes out first (026 rails landed, 027 proves
restart/recovery), then 028 (reasoning engine) builds slice by slice — it
makes every chat cheaper and sharper, but life-first initiative work (ADR
0016) takes build time ahead of it whenever both are ready.

**After move-in: 023 → 024** (memory taste before chat-log mining, so the
mine obeys the taste rules from day one).

**Parked:** 019 (until Jacob activates), recovery expert pack (until Jacob
explicitly asks — see 018).

## Jacob's personal queue (not agent tasks)

1. **Judge the Bs** (016 review loop): `./kitty project add` your 2–3
   real projects with real paths, `refresh` each, and read what comes
   back. A week of "useful or garbage?" verdicts closes the packet.
2. **Look at the new console** (004 shipped): with the gateway up on the
   Air, open the UI once — that's the layout-approval round, and the first
   time the front door has been real.
3. **007 sign-off:** the `packet.delegate` T1 line now in
   `config/action_tiers.json`, and the first generated packet reviewed
   against a hand-written one.
4. **025 installs** (when the packet lands): Draw Things model downloads
   are ~7 GB — start them before a work session, not during.
