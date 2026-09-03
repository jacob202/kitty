# Outcome-First Product Delivery Design

**Date:** 2026-09-03
**Status:** approved design direction
**Purpose:** stop Kitty work from being declared complete when implementation exists but the intended user outcome still cannot be completed in the running product.

## Problem

Kitty repeatedly produces technically valid partial implementations that satisfy narrow packet text, tests, and reviewer expectations while failing the original user request.

The recurring failure chain is:

1. Product intent is translated into implementation-sized tasks.
2. Agents optimize against the task text rather than the user outcome.
3. Tests prove components, endpoints, or isolated controls.
4. Review inherits the implementer's framing.
5. A PR is merged and described as complete.
6. Real dogfooding later reveals the intended workflow is incomplete, confusing, inert, stale, or misleading.
7. A later audit rediscovers the same unmet requirement under a new finding ID.

The system therefore needs an authority above individual packets: durable product contracts plus end-to-end acceptance that preserve the original intent.
## Prime delivery rule

> Implementation is not the deliverable. The intended task being successfully completed in the running Kitty is the deliverable.

A feature is not done because a route exists, a control renders, a unit test passes, or an agent reviewer approves a diff. It is done only when the relevant product contract is proven in the exact candidate running product.

## Product contracts

Each primary surface gets a concise non-negotiable contract describing what the user must be able to accomplish without internal knowledge.

Examples:

- **Builder / Work:** describe desired work in ordinary language; understand the proposed work; change or approve it; see the actual model/provider and estimated/actual spend; understand the queue, provenance, ownership, running/blocked/next state; intervene and recover; inspect the result; never require packet IDs, CLI syntax, YAML, or a terminal for the normal lifecycle.
- **Image Lab:** add or select source/character material; describe identity and desired output; understand route/cost before spend; generate; see why a generation cannot run; recover; compare/refine; retain identity/provenance/result truth.
- **Library:** know why an item exists, where it came from, whether it is saved/indexing/indexed/failed, manage unwanted content safely, find uploaded material later, and use canonical references in Chat or Projects.
- **Projects:** show only meaningful project objects; make lifecycle/staleness explicit; archive/manage obsolete records; answer where the user left off and what to do next; preserve identity across related surfaces.
- **Automations:** create, edit, enable, run, inspect delivery/history, understand failure, retry safely, and survive restart without duplicate effects.## Delivery gates

### Gate 0 — Product Contract Authority
Before implementation, define the exact user outcome, starting state, success state, prohibited workarounds, degraded behavior, and recovery behavior. Every implementation packet must name its parent contract.

### Gate 1 — Product Truth Cleanup
Repair corrupt, stale, synthetic, misleading, or ambiguous underlying state before polishing its presentation. A better UI over untrustworthy data is not progress.

### Gate 2 — Critical User Loops
Implement vertically from intent through durable result. Prefer one complete usable workflow over several partially connected subsystems.

### Gate 3 — Cross-Cutting Reliability
Repair shared state ownership, performance, error semantics, provenance, accessibility, persistence, and common primitives only where they strengthen proven product loops.

### Gate 4 — Capability Unlocks
Expose hidden backend capability only when it improves an existing decision or workflow. Existing endpoints do not justify new cards or navigation by themselves.

### Gate 5 — Ruthless Product Acceptance
Dogfood the exact candidate on the running application. Every material finding terminates in FIX, DELETE, explicit PARK with reason, or REJECT.

## Anti-half-ass requirement

Every implementation packet must state how an implementation could technically satisfy its local requirements while still failing the product contract. Reviewers must actively test those failure modes.

Examples include: a rendered button whose action is inert; a successful HTTP response whose outcome is not durable; a Builder inspector that exposes internals but cannot originate normal-language work; an Image Lab character record with no usable descriptor workflow; a Library inventory that faithfully renders acceptance-test debris; or a Projects page that accurately displays stale records that should no longer be active.

## Acceptance authority

Independent product acceptance starts from the user outcome, not the diff. The reviewer receives the product contract and a running candidate first. Implementation details are inspected only after the task has been attempted as a user.

For primary workflows, acceptance must cover desktop and iPhone-class widths, fresh start and reload, healthy and degraded dependencies, failure and recovery, and persistence where claimed. Fixture-only proof may validate mechanics but cannot substitute for a live-provider or live-runtime claim.
## Governance changes

1. Product contracts outrank packet-local convenience. A packet cannot redefine success downward.
2. Reviewers must record the original requested outcome, exact candidate SHA, environment, scenario, observed result, and any deviation.
3. A merged PR is publication evidence, not product-completion evidence.
4. User dogfooding is first-class acceptance evidence. Repeated user-reported failures must graduate into durable regression scenarios rather than remain chat history.
5. Duplicate rediscovery is a process defect. Rejected, already-solved, already-owned, and recurring findings should be retained as negative knowledge so future audits do not spend again on the same ground.
6. Normal user surfaces must not require knowledge of packet IDs, leases, internal state machines, CLI syntax, ports, provider plumbing, or repository structure.
7. Internal/operator detail may remain available behind progressive disclosure when it helps diagnose or govern the system.

## Sequencing rule

Do not create one flat backlog of every observation. Sequence work by causal leverage: first restore trustworthy underlying state, then complete the highest-value user loops, then repair shared engineering constraints, then expose additional capability, and finally run whole-product acceptance.

Within each user loop, prefer vertical slices that can be independently used and rejected. Do not split backend/frontend/testing into separate definitions of done when that allows an unusable intermediate state to be declared complete.

## Success metric

The primary metric is not number of packets, merged PRs, endpoints, tests, routes, or hidden capabilities. It is the proportion of intended Kitty jobs that can be completed correctly, understandably, and recoverably in the running product without developer knowledge.

A secondary engineering metric is rework: the same user requirement should not repeatedly reappear after being declared complete. Recurrence is evidence that the delivery system failed, even when each prior implementation was locally correct.

## Immediate implication

Before activating the large product-reality backlog, perform a meta audit of Kitty's product definition, architecture, technology stack, persistence model, runtime shape, development process, agent coordination, packet design, verification system, and historical churn. Use that audit to revise the recovery program so it fixes both the product and the mechanism that has repeatedly produced partial product outcomes.
