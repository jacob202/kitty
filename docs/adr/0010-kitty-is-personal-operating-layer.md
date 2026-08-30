# ADR-0010: Kitty Is A Personal Operating Layer

**Status:** Accepted; amended 2026-07-26
**Date:** 2026-07-01 (from `docs/OPERATOR_STRATEGY.md`, merged in #59)

## Context

Kitty's product identity has to be one thing. Without a clear identity, every
new packet becomes its own product: chat over here, capture over there, memory
in a different direction, agents in yet another.

## Decision

Kitty is a personal operating layer: a state store, capture-and-triage loop,
action queue with enforced approval tiers, and model-delegation router — worn
with the SOUL persona. Chat is one interface to that layer, not the product.

## Original near-term consequence

The original ADR prioritized the state + action spine over further
consolidation, memory expansion, or UI polish and ruled out new substrates and
fabricated state surfaces until that spine shipped.

## Amendment — 2026-07-26

The state and action spine has shipped. Its old packet-order instruction is
fulfilled and no longer controls the roadmap.

The durable product decision remains:

- Kitty is the personal operating layer, not a collection of disconnected
  feature panels.
- State surfaces bind to real rows or report unavailable/unknown; they do not
  render fabricated success.
- New work is sequenced by `docs/ROADMAP.md` under ADR 0020 and the life-first
  North Star, not by the 2026-07-01 packet order.
- The next product proof is the resume loop working end to end for a real life
  project, after the trust foundation is restored.
