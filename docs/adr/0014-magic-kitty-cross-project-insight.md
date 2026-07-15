---
type: adr
title: "Magic Kitty: Cross-Project Insight Is The Point, Not A Feature"
status: accepted
owner: jacob
primary_purpose: Cross-project insight is the core value proposition, not an optional feature
derives_from:
  - docs/CONSTITUTION.md
review_cycle: as needed (superseded by replacement ADR)
---

# ADR-0014: Magic Kitty: Cross-Project Insight Is The Point, Not A Feature

**Status:** Accepted
**Date:** 2026-07-05 (decided by Jacob, mid-build on packet 016)

## Context

A Codex-generated brief found a real connection between two of
Jacob's projects that looked unrelated — and it landed. His words:
_"that's exactly the kind of information, insights, or whatever
the experience I wanna have with AI... I'm always kind of blown
away."_

Then, pushed on scope: _"I'm a little disorganized and so much
happens — little shit gets missed all the time, the magic a
project can have just disappears when there's no attention to the
minutiae that makes a life extraordinary... I kind of want magic.
That's a phrase we need more of — Kitty is all about perspective
shifts. Magic Kitty."_

## Decision

The per-project "what's B" navigator (016) and cross-project
insight-finding are two different capabilities, not one. 016 stays
narrow and mechanical-plus-one-LLM-call by design — one step, one
project, anti-nag. Insight-finding is a separate, later layer: look
across _all_ active projects' composed state (021's `resume()` for
each) and surface non-obvious connections between them — the "huh,
these are actually related" moment. That layer is not yet
packet-scoped; naming it here so it survives past this session
instead of getting lost the way Jacob just described things getting
lost.

**Build order (his own call, same message):** basic thing first,
verified working, _then_ integrate magic on top. Do not let "but
what about the insight layer" block 016 from shipping. Do not let
016 shipping close the door on the insight layer — it's next, not
someday.

## Consequences

What this rules out:

- Treating 016 as "done" in the product-vision sense once it ships
  — it's the floor, not the ceiling. The move-in-day bar
  (ADR-0013) only needs the floor; "magic" is what makes Kitty
  worth continuing to use after.
- Building the insight layer as a bolt-on inside 016's narrow
  prompt (one step, one project) instead of its own packet with
  its own prompt design — conflating the two reproduces the exact
  overload 021 already refused (see that packet's
  "next_actions_json stays mechanical" note).
- Losing this note. If a future session reads D1–D12 and not this
  one, the thing Jacob actually said he wants from Kitty is
  invisible again.
