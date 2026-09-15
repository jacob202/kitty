# Kitty Reliability Enhancements Design — 2026-08-30

**Status:** approved by Jacob’s instruction to research broadly and proceed directly into implementation.

## Architecture

Keep reliability local to the seams that already own the behavior. `mcp_tool_bridge` owns subprocess invocation and ephemeral dependency cutoff state. `context_assembler` owns request-specific context availability. `health_surface` remains the one read-only operational projection. A new developer-only reliability gate repeats fixed pytest fault scenarios and emits evidence; it is not a runtime scheduler or database.

## 1. Tool resilience

Use a circuit keyed by `(server_name, tool_name)` with three consecutive failures opening it and a 30-second cooldown. When open, `invoke()` returns a structured error without launching a child. After cooldown, one call is allowed as a recovery probe; success clears the circuit, failure opens it again. State is process-local by design: this is load shedding, not durable business state.

Timeout resolution is server/tool specific: `tool_timeouts[tool_name]`, then server `timeout_seconds`, then a safe default. Values must be finite positive numbers within a hard maximum. Timeout and cancellation always terminate the child, await exit briefly, then kill and await if necessary. Cancellation is re-raised after cleanup.

`tool_health_snapshot()` exposes configured-server count and open circuits. `health_surface` adds an `mcp_tools` domain. No configured MCP servers is healthy/available with a truthful reason; any open circuit is degraded. It does not probe remote servers and must say so in detail/reason.

## 2. Context health

`ContextBundle` gains `context_health`, a JSON-ready receipt containing `mode`, `degraded_sources`, `budget_clipped`, and `warning_count`. Source names are derived from warning prefixes and normalized; raw exception messages never enter model context.

When retrieval/enrichment has source failures, prepend a compact `<kitty_context_state ...>` marker to the existing domain block before budget fitting. It tells the model not to imply missing context was used and to disclose the limitation only when material. Healthy turns add no marker, preserving current output. Budget clipping remains visible through existing truncation markers and the structured receipt.

## 3. Repeatability gate

`scripts/kitty_reliability_gate.py` runs only a repo-owned fixed list of pytest node IDs that deliberately exercise degraded context, health degradation, MCP timeout cleanup, and circuit recovery. CLI accepts only bounded repetition count and optional JSON output path; it never accepts arbitrary commands. Every repetition must pass. Evidence includes schema version, git SHA, scenario IDs, repetition count, per-run exit/duration, success rate, and `all_passed`. JSON output is atomic (`tempfile` + `os.replace`).

## Testing and boundaries

All behavior is test-first. Focused tests cover timeout/cancellation cleanup, circuit transitions, timeout configuration validation, health projection, healthy/degraded context output, and reliability-receipt math/CLI failure semantics. Then run surrounding health/context/action/runtime suites, Ruff, mypy, `git diff --check`, the repeatability gate itself, and an independent exact-head review.

Excluded paths include all PR #705 files, current Work/Builder retry/supervisor lanes, and the canonical dirty checkout.
