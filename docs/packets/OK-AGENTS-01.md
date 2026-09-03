# OK-AGENTS-01 — Agents and the Global Agent Room Are a Usable Coordination Surface

**Status:** draft candidate; not activated
**Roadmap phase:** 3 — companion completion

## Mission
Finish the Agents experience as a durable human/agent communication surface while preserving the hard boundary that GAR is not the execution queue and registered agents are not presumed online.

## Depends on
- Current `workspace_global` GAR API/CLI semantics.
- `KH-CONT-01/02` where assignment-scoped continuity/writer retirement affects the UI.
- Builder remains execution/task/lease authority; issue #490 remains interactive ownership/collision authority.

## Product acceptance moment
Open Agents, read current relevant conversation, send a broadcast or direct message, reply in-thread, acknowledge an addressed message, follow a durable task/result reference, reload, and continue without localStorage room recreation or fake online/completed state.

## Required behavior
- `workspace_global` opens as the normal room; no duplicate room state machine.
- Message, direct recipient, parent/thread, acknowledgement and unread semantics match Gateway truth.
- ACK means received, never task completed.
- Registered agent identity is not presented as online/present unless a separate real signal exists.
- Task/run/result references deep-link to the owning Work/Builder/product destination when available.
- GAR does not create/claim/complete Builder tasks.
- Transient room failure preserves previously loaded context and shows a recoverable unavailable state.
- Mobile composition supports reading/replying without obscured composer/actions.

## Verification
**Tier 1:** agent-room gateway/client/component tests for direct/broadcast/reply/ack/unread and no fake presence/completion semantics.

**Tier 2:** desktop + iPhone-class running app: read → direct post → reply → ack → reload; one Gateway unavailable/recovery path.

**Tier 3:** independent reviewer confirms the same durable message/thread survives reload and that no execution state is inferred from GAR prose.

## Non-goals
- Presence/chat-status invention.
- A second task board or queue.
- Replacing Builder or issue #490 ownership semantics.

## Done when
Agents is a dependable coordination room that reduces manual relay without becoming another source of execution truth.
