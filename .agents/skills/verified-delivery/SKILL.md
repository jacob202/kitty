---
name: verified-delivery
description: Use when implementing, repairing, reviewing, or claiming completion of software work where success must be demonstrated with reproducible evidence.
---

# Verified Delivery

## Core rule

A plausible artifact is not a completed outcome. Define success before implementation, preserve only high-signal context, and verify the result from a fresh perspective.

## 1. Create the outcome contract first

Copy `outcome-contract.md` into the task notes and fill it in before editing code. The contract must contain:

- the user-visible outcome;
- observable acceptance criteria;
- exact verification commands or interactions;
- prohibited shortcuts and non-goals;
- required evidence artifacts;
- the maximum repair cycles before reporting blocked.

A criterion such as “looks good” or “should work” is invalid. Rewrite it as something an independent reviewer can observe.

## 2. Keep the active context small

Load only the authority, code, tests, and live evidence needed for the current criterion.

Persist outside the active conversation:

- accepted requirements and decisions;
- unresolved questions and blockers;
- changed paths and current SHA;
- exact commands and results;
- facts that must survive a new session.

Drop or re-fetch:

- large file/tool outputs;
- repeated discussion;
- stale plans;
- speculative explanations;
- data already represented by a concise verified note.

Compaction is lossy. Before any reset or handoff, explicitly preserve the outcome contract, decisions, current state, failures, and next verification action.

## 3. Implement against one criterion at a time

For each criterion:

1. establish the failing or missing behavior;
2. make the smallest bounded change;
3. run the narrow verification;
4. record the command, result, and artifact;
5. continue only when the evidence matches the claim.

Do not widen scope because nearby cleanup is tempting.

## 4. Verify independently

The implementer may run checks, but cannot grant independent acceptance to its own work (Constitution VI.4: the worker that executes a change is never the reviewer that accepts it).

A review-only pass *in the same context* is a self-check: it feeds the repair loop and records implementation evidence, but it is not independent acceptance. When the final state depends on a verifier’s verdict, the verification must run in a genuinely separate trust boundary — a different agent or tool process, or a distinct review invocation that receives only:

- the outcome contract;
- the changed SHA or diff;
- the allowed verification tools;
- the produced evidence.

The verifier must inspect the actual artifact and rerun the relevant checks. It returns a per-criterion verdict: `PASS`, `FAIL`, or `UNVERIFIED`, with concrete gaps.

A solo interactive session that cannot invoke a genuinely separate verifier must finish as `implemented, awaiting verification` (or `blocked`/`failed`), never `verified`.

## 5. Repair with a hard cap

Feed only verifier gaps back to the implementer. Repeat up to the contract’s repair limit. When the cap is reached, stop and report the unresolved criterion and evidence; do not keep polishing indefinitely.

## Completion language

Use exactly one honest state:

- **verified** — every criterion passed independently on the reviewed SHA or runtime artifact;
- **implemented, awaiting verification** — implementation exists but independent review has not passed;
- **blocked** — a named dependency prevents further progress;
- **failed** — attempted work did not achieve the contracted outcome.

The classification must bind to the durable record, not only to this conversation. Where Kitty’s Builder owns the state, reconcile the classification with `initiative_status`, attempt/run states, decision events, and PR check runs; a claim must not contradict that durable state.

Never use “done,” “fixed,” or “working” without binding the claim to reproducible evidence.