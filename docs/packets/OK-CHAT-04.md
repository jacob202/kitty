# OK-CHAT-04 — Cross-Surface Continuity Acceptance

## Mission

Define and run the acceptance scenarios proving one Kitty object is recognizably the same everywhere: Project + Work + Deadline + Artifact continuity across Chat, Home, and Work/Projects, with Chat answering truthfully from current state.

This is a verification packet. It owns the scripted, reviewer-run scenario set for the Wave 2 acceptance bar; it is not an implementation packet beyond the minimal drivers it needs.

## Depends on

- `OK-CHAT-01/02` (concierge context projection wired into chat with bounded limits/provenance)
- `OK-CHAT-03` (typed objects rendered in chat)
- `OK-ACTION-01/02` (canonical contract + shared renderer)
- `OK-ACTION-03/04` scenario coverage where Home/Work migration has landed

## Product acceptance moment

Start Builder work in Chat, see the same work in Work and Home, finish it, open the resulting Artifact, attach it to a Project, then ask Chat about that Project — without copying IDs. Chat truthfully answers questions about at least Projects, Work, Artifacts, and Deadlines using current Kitty state, and at least one suggested action per domain invokes the real owning workflow.

## Constraints

- Acceptance runs execute against the live app with real gateway state; hermetic/mocked runs may support development but cannot satisfy this packet.
- No new source of truth; scenarios verify existing authorities only.
- Context passed to Chat uses the bounded explicit-context reference mechanism (durable refs, marker stripping, budget caps) — no full-history dumps, no raw packet IDs in user-visible flows.
- Errors explain what failed and what to do next; no raw server errors in any scenario.
- Scenarios run at desktop and phone viewports; no horizontal overflow.
- A reviewer who did not implement the change completes the scenario list and records the receipt.

## Target locations

- Scenario definitions and evidence: this packet plus the PR description it is run in.
- Minimal drivers, if needed: `gateway/kitty-chat/tests/` (playwright specs following the existing acceptance-spec pattern).
- No production code changes expected; any seam fix discovered by a scenario ships as its own small PR referencing this packet.

## Behavior — scenario set

Run and record each scenario with observed visible results:

1. **Project continuity.** The same project appears in Projects and Chat with the same name/status; "open project" from Chat lands on the canonical Projects destination; a suggested action on the project invokes a real owning workflow (e.g., next step).
2. **Work continuity.** Start/observe a work item via Chat; Work and Home show the same truthful status; finishing it updates all three surfaces on next view; no stale prose controls remain.
3. **Deadline continuity.** A deadline requiring attention appears in Home "Needs you" and is answerable from Chat; the suggested action opens the owning project or approval flow, not a dead end.
4. **Artifact continuity.** An artifact produced by work opens from Chat and Home to the same canonical destination; attaching it to a project succeeds through the owning route; Chat can reference it afterwards without copying IDs.
5. **Truthful answers.** Ask Chat one question per domain (Project, Work, Artifact, Deadline); each answer is consistent with current gateway state at answer time, and wrong/stale state is acknowledged rather than invented.

## Verification

- **Tier 1 — mechanical:** existing suites green (`python -m pytest`, kitty-chat vitest, typecheck, lint).
- **Tier 2 — running app:** the scenario drivers above pass at desktop + phone viewports with screenshots.
- **Tier 3 — product acceptance:** an independent reviewer executes the five scenarios in the running app and posts the receipt with exact heads and evidence.

## Non-goals

- New projections, stores, or backend routes.
- Home or Work migration work (covered by `OK-ACTION-03/04`).
- Concierge context capacity changes (`OK-CHAT-01/02` own limits).

## Done when

All five scenarios pass in the live app with an independent reviewer's receipt recorded, covering Project, Work, Deadline, and Artifact continuity plus truthful per-domain answers.
