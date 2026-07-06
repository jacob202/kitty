# ADR-0004: memory_graph Owns Context Reads

**Status:** Accepted
**Date:** 2026-07-02

## Context

Context reads for prompts and search need a consistent shape across
memory stores (inbox, journal, todos, knowledge, etc.). Without a
single read path, every call site reinvents filtering, ordering, and
error handling, and the result is uneven.

## Decision

New prompt/search context reads go through `gateway/memory_graph.py`.
Phase B may add a write-side router, but should not bypass this read
rule.

## Consequences

- Every new context read is a `memory_graph` adapter, not a direct
  store import.
- The shape of a read result (`Item`, `GraphResult`) is defined in
  `memory_graph.py`; downstream code is shaped to it.
- Direct store imports are still allowed in subsystem owners and in
  tests, but never in route or prompt-assembly code.
