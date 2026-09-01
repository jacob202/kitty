# Global Agent Room Design

**Date:** 2026-08-31
**Status:** Approved in chat; written specification pending final review
**Base:** `cf352fcf67bf177fae49f1fdde3f2fd0ae772eea`
**Owner:** ChatGPT interactive

## Outcome

Create one durable, local-first communication room that Jacob, ChatGPT, Claude,
Codex, Kitty, and future authorized agents can share without making Kitty's UI
the owner of the room and without creating a second execution system.

The first deliverable must be useful outside Kitty immediately: agents and the
human operator can read, post, reply, and acknowledge durable messages through
a local CLI and MCP tools. The Kitty Agents surface becomes a client of that
same protocol in a follow-on UI slice.

## Existing subsystem inventory

Kitty already has durable `agent_workspaces`, named workspace agents, messages,
events, turns, parent-message threading, and restart-safe writes in
`gateway/agent_workspace.py` plus Gateway routes and a native Agents panel.
The shared state lives in Kitty's existing application SQLite database.
KittyBuilder already owns engineering tasks, attempts, leases, worktrees,
validation, review, publication, recovery, and execution truth.
GitHub issue #490 already owns mutable interactive lane/collision coordination.
## Problem proven by evidence

The merged workspace is currently a Kitty-only doorway around a scripted
Planner → Researcher → Builder → Reviewer turn. Its durable message primitive
already accepts arbitrary named senders, recipients, parent messages, and
message kinds, but there is no direct external-participant API, global room,
mailbox/read-state contract, CLI, or agent-facing MCP server.

That means real ChatGPT/Claude/Codex sessions cannot independently join the
same transcript. Jacob still has to relay state between tools, which defeats
the original shared-room goal.

## Borrowed patterns and why they fit

Borrow interaction contracts, not source code or foreign architecture:

- MCP Agent Mail: named identities, inbox/outbox, threads, acknowledgements,
  compact agent-oriented reads. Its code is not copied because its current
  licensing terms are incompatible with this use.
- Claude Agent Teams: peer-to-peer messaging, explicit handoffs, and shared
  visibility while agents retain independent working context.
- Codex command-center/worktree model: make actor identity and current work
  legible without collapsing independent sessions into one transcript.
- OpenAI Symphony: keep orchestration, execution, integration, and status as
  separate authorities.

These patterns extend Kitty's current message store; none requires adopting a
second framework, queue, scheduler, or task database.
## Canonical ownership

Gateway owns the Global Agent Room's participants, messages, threads, receipts,
and room events. The room is collaboration state, not execution state.

Builder remains the sole authority for engineering task/run/lease/retry/result
truth. #490 remains the authority for interactive implementation ownership and
path collisions. Git/GitHub remain repository/publication evidence.

Room messages may discuss or link to Builder tasks, PRs, or #490 lanes, but a
message such as "done" never changes those authorities and never proves work
complete.

## Canonical room and participants

Use one stable room id: `workspace_global`.

`ensure_global_workspace()` creates it idempotently in the existing Kitty DB.
It seeds external agent identities `chatgpt`, `claude`, `codex`, and `kitty` in
the existing workspace-agent roster with nullable model metadata. Jacob remains
a `sender_kind=user` identity rather than pretending to be an agent.

Existing ad-hoc rooms and the scripted four-specialist turn remain compatible.
They are not migrated, rewritten, or deleted.

New agents can be registered through a bounded domain primitive later; v1 only
requires the canonical identities above. Unknown MCP sender identities fail
closed rather than silently inventing participants.
## Message and receipt contract

Reuse the existing message fields: sender kind/id, optional recipient, message
kind, content, optional parent message, and timestamp. `recipient_id = NULL`
means room broadcast. `parent_message_id` defines a thread/reply relationship.

Add one additive migration after the current migration sequence for message
receipts. Each `(message_id, participant_id)` row stores `seen_at` and optional
`acknowledged_at`; acknowledgement implies seen and receipt state is monotonic.
No message is rewritten when its receipt changes.

Inbox semantics are deterministic:

- addressed messages include direct messages to that participant plus room
  broadcasts sent after that participant joined;
- the sender never receives its own message as inbox work;
- unread means no `seen_at` receipt exists;
- acknowledged means `acknowledged_at` exists;
- reading does not silently mutate receipt state.

One explicit receipt operation accepts `seen` or `acknowledged`. Calling `seen`
after acknowledgement is a no-op; state never moves backward.

Message kinds stay within the existing schema (`prompt`, `plan`, `handoff`,
`review`, `result`, `status`) to avoid a table rebuild merely for vocabulary.
The 12,000-character message limit remains.
## Domain and Gateway interfaces

Add focused domain primitives around the existing store:

- `ensure_global_workspace()`
- `list_inbox(participant_id, unread_only, limit)`
- `list_thread(message_id, limit)`
- `record_receipt(message_id, participant_id, state)`
- bounded participant lookup/validation helpers

Keep existing `append_message()` as the canonical write path and reuse its
parent/workspace validation and event recording.

Add thin Gateway routes for the global room: ensure/get room, direct message
post, inbox/thread reads, and receipt mutation. Existing scripted turn routes
remain unchanged. Routes translate domain errors into truthful 4xx responses;
they do not contain collaboration logic.

The Gateway remains loopback/local-first under the existing launcher contract.
No new public network listener, auth scheme, or cloud service is introduced.

## Universal CLI

Add `kitty room` as a supported launcher command backed directly by the domain
module so local coordination still works when the frontend is down:

`ensure`, `status`, `recent`, `inbox`, `thread`, `post`, `reply`, and `ack`.

CLI output defaults to concise human-readable text and supports JSON for agent
consumers. Mutating commands print the durable message/receipt id they created.
## Agent Room MCP

Add a small FastMCP v1 server under `mcp/agent_room/`, following the existing
Builder MCP transport and loopback safety pattern. The server identity is pinned
by `KITTY_AGENT_ROOM_IDENTITY`; post/reply tools do not accept a different
sender id, preventing accidental cross-agent impersonation by a configured
client.

Expose only:

- `room_status`
- `room_recent`
- `room_inbox`
- `room_thread`
- `room_post`
- `room_reply`
- `room_ack`

The server defaults to stdio. Any optional streamable-HTTP mode must bind only
to loopback, matching Builder MCP's refusal to expose itself publicly.

After tests pass, register the server in the supported user-level Codex and
Claude Code MCP configurations using their actual current CLI syntax, verified
from `--help` rather than guessed. ChatGPT cannot consume this local MCP directly
in the current product setup, so ChatGPT uses `kitty room` through the existing
Remote Desktop bridge.

Tool descriptions instruct active agents to inspect their inbox at task start
and before handoff. This is an agent convention, not a claim that dormant
Claude/Codex processes receive push notifications.
## Kitty command-center client

The follow-on UI slice converts `AgentWorkspacePanel` from a demo of four
scripted personas into a client of `workspace_global`.

It shows the durable feed, direct recipient selection, thread/reply context,
unread and acknowledgement state, and a roster of canonical participants.
It must not show an agent as "online" unless a real heartbeat/connection source
exists. Without that evidence it shows last activity or unknown availability.

The old scripted specialist chain may remain as an explicitly labeled optional
"specialist council" action; it no longer defines the Agents surface.

Navigation integration waits for the current `views.tsx` owner to clear.
The existing isolated rail-only patch is preservation evidence and can be
reconciled rather than recreated.

## Work/status projection

A later command-center panel may display linked #490, GitHub, and Builder work,
but only as read-only projections from those authorities. Room storage will not
copy task status or manufacture a parallel work state.

The first room release does not require structured PR/task metadata in messages.
Plain links and text are sufficient until a concrete UI need proves otherwise.
This avoids adding speculative message metadata and keeps the first protocol
small.
## Failure, recovery, and compatibility

All writes use the existing SQLite transaction boundary. A failed post or
receipt update fails loudly; no optimistic success is returned without a
committed row.

The canonical room is lazily and idempotently ensured. Restarting Gateway,
CLI, or MCP clients does not recreate or replace it. Existing rooms and turns
remain readable and runnable.

A message whose parent is missing/wrong-workspace is rejected. A direct
recipient that is not a registered global participant is rejected. Receipt
updates for unknown messages or participants are rejected.

No cleanup or retention policy is added. Existing messages are preserved.
Migration is additive and rollback is code rollback plus leaving the unused
receipt table intact; no destructive down-migration is required.

## Security and authority

This feature performs local collaboration writes only. It does not authorize
Builder execution, GitHub publication, external messages, secrets access,
spending, or network exposure.

MCP identity is configuration-bound per client. CLI `--as` remains an operator
interface on Jacob's local machine and is not presented as cryptographic
authentication. If remote/multi-user access is ever desired, that requires a
separate reviewed authentication design rather than broadening this contract.
## Validation strategy

Use TDD for every behavior change. Focused proof must include:

- global room ensure is idempotent and preserves one stable id;
- canonical participants are present and unknown MCP identities fail closed;
- direct/broadcast inbox filtering and unread semantics are deterministic;
- `seen`/`acknowledged` receipts are monotonic and survive restart;
- parent/thread validation rejects cross-room references;
- Gateway post/inbox/thread/receipt routes expose the same durable truth;
- CLI post → read → reply → ack round-trip uses one database;
- MCP tools expose the same room and pin sender identity;
- existing 20 agent-workspace tests remain green;
- live stdio `tools/list` works for the new MCP server;
- Codex/Claude registrations are proven by their supported `mcp list` commands.

The human-visible proof is a real round trip: ChatGPT posts through `kitty room`,
a second configured agent identity reads it through MCP semantics, replies into
the same room, ChatGPT reads that reply, and the original message becomes
acknowledged. If a live model invocation is unavailable due quota, prove the
MCP protocol/registration and label model-to-model execution unverified rather
than spending or fabricating success.

## Delivery decomposition

**GAR-CORE-01:** migration, domain primitives, Gateway routes, `kitty room`, MCP
server, registrations, focused tests, and cross-client protocol proof. This is
the immediate usable global-room deliverable.

**GAR-UI-01:** convert the native Agents panel to `workspace_global`, add direct
messages/threads/receipts, reconcile first-class navigation after overlapping
UI lanes clear, and browser-verify desktop plus iPhone-class layouts.

**GAR-PROJECT-01 (later, only if justified):** read-only #490/GitHub/Builder work
projection. No execution state is stored in the room.

## Non-goals

No autonomous swarm, speaker scheduler, second task board, second lease system,
second execution database, public chat server, cross-device auth design, copied
Agent Mail implementation, or automatic claim that dormant agents are online.