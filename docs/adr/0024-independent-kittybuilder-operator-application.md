# ADR 0024: KittyBuilder Has an Independent Operator Application

**Status:** Accepted
**Date:** 2026-08-01
**Decision owner:** Jacob
**Amends:** ADR 0017
**Supersedes:** only the KB-BRAIN-04 requirement that Builder be a navigation mode inside the normal Kitty frontend

## Context

ADR 0017 correctly assigns intent and Mission authorship to Kitty and execution truth to KittyBuilder. The remaining product question is where Builder's engineering control surface lives.

PR #287 merged Builder execution into Kitty's normal Work surface. That made personal tasks and engineering operations share one shell, exposed Builder concepts where they did not belong, and made the repair surface dependent on the product it may need to diagnose. The `kittybuilder-brain-v1` manifest later encoded this drift as an acceptance criterion: Builder must be a distinct Kitty navigation mode and not a separate application.

KittyBuilder already owns durable initiatives, packets, attempts, leases, branches, worktrees, validation, review, recovery, publication evidence, operator actions, and budget receipts. The missing work is a reliable projection and operator experience over those authorities, not another queue, database, workflow engine, or agent manager.

OpenHands Agent Canvas is a plausible UI foundation, but it is a beta product with its own Agent Server assumptions. Reuse must therefore be proven behind an adapter rather than adopted as Builder authority.

## Decision

KittyBuilder will have an independent operator application with these boundaries:

1. **Same monorepo and release discipline.** The operator application remains in `jacob202/kitty` and follows the same review, evidence, and dependency policies.
2. **Same authoritative Builder backend.** It reads and acts only through versioned KittyBuilder APIs. It must not read SQLite directly, infer completion from frontend state, or introduce a second event store.
3. **Separate frontend package, build, process, and URL/port.** It is not a route or navigation mode inside `gateway/kitty-chat`.
4. **Independent failure domain.** The operator application must still open and display Builder truth when the normal Kitty frontend is stopped, fails to build, or serves an error page.
5. **CLI repair floor.** Existing `./kitty builder ...` commands remain the lowest-level emergency and automation surface when either frontend is unavailable.
6. **Narrow integration into normal Kitty.** Kitty may show a compact status such as “Builder needs two decisions” and deep-link to the operator application. Normal Kitty must not expose packet dumps, leases, worktrees, provider internals, budget ledgers, or KTF terminology as ordinary Work content.
7. **Decision Inbox first.** The cockpit home is a plain-language list of approvals, blockers, failed checks, merge conflicts, exhausted budgets, and recovery actions. A raw queue dashboard is secondary.
8. **One canonical projection.** Runtime snapshot, event stream, commands, evidence bundles, and spend data are derived from existing Builder authorities with provenance and explicit stale/missing states.
9. **Generated client contract.** Builder API schemas are versioned and generate the frontend client. Hand-maintained duplicate request/response types are not accepted.
10. **Standard run evidence bundle.** Every inspectable run links the Mission revision, initiative/packet/attempt identities, exact base and head SHAs, branch/worktree, normalized events, commands, changed paths, validation, review, PR/check state, artifacts, costs when known, decisions, and explicit evidence gaps.

## Agent Canvas foundation spike

No Agent Canvas dependency is authorized merely by this ADR. After Builder B1 reconstructs the live execution path, a bounded spike must compare:

1. embedding exported Agent Canvas UI/components behind a KittyBuilder adapter;
2. a thin frontend fork with OpenHands-specific cloud, automation, and backend authority removed; and
3. a native KittyBuilder frontend using Agent Canvas only as a pattern reference.

The spike must pin the evaluated version or commit and measure:

- which conversation, terminal, browser, file, diff, and responsive components can be used without Agent Server ownership;
- adapter surface area and number of patched upstream files;
- bundle/install cost, build time, runtime memory, and accessibility regressions;
- ability to render a recorded KittyBuilder snapshot and event fixture with no OpenHands backend running;
- upgrade burden across one upstream version change;
- license and notice obligations;
- what existing Kitty code or planned work the dependency replaces.

**Kill rule:** reject the dependency if it requires OpenHands' workflow/agent server to become authoritative, requires a long-lived fork with invasive patches, cannot render from Builder-owned fixtures, or saves less work than the maintenance it introduces.

## Sequencing

- Builder B1 remains first and blocks B2–B10.
- B2/B3 establish the canonical snapshot and replayable event stream.
- The Agent Canvas spike may begin only after B1 and may not change Builder authority.
- Operator controls use canonical Builder commands with actor, reason, expected version, and auditable result.
- Conversational Builder work belongs in this operator application after the deterministic B2–B10 path is proven.
- This ADR does not authorize feature implementation while higher-priority active roadmap work or the repository's one-lane policy forbids it.

## Acceptance

The boundary is not complete until an automated or scripted acceptance test proves all of the following:

1. start the Builder backend and operator application;
2. deliberately stop or break `kitty-chat`;
3. open the Builder URL through `./kitty builder open` or its documented equivalent;
4. see the same active, blocked, allowed-next, and prohibited state reported by the Builder CLI/API;
5. inspect one run evidence bundle and one required decision;
6. take a bounded operator action through a canonical Builder command;
7. observe requested, succeeded/failed, and resulting-state evidence without local optimistic success;
8. recover through the CLI if the operator application is also stopped.

A screenshot of a cockpit shell, a mock queue, or a frontend using fixture state without the cross-process failure test does not satisfy this ADR.

## Consequences

- Kitty's normal product becomes simpler and less contaminated by engineering machinery.
- Builder gains a repair surface that does not share the failure domain of `kitty-chat`.
- A second frontend package and process add build and launcher work, but no second control plane is permitted.
- Reusable third-party UI may be adopted aggressively at the edge, while Mission ownership, queue state, attempts, leases, evidence, budgets, approvals, and publication authority remain Kitty-owned.
- KB-BRAIN-04 and all later cockpit packets must be revised before execution so their allowed paths, validation commands, and acceptance criteria match this decision.
