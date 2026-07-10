# KittyBuilder Orca Setup

KittyBuilder uses Orca as the outer worktree and agent coordinator while the local SQLite queue grows into the source of truth.

## Current Role Split

- **Orca** creates isolated worktrees, tracks task dispatch, carries worker messages, and exposes decision gates.
- **OpenCode** is the default implementation, planning, packaging, and cheap review lane.
- **Codex** is reserved for high-risk review or blocked escalation.
- **KittyBuilder queue** remains the future authoritative task state.
- **GitHub issue #127** is only a temporary bridge inbox.

## Setup Hook

Configure the Kitty repo setup hook in Orca to run:

```bash
./scripts/orca_worktree_setup.sh
```

The hook is intentionally read-only. It prints the current branch, dirty status, model routing rules, approval tiers, and the key files an agent should read before working.

## Approval Tiers

| Tier | Approver | Examples |
| --- | --- | --- |
| T0 | Automatic | read-only audits, task cards, formatting, local tests, PR descriptions |
| T1 | Separate model reviewer | normal scoped implementation, local commits, draft PR preparation |
| T2 | Jacob | push, merge, deletes, auth/secrets/env, paid or heavy dependencies, broad scope changes |

The implementer must not approve its own work. A model approval must be from a separate session or agent lane and should return a clear `APPROVE` or `BLOCK`.

## Provider Routing

Default to OpenCode first:

1. OpenCode cheap/free model for task cards, planning, packaging, and mechanical audits.
2. OpenCode stronger cheap coding model for implementation.
3. OpenCode reviewer for normal scoped review.
4. Codex Terra/Sol only for queue/state/concurrency/auth/destructive risk, or when OpenCode is blocked.

Cap silent provider retries quickly: one cheap attempt, one stronger attempt, then block or escalate. Do not loop through providers silently.

## Safe Build Train

Use this sequence for low-babysitting work:

1. Create an Orca worktree from `origin/main`.
2. Generate or paste one task card with allowed files, forbidden files, tests, and stop condition.
3. Dispatch OpenCode implementation.
4. Dispatch a separate OpenCode review gate.
5. Escalate to Codex only for high-risk safety review or repeated blocker.
6. Prepare PR text, but do not push or merge without the configured gate.

## Non-Goals

- No autonomous merge.
- No unattended paid-provider spending loop.
- No secrets or env edits from the setup hook.
- No worker spawning from the KittyBuilder queue until the queue CLI and runner gates exist.
