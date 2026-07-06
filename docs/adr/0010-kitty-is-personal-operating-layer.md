# ADR-0010: Kitty Is A Personal Operating Layer

**Status:** Accepted
**Date:** 2026-07-01 (from `docs/OPERATOR_STRATEGY.md`, merged in #59)

## Context

Kitty's product identity has to be one thing. Without a clear
identity, every new packet becomes its own product: chat over
here, capture over there, memory in a different direction, agents
in yet another.

## Decision

Kitty is a personal operating layer: a state store,
capture-and-triage loop, action queue with enforced approval tiers,
and model-delegation router — worn with the SOUL persona. Chat is
one interface to that layer, not the product.

The near-term build order is the state + action spine (packets in
`docs/packets/`), not further consolidation, memory expansion, or
UI polish.

## Consequences

What this rules out until the spine ships:

- New memory substrates, typed knowledge graphs, event buses.
- Autonomous outbound actions of any kind (draft-only until the
  action queue has audit history).
- Panels or endpoints that serve fabricated data; state surfaces
  bind to real rows or do not ship.

What this commits to:

- New state-spine stores (signals, triage, actions, projects) are
  each their own module over `kitty.db` migrations, per ADR-0008.
- External feeds are cron-polled connectors that emit deduped
  signal rows.
- Every action Kitty takes is a recorded row with a preview and a
  result; approval tiers are enforced in the executor registry,
  in code.
