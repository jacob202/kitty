# OK-HOME-01 — Home Action Board

## Mission

Turn Home into a prioritized action surface where every prominent item has a clear reason to exist and a real next action.

## Hard dependency

Do not implement against the pre-WOW Home. Base on the accepted/integrated state containing the selective personal-intelligence work (`feat/wow-personal-intelligence-20260831` or its merged equivalent) and the shared Action Grammar from `OK-ACTION-01/02`.

## Product acceptance moment

Open Home and, without scrolling through unrelated sections, see:

1. the best thing to continue;
2. things that genuinely need the user;
3. today/upcoming commitments;
4. meaningful active work;
5. at most one high-value Kitty insight/connection.

Every primary control either performs a real action, starts a real workflow, or opens the canonical destination.

## Default hierarchy

### Continue
Exactly one primary continuation when there is a strong candidate.

Candidate sources may include:
- active Project resume/next step;
- interrupted recent Chat/workflow;
- Work waiting at a meaningful resumable point;
- recent Artifact with an unfinished associated task.

Do not manufacture a continuation when ranking confidence is weak.

### Needs you
Only unresolved items where user input/action is required:
- approval;
- blocked/failed work requiring a decision;
- deadline with a useful planning action;
- explicit ActionQueue proposal;
- other authoritative waiting-for-user states.

Resolving the underlying object should remove/update the item automatically.

### Today / Upcoming
Prioritized deadlines/commitments. Every card must expose a meaningful action such as Plan, Open project, Ask Kitty, or the domain-specific canonical action.

### Active
Running work worth monitoring. Avoid turning Home into the Activity Center; show only high-value entries with canonical `Open work`/`View` actions.

### Kitty noticed
At most one selective intelligence/connection item by default. Reuse the WOW personal-intelligence projection. This slot is for a genuinely useful relationship/continuation, not a feed of insights.

## Demotion / removal rules

Move below first-screen priority or behind disclosure:
- routine system health when healthy;
- passive state changes;
- provider/debug information;
- full Builder cockpit data;
- generic counts;
- duplicated Project/Work summaries;
- cards whose only action is “read more” when nothing requires attention.

Do not delete truthful degraded-state reporting when it affects user capability; surface it concisely when material.

## Action semantics

Consume `OK-ACTION-02` shared action rendering. Home must not recreate domain-specific mutation handlers for migrated objects.

Each first-screen item must answer in code/data:
- `why_now`
- canonical object reference
- primary action
- optional secondary actions
- truth state/source health

These fields may be derived in a projection rather than stored.

## Ranking

Prefer deterministic rules over a new ML ranking system.

Suggested ordering factors:
1. waiting for explicit user decision;
2. deadline proximity/severity;
3. active Project relevance;
4. resumability/continuation confidence;
5. active work state;
6. recency;
7. intelligence score only after actionable state.

Document ties and fallback behavior.

## Existing areas to inspect

- `HomeState.tsx`
- `HomeView.tsx`
- WOW `HomeIntelligence.tsx`
- next-step / `whats next` projections
- `NeedsJacob`
- ActionQueue
- deadlines
- Activity projection
- Builder glance
- repairs/signals
- Project projections

Reuse sources; do not create `home_items` as a second durable store.

## Visual composition

- avoid equal-weight card grid;
- one bounded desktop canvas;
- one-column phone flow;
- use whitespace/list hierarchy before borders;
- one dominant first action, not many accent buttons;
- stable skeleton geometry;
- 44px minimum touch targets;
- body copy remains readable 15–16px where appropriate;
- no tiny monospaced metadata in primary hierarchy.

## Tests

Prove:
- `Needs you` outranks passive context;
- successful resolution of an underlying action removes/updates its Home item after refetch;
- failed source does not become empty truth;
- at most one default `Kitty noticed` item;
- no actionless first-screen card in populated fixture;
- mobile composition has no document-level horizontal overflow in acceptance harness;
- Home still renders useful partial state when one source is degraded.

## Non-goals

- New dashboard analytics.
- New notification store.
- Full Activity feed.
- System/provider console.
- Brand illustration rollout (separate packet/wave).

## Done when

Home functions as an action board in running-product acceptance: the first screen is prioritized, sparse, actionable, truthful, and every primary control has a verified outcome.
