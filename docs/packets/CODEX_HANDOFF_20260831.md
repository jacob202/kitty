# Codex handoff — 2026-08-31

Read this before touching anything. It is written to be enough on its own.

## Who owns what

Every implementation has exactly one execution owner. Builder owns the backend
packets below; Codex owns the frontend ones. **Never both.** Reviewing Builder's
output does not transfer ownership.

The split is not a preference. A Builder worktree is a git worktree and
`node_modules/` is gitignored, so it is absent, and the runner exposes a Python
toolchain but no Node one (`PACKET_STANDARD.md` F9, decision `D-007`). Builder
cannot run a single frontend test, so it must never be given frontend work — a
packet it cannot prove is a packet it will fail.

| Packet | Owner | Blocked on |
| --- | --- | --- |
| `KT-RESTORE-01` | builder | — (implementation succeeded 2026-08-31) |
| `KT-AUTO-01` | builder | — |
| `KT-DEADLINE-01` | builder | `KT-AUTO-01` |
| `KT-PRIVACY-01` | builder | — |
| `KT-TOOLBRIDGE-01` | builder | — |
| `KT-UI-MOUNT-01` | **codex** | — |
| `KT-BACKUP-UI-01` | **codex** | `KT-RESTORE-01` merged |
| `KT-CHAT-TOOLS-01` | **codex** | `KT-TOOLBRIDGE-01` merged |

Manifests: `docs/initiatives/kitty-finish-truth-20260831-v2.json` and
`docs/initiatives/kitty-jacob-decisions-20260831-v1.json`. The Codex packets
have no manifest on purpose.

## Start here, in this order

1. `KT-UI-MOUNT-01` — unblocked now, no dependency, two finished screens that
   nothing links to. Read its "not pure wiring" section first: monitors delete
   by an identifier the gateway does not return, and the only control that
   completes a todo is labelled `retry`.
2. `KT-BACKUP-UI-01` — the moment `KT-RESTORE-01` merges.
3. `KT-CHAT-TOOLS-01` — the moment `KT-TOOLBRIDGE-01` merges. Highest user
   value in the whole set, and the one with a real half-shipped hazard: a chat
   that sends tools but cannot run the calls that come back is worse than
   today, because the model will promise actions it never takes.

## Jacob's rulings — these are settled, do not reopen

Recorded as `D-015` on 2026-08-31, in his own words: *"kitty chat almost never
should need my okay for anything, asking for a private memory who cares give
them the info, and back up should get a real screen"*.

- **No permission prompts.** Approval survives for exactly four things:
  spending money, sending something to another person, deleting his data, and
  pushing or merging code. Everything else acts.
- **A directly requested private memory is simply given.**
- **Backup gets a real screen.**

Two of his standing rules govern every surface you touch:

- **Every surface is actionable in place.** A read-only card is a defect. If an
  item genuinely has no available action, it says so and says why.
- **Write to Jacob assuming he does not code.** Nothing you put on screen — an
  error, a count, a status — may require knowing what a channel, an endpoint,
  or an MCP server is.

## What tonight cost, so you do not pay it again

Builder had 167 attempts and 1 completion. Three infrastructure defects in a
chain, each hiding the next. All fixed and merged (#719, #720, #721). The
lessons that transfer:

1. **Re-verify every premise against real source before writing a line.** Of
   the findings handed to me, one was already fixed and thirteen review points
   against my own packets were all real. The worst would have turned a
   duplicate-copies bug into permanent deletion.
2. **A test written against the wrong shell, path, or interpreter sees nothing
   wrong.** One defect was invisible under `/bin/bash` and fatal under the
   Homebrew bash Builder actually resolves.
3. **Say what you observed and what you inferred.** One fix in #721 ships with
   a measured behaviour table and an explicit note that the kernel mechanism is
   *not* established. Do not repeat an explanation for it.

## Before you open a PR

- Run the narrowest tests that cover your change and report exact counts.
  `venv/bin/python3.12` is the interpreter; `python3.12` is not on the default
  PATH.
- Required checks are `policy-gate` and `merge-gate`, strict, so your branch
  must be up to date with `main`. Zero approving reviews are required, but
  **every review thread must be resolved** or the merge is blocked.
- Read the current rules with `gh api repos/:owner/:repo/rulesets` rather than
  trusting this paragraph; the check names have been restructured mid-session
  before.
- Never apply an approval or risk label to a PR you authored.
- Push and merge only with Jacob's authorization.

## Open, unowned, and deliberately deferred

- The Builder-runtime findings (`BLDR-B001` through `BLDR-B006`) were deferred
  during the prioritization pass because four PRs owned those files. Those PRs
  (#712, #713, #715, #716) were **closed unmerged** on 2026-08-31, so the fence
  is released and they can be picked up.
- `MEMCTX-B008` is **already fixed** in code; the finding record was stale.
  Do not packetize it.
- `LIB-B004` is an unproven inventory claim. Do not packetize it without a
  permitted data snapshot.
- Product decisions still open: `MEMCTX-B001`, `MEMCTX-B002`, `MEMCTX-B005`,
  `PROJ-B001`, `PROJ-B006`, `PROJ-B008`. Ask Jacob; do not engineer around them.
