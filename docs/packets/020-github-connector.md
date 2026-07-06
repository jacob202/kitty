# Packet 020 — GitHub read-only connector

- **Status:** 🧭 planned — needs an executor-ready authoring pass. This is
  the "P5b" from OPERATOR_STRATEGY §5.7 that never got its own packet:
  read-only GitHub state (PRs, check runs, review comments) as signals.
- **Best executor:** Codex / Claude Code — mechanical once 005 sets the
  connector pattern.
- **Purpose:** Jacob runs a multi-agent development operation on the kitty
  repo and Kitty can't see a PR, a failing check, or a review comment. The
  connector fixes the product's blindness to its owner's most active
  workspace, and it's what makes packet 016's B for code projects live
  ("PR #94 is green and waiting on merge" instead of stale git-log
  inference).

## Scope sketch (for the authoring pass)

- `gateway/connectors/github.py`, copying 005's shape exactly: cron-polled,
  token via env (`GITHUB_TOKEN`, classic PAT with `repo:read` — Jacob
  creates it, agents never handle credential issuance), deduped signal
  rows. Sources: open PRs + their check-run conclusions + new review
  comments on Jacob's repos (config list, kitty first).
- Signal payloads carry repo/PR/title/state/URL — never diff contents.
- Doctor check for connector health; poll failure is loud.
- Project resume (006) and navigator (016) consume the signals for code
  projects.

## Dependencies

- 005 merged first (it establishes `gateway/connectors/` and the pattern —
  §17.2). 015 optional for "PR went red" pushes.

## Acceptance sketch

- Mocked-transport tests prove signal shape + dedupe (same bar as 005).
- A failing check run on a watched repo becomes a signal within one poll.
- No write scope anywhere: the token permissions and the code both refuse
  (github.push / github.merge remain in the tier sheet's disabled list).

## Jacob reviews

- The repo watch-list and the PAT scopes (he creates the token himself).

## Too broad if

- It posts comments, merges, triggers workflows, or watches repos he
  doesn't own.
