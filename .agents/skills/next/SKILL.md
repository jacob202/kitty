---
name: next
description: "Continue the current interactive Claude Code, OpenCode, Codex, or other repo-aware assignment from its valid checkpoint. USE WHEN the user gives a bare continuation such as: next, continue, resume, keep going, or do the next thing."
---

# Next — Continue This Interactive Assignment

A bare `next` continues the assignment owned by the current interactive session.
It is not a command to drain KittyBuilder's queue, apply an initiative, claim a
packet, or choose unrelated work.

KittyBuilder is a separate autonomous execution control plane. It should already
be progressing through approved work under its own scheduler, workers, leases,
and evidence rules. Claude Code, OpenCode, Codex, and similar sessions are
interactive engineering workspaces unless Builder explicitly launched them as a
packet worker.

## 0. Establish the execution owner

Every implementation task has exactly one execution owner:

```text
interactive | builder
```

Use `builder` only when at least one of these is true:

- KittyBuilder launched this process and supplied a valid packet/task bundle;
- the user explicitly said `builder next`, `take the next Builder packet`, or
  named a Builder task/initiative/packet;
- a supported Builder transfer record assigns the packet to this tool and the
  live lease agrees.

Otherwise the owner is `interactive`. Merely being able to run Builder commands
does not make an interactive session a Builder worker.

Never let both lanes own the same implementation. An interactive session may
inspect or review Builder output without taking execution ownership.

## 1. Verify the current interactive checkpoint

Run the normal bootloader from `START_HERE.md`. Discover continuity first:

```bash
git status --short --branch
./kitty room inbox --as <identity> --unread --json
# If the assignment or handoff gives a durable locator:
./kitty room thread <message_id> --json
```

Prefer the Agent Room MCP equivalents when configured. An unread direct handoff
or a known `room_thread` message id is a deterministic continuation locator.
Use `room_recent` only for bounded shared situational context; the newest global
window is not an assignment index.

Then choose exactly one receipt mode:

```bash
# GAR has an unread handoff or known durable thread for this assignment:
./kitty context --agent --skip-legacy-continuity

# GAR has no locator and legacy checkpoint fallback is required, OR GAR is unavailable:
./kitty context --agent
```

Never use a legacy fallback after a legacy-skipping receipt alone. The strict
receipt must validate `.claude/STATE.md` and `.claude/HANDOFF.md` before either
file can supply the assignment. If the room itself is unavailable, report that
explicitly. `bash scripts/session_end_survey.sh` may be used for collision and
field awareness, but it does not replace strict checkpoint validation.

Inspect open PRs, worktrees, and Builder's read-only projection to detect
collisions—not to find new work for this session. A failed or unavailable source
stays failed or unavailable. Do not convert it into an empty queue, clean state,
or permission to improvise.

## 2. Resolve what `next` means

Continue in this order:

1. the explicit assignment in the current conversation;
2. an unread direct `workspace_global` handoff or known durable room thread for
   this interactive assignment;
3. a strict-receipt-validated non-terminal legacy compatibility checkpoint
   owned by this interactive tool/session when no durable room locator exists;
4. the current branch's documented next action when it still matches live state;
5. a concrete recovery or review action for this interactive assignment;
6. an explicit no-op explaining that no valid interactive assignment exists.

Do not silently substitute:

- the highest-priority Builder packet;
- a roadmap item that has not been assigned to this session;
- an unowned workflow-learning signal;
- another worker's branch, worktree, lease, or PR;
- whatever looks interesting in the repository.

When no valid interactive assignment exists, stop and say that `next` has
nothing to continue. Do not manufacture a task merely to avoid asking Jacob for
a new assignment.

## 3. Builder is inspected, not consumed

For collision and status awareness, supported read-only Builder commands may be
used when relevant:

```bash
./kitty builder initiative list --json
./kitty builder initiative status <initiative-id> --json
./kitty builder queue status --json
```

A bare `next` must not:

- apply `docs/initiatives/ktl-001-leverage-and-learning-v1.json` or any manifest;
- claim, release, cancel, grant, archive, or execute a Builder task;
- run `initiative run-packet`;
- alter Builder scheduling or provider policy;
- turn KB observations into queue work.

Those actions require an explicit Builder instruction or a valid Builder-owned
worker bundle.

## 4. Continue the interactive assignment end to end

For the resolved interactive task:

1. re-check scope, authority, and collisions;
2. gather the minimum relevant context;
3. perform the requested investigation, implementation, review, or recovery;
4. run the narrowest meaningful verification;
5. preserve exact evidence and limitations;
6. avoid touching files owned by active parallel work;
7. preserve initiative without lane theft by following the canonical adjacent-work policy in `docs/reference/MULTI_AGENT_COORDINATION.md#adjacent-findings-and-initiative`: read-only adjacent investigation/capture is encouraged; adjacent mutation requires collision reconciliation plus durable `OWN`/`INTEGRATE` ownership before editing; KX `CONFLICT` means handoff; and security/data-loss/P0 urgency never self-bypasses ownership;
8. stop at any required human, security, money, secret, or destructive gate.

Exploration is never a scope violation. Silent lane-switching is.

The same agent never treats its own implementation as independent approval.
Review-only sessions must not quietly become implementation owners unless Jacob
explicitly transfers ownership.

## 5. Close the continuation honestly

When this bounded continuation reaches an honest complete, blocked,
awaiting-review, failed, cancelled, or no-op state, run
`.agents/skills/session-end/SKILL.md` when the session is actually ending or the
user requested a complete continuation cycle.

Session-end records the execution owner, KB effectiveness receipt, evidence,
continuity, and workflow signals. It does not claim Builder work or schedule the
next Builder packet.

Then stop. A bare `next` continues one interactive assignment; it does not begin
a second assignment or drain any queue.

## Explicit Builder commands

These are intentionally different user intents:

- `builder status` — inspect Builder without taking work;
- `builder next` / `take the next Builder packet` — use Builder's governed
  selection and execution workflow;
- `review builder` — independently review Builder output without becoming its
  implementation owner;
- `next` — continue this interactive assignment only.
