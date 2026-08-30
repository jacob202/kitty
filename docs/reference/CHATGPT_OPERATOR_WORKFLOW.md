# ChatGPT Operator Workflow

This document defines the low-cost operator path for Kitty. It complements
`AGENTS.md`; it does not replace repository or Builder authority.

## Default execution route

ChatGPT is the persistent Thread Master and first-line operator.

For Kitty work, prefer currently connected tools before escalating:

1. GitHub — remote repo, PRs, issues, checks, reviews, durable coordination.
2. Remote Desktop Commander — local Git, files, worktrees, commands, runtime.
3. Context7 — current dependency/framework documentation.
4. Web — current public facts that are not project-private.
5. Codex — specialist escalation when explicitly requested or when the task
   genuinely cannot be completed through the connected-tool route.

Do not reflexively hand Kitty work to Codex/Work merely because it involves
code. Limited Codex quota is a routing constraint, not a blocker to using the
connected tools available in ordinary ChatGPT.

## Context before NEXT

Before choosing the next action for an ongoing Kitty campaign, reconstruct the
smallest current state needed to make that decision. Do not infer the campaign
from the final message of the previous chat.
For substantive technical work, reconcile as needed:

- current GitHub `main`, open PRs, and required checks;
- local branch, HEAD, dirty paths, and worktrees through RDC;
- issue #490 for active ownership/collision markers;
- `docs/ACTIVE_MISSION.md` and the current context receipt;
- Builder durable status only when Builder ownership/execution matters.

If sources disagree, call out the contradiction and resolve it before mutation.
A tangent does not silently become the new campaign priority. Capture it, then
return to the active objective unless Jacob explicitly changes direction.

## Canonical checkout hygiene

The canonical checkout should be a stable observation/integration point, not the
default implementation workspace. Prefer isolated task worktrees for changes.

`ahead N` means local commits exist that are not on the compared remote ref.
`dirty` means tracked changes or untracked files are not committed. Neither is
proof of damage, but repeated local-only work on canonical `main` creates context
and recovery debt.

Before "cleaning" either condition, identify ownership and preserve the work.
Never reset, stash, delete, or overwrite merely to make status look clean.
## Thread Master checkpoint

GitHub issue #490 is the durable cross-chat Thread Master surface. ChatGPT
cannot append directly into a different ChatGPT conversation, so use #490 as
the shared state that any fresh chat or agent can recover.

After substantive Kitty work, and before the final user-facing response, append
one concise checkpoint to #490 when material state changed. Do not spam it for
pure discussion with no state change.

Use this shape:

```text
THREAD MASTER CHECKPOINT — <timestamp>
VERIFIED: <fresh durable facts>
CHANGED: <what this session changed>
CURRENT OBJECTIVE: <mission/campaign goal>
OWNERSHIP: <active lanes or none>
NEXT: <one highest-leverage action after context reconciliation>
BLOCKED: <real blockers, or none>
DO NOT REDO: <completed/preserved work that could be mistakenly repeated>
```

End the user-facing response with the compact state:

```text
DONE: ...
NEXT: ...
BLOCKED: ...
```

`NEXT` is not a continuation token. It is a recommendation derived from the
current objective plus fresh evidence.