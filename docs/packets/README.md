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

| # | Packet | Best executor | Status |
|---|---|---|---|
| 001 | State spine: signals, snapshots, /state/now | Claude Code / Codex | shipped (this PR) |
| 002 | Inbox triage | Codex / Claude Code | ready |
| 003 | Action queue with enforced tiers | Claude Code | ready — needs Jacob's tier sheet sign-off first |
| 004 | State home surface | Claude Code | spec-complete (§16.1 decided: console home) — blocked on 003 merge |
| 005 | Mail read-only connector | Codex/Claude Code + Jacob (credentials) | blocked on §16.2 decision |
| 006 | Project resume | Claude Code | blocked on 001 |
| 007 | Delegation packet generator | strongest model (template) + Codex (plumbing) | blocked on 003 |

Packets 004–007 are specified in `docs/OPERATOR_STRATEGY.md` §15; author
their packet files from that spec when their blockers clear.
