# Kitty Reliability + Enhancement Brief — 2026-08-30

## Purpose

Turn recent agent-reliability research into small improvements to Kitty itself (not another Builder-only pass). The selection rule is user-visible reliability leverage first, reuse current owners, and no new queue/store/observability framework.

## External reconnaissance

1. **HAL Reliability (Princeton, 2026):** capability and accuracy can improve while repeated-run reliability barely moves. The practical release question is not “did it pass once?” but “does the same scenario keep passing?” Source: https://hal.cs.princeton.edu/reliability/findings/
2. **AWS Agentic AI Lens (2026):** degraded dependencies should map to explicit reduced modes; checkpoint/recovery and fault injection should be routine; external tools need per-tool cutoffs, timeout/retry policy, and recovery probes. Sources: https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/reliability.html and https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentrel03-bp04.html and https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentops04-bp03.html
3. **Microsoft MCP governance (2026):** MCP standardizes execution but not policy/reliability. Deterministic checks belong between model intent and execution; cascading retries need circuit breakers. Source: https://developer.microsoft.com/blog/securing-mcp-a-control-plane-for-agent-tool-execution/
4. **Microsoft Research tool-space interference (2025):** more tools can reduce end-to-end task performance, inflate context, and make recovery brittle. Source: https://www.microsoft.com/en-us/research/blog/tool-space-interference-in-the-mcp-era-designing-for-agent-compatibility-at-scale/

## Kitty reconnaissance

Kitty already has most of the right primitives:

- `context_assembler` performs concurrent partial-result retrieval with per-source warnings.
- `health_surface` already projects `available/degraded/stale/unavailable/unknown` without a second health store.
- `runtime_manifest` already gives every chat turn explicit runtime truth.
- `action_grants` already owns deterministic tool/action authorization; do not build a second ACL.
- Builder now has durable execution/recovery receipts from PR #704.

The most useful gaps are therefore at existing seams, not new architecture.

## Ranked implementation

### R1 — MCP/tool invocation resilience

`gateway/mcp_tool_bridge.py` can leave a subprocess alive after timeout, uses one global 120-second timeout, and has no cutoff when the same tool is repeatedly failing. Add bounded per-server/tool timeout selection, deterministic in-memory circuit-breaker state, and guaranteed terminate/kill/wait cleanup. Expose only breaker/configuration health through the existing health projection; do not pretend an unprobed server is live.

### R2 — Context degradation truth inside the turn

`ContextBundle.warnings` is truthful but largely operator-only. Derive a stable `context_health` receipt (`full|degraded`, degraded sources, budget clipping) and add a small model-visible degradation marker when retrieval/enrichment sources fail. Never inject raw exception text into the prompt. Healthy prompts remain unchanged.

### R3 — Repeatability + fault-injection release gate

Add a fixed, non-arbitrary reliability gate that repeats a small set of deterministic failure-path tests and fails unless every repetition passes. Emit a JSON receipt with exact git SHA, repetitions, outcomes, and timing. This imports HAL’s repeated-success insight without inventing a new benchmark framework.

## Explicit deferrals

- **Chat/UI degradation badges and reconnect UX:** valuable, but PR #705 and the canonical checkout currently own overlapping Chat/frontend files.
- **Offline-first mutation queue:** larger architectural change; wait until current Chat persistence work settles and daily-driver evidence proves it is needed.
- **New memory database/cache:** rejected. Kitty already has explicit memory + memory graph + health semantics; another store would increase failure surface.
- **New policy engine for tools:** rejected. `action_grants` is already the deterministic authorization owner.
- **Large tool-catalog redesign:** defer until MCP execution is actually wired into the chat runtime; current bridge is mostly discovery/integration scaffolding.

## Success criteria

1. A timed-out/cancelled MCP subprocess is always reaped.
2. Repeated tool failures open a bounded circuit and stop new subprocesses until cooldown; a successful recovery probe closes it.
3. MCP breaker state appears in Kitty’s existing health surface without claiming live health that was never probed.
4. Request-specific context failures produce structured `context_health` and a bounded model-visible degradation marker; healthy output remains byte-identical.
5. A fixed reliability gate repeats the selected fault scenarios and exits non-zero on any repetition failure.
6. No PR #705 paths, Builder queue/retry files, canonical dirty checkout, new DB, or new dependency are touched.
