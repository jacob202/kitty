# STATE — Kitty

> Live packet coordination. Read before picking up work. Update when claiming or finishing.

## Goal

Execute open implementation packets without duplicate agent work.

## Branch

main

## Session

- 2026-07-04 — opencode session claiming **005** + **007**. Order:
  005 first (per registry), then 007. Each on its own worktree off
  `origin/main`. This row exists so other agents can see the claim
  before they pick the same packet.

## Packet claims

| Packet        | Claimed by          | Status                         |
| ------------- | ------------------- | ------------------------------ |
| 005           | opencode 2026-07-04 | 🚧 in progress (worktree soon) |
| 007           | opencode 2026-07-04 | 🚧 in progress (after 005)     |
| 008-remainder | —                   | available                      |

**Rule for other agents:** if the status above is anything other than
`available`, the packet is taken. Pick another. If you need to release a
claim, edit this row to `available` and commit to `main`.

## Done this session

## In flight

- 005 — implementing `gateway/connectors/mail.py`, cron registration,
  doctor check, mocked-transport tests. No code yet on disk.

## Blocked on Jacob

- 005 live verification needs Gmail OAuth setup. Per packet, the PR
  merges on mocked-transport tests; live poll is post-merge on Jacob's
  machine.

## Next actions

1. Create worktree `feat/packet-005-mail-connector` off `origin/main`.
2. Implement 005.
3. Push branch + open PR.
4. Merge, then mark 005 shipped in registry (chore commit on main).
5. Repeat steps 1–4 for 007.
6. Write `.claude/HANDOFF.md` end-of-session.
