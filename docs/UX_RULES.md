# Kitty UX Rules

The non-negotiable design disciplines for every surface, component, copy string,
and chat-routable action in Kitty. Adopting these is what stops the "nine panels
wearing the same CSS variables" problem. Adopted 2026-07-23 from
`docs/AUDIT_COMPANION_LAYER_HARVEST_2026-07-23.md` and from agent dogfooding on
the live UI.

## The rules

### 1. Chat IS the operating layer

Every action any surface offers must also be reachable from chat with one click.
Surfaces are workshops for sustained making; chat is the front door and the
remote control. **Reference:** HA Assist (chat overlay that controls the
dashboard), Open WebUI (chat-centered), Replit Agent (chat drives the work).

Forbidden: a control that lives only on a surface and is not also exposed in
chat. Forbidden: a chat feature that is not also surfaced as a card.

### 2. Decisions, not data

A surface shows a decision, not a dataset. The Builder pane should show *one*
"needs you" card with the actionable decision, not the full queue. The Home
should show the one next thing, not seven empty boxes. **Reference:** HA Repairs
(severity-sorted, action-ready cards).

Forbidden: an empty dashboard tile. If a section has nothing to say, it
should not exist on the page. If the section can have nothing, the empty
state must be one warm line — not "data" with zero rows.

### 3. One component, many shapes

Repairs, Signals, Experts (Home strip), Deadline cards, and any future
"thing with severity + status + action" all render with the same primitive.
The shape varies by data; the component does not. **Reference:** HA entities
(uniform renderer over heterogeneous data), Langfuse scorecards (uniform
card over heterogeneous signals).

Forbidden: a per-feature card style. If you find yourself designing a new card
component, the right answer is probably to extend the existing one with a
new data shape.

### 4. Plain English on every card

No user-facing title is a string from the backend. Every title is
`{ title_key, placeholders }` resolved through a small catalog. Placeholder
values are truncated to 80 characters before rendering. The full value lives
on the card and expands on click. **Reference:** OpenHands
`get-event-content.tsx` (`ACTION_MESSAGE$READ` etc.).

Forbidden: titles like "attempt 2 · scope failure". Required: "the worker
tried to touch files it wasn't allowed to — see what changed." Forbidden:
titles like `partial data`. Required: "Three packets need your attention.
Pick one to decide."

### 5. No "read-only" surfaces in a one-user product

A surface exists to do something. If it has no actions, fold it into chat
or delete it. **Reference:** HA Repairs (every card is either actionable
or informational, never both-and-also-pointless).

Forbidden: a pane whose only purpose is to display status.

### 6. No CLI in user-facing copy

User-facing text never contains `./kitty`, `POST /`, `curl`, or filesystem
paths. Backend errors surface as plain-English sentences. When an action is
unavailable in the UI, the message is "this isn't wired up yet — say
'kitty, add it'" not "POST /v1/repairs". **Enforced by:** a snapshot test
that fails the build if forbidden tokens appear in any user-rendered
string.

Forbidden: telling a non-coder to run a CLI command.

## The five cross-cutting disciplines

These are habits that come from problems the harvest repos already solved.
Adopt them in code review.

### Exactly-once tool execution

When the model streams tool args, the UI must guarantee that the host's
`streamCall` / `execute` callback fires exactly once per `toolCallId`,
regardless of how the snapshot mutates. No double side effects. No
re-execution on rollback or branch switch. **Reference:** assistant-ui
EDGE_CASES §A–F. **Maps to:** KX-02-01.

### Never throw in the hot path

Every observer wraps in try/catch and logs to `console.error`. A malformed
snapshot, a network blip, an unexpected response — none of them crash the
runtime. **Reference:** assistant-ui EDGE_CASES preface.

### Pre-flight correction

When the model emits a shell command or tool arg that will fail, fix it
before it runs. Surface the fix as a warning, not a silent rewrite. The
runner returns `{ shouldModify, modifiedCommand, warning }`. **Reference:**
bolt.diy `action-runner.ts#validateShellCommand`. **Maps to:** KX-05-03.

### Discriminated union for state

`'cancelled'` and `'failed'` are different *kinds* of terminal state; the
reducer must not confuse them. Use a tagged union, not a string field with
magic values. **Reference:** bolt.diy `ActionStatus`. **Fixes the**
"cancelled counts as needs attention" bug in KX-05-03.

### Group by source, not by chunk

Citations, repairs, signals, expert answers — anything that comes from
multiple sources is grouped by source (doc title, domain, book name) with
chunks underneath. **Reference:** anything-llm `Citation/`.

## Tier rule (Jacob 2026-07-23)

> "i dont like approving things. i like it just to get done."

All chat-routable actions in Kitty run at **T0** (auto-execute, every
execution recorded). New action kinds are added to
`config/action_tiers.json` at T0; the gateway picks them up on restart.
The action_queue tier framework Jacob signed off on handles the gating.
Per-action approval is not used.

The only exception: destructive or paid actions (e.g. `git push` to a
remote, sending an email, charging a credit card) remain at **T2** with
explicit approval. KX manifests should declare each new action kind's
tier.

## Layout rule (Jacob 2026-07-23)

The Builder pane renders attention-first by default — one "needs you"
card, the actionable decision cards for any paused or needs_decision
items, and a single "see all initiatives" link. Operability over
completeness. The full initiative grid is one click away.

## Import staging rule (Jacob 2026-07-23)

Approved items from any user-facing import flow (onboarding chat-import,
expert bookshelf sync, future sources) go to the staging table with
`user_review='approved'` (conservative staging). They become queryable
in chat in subsequent turns. No direct memory write. Skipped items
carry `user_review='skipped'` and are not re-offered.