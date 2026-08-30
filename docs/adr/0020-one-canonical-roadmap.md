# ADR 0020: One Canonical Roadmap and Planning Ownership

- **Status:** Accepted
- **Date:** 2026-07-26
- **Decision owner:** Jacob
- **Amends:** ADR 0017's assignment of packet decomposition to KittyBuilder

## Context

Kitty accumulated roadmaps, implementation plans, audits, initiative manifests,
packet prose, session checkpoints, and chat decisions that all described future
work. Several were individually useful, but together they made current priority
and authority expensive to determine. Runtime truth advanced faster than the
plans, leaving old plans active after their assumptions had become false.

Packets also carried too many jobs at once: idea storage, design, sequencing,
and executable instructions. That made them unstable planning documents and
unreliable worker contracts.

## Decision

There is exactly one active roadmap: `docs/ROADMAP.md`.

The planning hierarchy is:

```text
North Star + accepted ADRs + Alignment Map
  → canonical roadmap
  → approved Mission
  → initiative
  → executable packet
  → attempt and evidence
```

Responsibilities are separated:

1. Jacob, Kitty, or an explicitly assigned strong-model planning session owns
   architecture judgment, priorities, decomposition, and packet authoring.
2. KittyBuilder validates approved initiatives and packets, chooses the next
   eligible approved packet, executes it, verifies it, and advances delivery.
3. Runtime workers implement bounded contracts. They do not invent the roadmap,
   redesign packets, or silently widen scope.
4. Research, audits, brainstorms, old plans, and prose packets remain evidence
   or backlog input. Their existence does not make them active authority.
5. Ideas are preserved in an organized backlog or archive. Preservation does
   not imply current priority or executability.
6. Status is derived from repository, GitHub, and Builder evidence. A manually
   maintained status document may summarize that evidence but may not compete
   with it.

## Consequences

- `docs/INITIATIVES_OPTIMIZED_2026-07-24.md`, `docs/PLANS.md`, and retained
  Builder plans become inputs to the roadmap rewrite, not parallel roadmaps.
- A packet compiler or authoring assistant may render validated manifests, but
  it cannot supply unresolved product or architecture judgment.
- Packet 007's current Markdown renderer is not the planning engine and is not
  first in the free-execution conversion order.
- A material roadmap change is reviewed as a planning decision before packets
  are generated from it.
- Clean workers need one reading path rather than reconstructing priority from
  several plans and chat history.

## Revisit trigger

Revisit only if one roadmap cannot represent genuinely independent products or
repositories without becoming ambiguous. Multiple views generated from one
roadmap are allowed; multiple authorities are not.
