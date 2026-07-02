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

**Updated:** 2026-07-02

| #   | Packet                                                        | Best executor                                 | Status                                                         |
| --- | ------------------------------------------------------------- | --------------------------------------------- | -------------------------------------------------------------- |
| 001 | State spine: signals, snapshots, /state/now                   | Claude Code / Codex                           | ✓ shipped                                                      |
| 002 | Inbox triage                                                  | Codex / Claude Code                           | ✓ shipped                                                      |
| 003 | Action queue with enforced tiers                              | Claude Code                                   | ✓ shipped (#65 + #67)                                          |
| 004 | State home surface                                            | Claude Code                                   | 📋 spec-complete (§16.1: console home) — **unblocked**         |
| 005 | Mail read-only connector                                      | Codex/Claude Code + Jacob (credentials)       | ⛔ blocked on Jacob's §16.2 decision (Apple Mail vs Gmail API) |
| 006 | Project resume                                                | Claude Code                                   | ✓ shipped (#71)                                                |
| 007 | Delegation packet generator                                   | strongest model (template) + Codex (plumbing) | ✏️ **unblocked** (003 + 012 shipped)                           |
| 008 | Knowledge library + expert retrieval                          | Claude Code / Codex                           | ◐ routes shipped (#73); expert retrieval remainder open        |
| 009 | De-fake loops/insights (backend routes)                       | Claude Code                                   | ✓ shipped (#75)                                                |
| 010 | Capture-to-knowledge (file/PDF/screenshot → inbox → pipeline) | Claude Code                                   | ✓ shipped (#74)                                                |
| 011 | Brief v2 + push delivery (state-diff open + scheduler)        | Claude Code                                   | ✓ shipped (#76)                                                |
| 012 | Privacy boundary in router (§17.3)                            | Claude Code                                   | ✓ shipped (#72)                                                |
| 013 | Nudges + web_monitor → signal emitters                        | Claude Code                                   | ✓ shipped (#77)                                                |

Packets 004–007 are specified in `docs/OPERATOR_STRATEGY.md` §15; author their packet files from that spec when ready. Packets 009–013 were identified in a 2026-07-02 codebase audit; see `docs/AGENT_HANDOFF.md` for rationale.

**Priority note:** Packet 012 (privacy boundary) should land before 005 and 007 — mail bodies and journal entries will flow to cloud models once drafting or delegation ships, and the routing boundary must be enforced first.
