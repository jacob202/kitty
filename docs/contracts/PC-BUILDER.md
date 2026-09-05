# PC-BUILDER

## Intended outcome
A person can ask Kitty in ordinary language for one bounded piece of Builder work and complete the whole journey without knowing packet IDs, YAML, repository internals, ports, environment variables, or terminal commands. Kitty turns the request into an understandable bounded proposal, lets the person edit or approve it, truthfully shows the selected model/provider and estimated/actual spend, shows queue/owner/running/blocked/next state while work proceeds, supports intervention and recovery, and exposes the actual resulting change or artifact.

## Starting condition
The exact current Kitty candidate is running with Gateway, LiteLLM, and the native UI healthy. The acceptance run uses a verified isolated app-data root that does not expose or mutate Jacob's canonical app data. The person starts from Kitty's normal Home, Chat, or Work surface on desktop or an iPhone-class viewport.

## Successful ending
The requested bounded work has either completed or truthfully ended in a recoverable failure state. For a successful run, the user can inspect the real result from Kitty and can see what request was approved, what ran, who/what owns it, which model/provider actually executed it, what it cost, and that the visible final state matches runtime truth. Reload or restart does not erase or misstate the outcome.

## Unacceptable workarounds
The user must not need a terminal, Builder CLI, packet ID, direct database access, repository knowledge, manual JSON/YAML editing, hidden endpoint calls, or a second product surface to create, approve, monitor, recover, or inspect the work. A green test, queued internal job, merged PR, or agent `DONE` report is not a substitute for the visible user outcome.

## Degraded behavior
If a provider, scheduler, model, network dependency, or Builder execution step is unavailable, Kitty preserves the user's request and approved scope, says what is unavailable in user language, distinguishes blocked from failed or queued state, avoids claiming work ran when it did not, and does not spend or mutate silently. The user can still inspect the request and current truthful state.

## Recovery behavior
From the failed or blocked state, the user can retry, choose an available permitted route when routing is the problem, revise or cancel the bounded proposal when scope is the problem, or resume after the dependency recovers without recreating the request from scratch. Recovery does not duplicate execution or lose the audit trail, and the visible state updates to the real current state.

## Acceptance evidence
Acceptance requires the exact running candidate with its SHA/build identity recorded; no stubs or network interception for the behavior under test; a verified isolated data root with no canonical-data leakage; one real ordinary-language request carried through proposal, edit/approve, routing/cost display, queue/owner/progress, recovery/intervention, and inspection of the actual result; desktop and iPhone-class completion; reload/restart continuity; and captured evidence that visible state agrees with Builder/runtime truth. Any reproduced failure in this journey is a PC-BUILDER defect and can reopen acceptance.