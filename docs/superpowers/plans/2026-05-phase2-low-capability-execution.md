# Phase 2 Low-Capability Execution Packet

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans` (or `superpowers:subagent-driven-development`).  
> **Mode:** Low-capability / low-reasoning execution with no quality loss.

**Goal:** Execute remaining Phase 2 work (`2C`) with weaker models while preserving implementation quality and reducing token usage.

**Architecture:** Keep the existing architecture decisions; reduce execution ambiguity through deterministic task cards, bounded context, and hard verification gates.

**Tech Stack:** Python 3.12, pytest, existing `src/tools/*` runtime surface, existing Phase 2 docs.

---

## Operating Profile (Required)

- Model tier: low-cost model first (e.g., `gpt-5.4-mini`)
- Reasoning effort: `low`
- Context mode: minimal; no broad repo scans
- One worker = one task card
- Hard budget target: `<= 250k total_tokens` per lane
- Escalation: only after failing a defined gate twice

## Minimal Read Set (Do Not Expand By Default)

1. `CURRENT_FOCUS.md`
2. `TASKS.md`
3. `docs/plans/phase2-orchestration-workflow-2026-05-06.md`
4. `docs/plans/2026-04-30-unified-tool-runtime.md`
5. `docs/handoffs/HANDOFF-2026-05-06.md`

If blocked, add exactly one file and record why.

## Worker Micro-Brief Template (Token-Optimized)

Use this exact brief format for delegated lanes:

```text
Task: <single bounded task>
Owned files: <explicit list>
Do not touch: <explicit list>
Deliverables: <explicit artifacts>
Validation command: <single command>
Report required: files changed + tests + blockers
Stop if: unclear requirement, missing dependency, gate failure
```

## Quality Gates (No Quality Loss)

A task is complete only if all are true:

1. Owned files only (or documented exception).
2. Validation command executed and passed (or documented strict-gate blocker + scoped fallback pass).
3. Completion report includes:
   - exact files changed
   - exact command(s) run
   - pass/fail outcomes
   - residual risk
4. Tracking files updated:
   - `TASKS.md`
   - `docs/TASKS.md`
   - `docs/OPEN_LOOPS.md`
   - `docs/handoffs/HANDOFF-2026-05-06.md`

---

## Task Cards: Phase 2C (Tool Runtime Alignment)

### Task Card 2C-1: Runtime Inventory + Boundary Lock

**Files:**
- Modify: `docs/OPEN_LOOPS.md`
- Modify: `docs/handoffs/HANDOFF-2026-05-06.md`
- Create: `docs/audits/tool-runtime-alignment-inventory-2026-05-06.md`

- [ ] Step 1: Inventory active tool surfaces from code.
  - Command:
    - `rg -n "ToolManager|tool_registry|KittyTools|ToolDefinition|execute\\(" src/tools src/core -g '*.py'`
- [ ] Step 2: Write inventory report with:
  - current entry points
  - overlap/duplication points
  - migration-safe boundaries
- [ ] Step 3: Update open loops with explicit 2C lane decomposition.
- [ ] Step 4: Update handoff with inventory result and next task cards.

**Validation:**
- `venv/bin/python -m py_compile scripts/kitty_builder.py`
- Expected: pass

### Task Card 2C-2: Unified Runtime Facade (Non-Destructive)

**Files:**
- Create: `src/tools/runtime.py`
- Modify: `src/tools/tool_manager.py`
- Test: `tests/test_tool_runtime.py`

- [ ] Step 1: Define typed runtime contract (`ToolDefinition`, `ToolContext`, `ToolResult`).
- [ ] Step 2: Implement minimal `ToolRuntime` registry + execution facade.
- [ ] Step 3: Make `ToolManager` delegate to `ToolRuntime` without breaking existing call sites.
- [ ] Step 4: Add tests for:
  - successful execution
  - unknown tool handling
  - compatibility with `ToolManager.execute(...)`

**Validation:**
- `venv/bin/python -m pytest tests/test_tool_runtime.py -q --tb=short --noconftest`
- Expected: pass

### Task Card 2C-3: Permission Path Alignment

**Files:**
- Modify: `src/tools/runtime.py`
- Modify: `src/tools/tool_registry.py`
- Test: `tests/test_tool_runtime.py`

- [ ] Step 1: Add permission check bridge in runtime path using registry permissions.
- [ ] Step 2: Ensure denied actions produce structured errors.
- [ ] Step 3: Add tests for permission denied behavior.

**Validation:**
- `venv/bin/python -m pytest tests/test_tool_runtime.py -q --tb=short --noconftest`
- Expected: pass

### Task Card 2C-4: Integration and Regression Gate

**Files:**
- Modify: `TASKS.md`
- Modify: `docs/TASKS.md`
- Modify: `SESSION_SUMMARY.md`
- Modify: `docs/handoffs/HANDOFF-2026-05-06.md`

- [ ] Step 1: Run focused runtime tests.
- [ ] Step 2: Attempt strict gate; if blocked by known Icon guard, run scoped fallback and record blocker.
- [ ] Step 3: Update tracking docs with objective results.

**Validation:**
- Strict:
  - `venv/bin/python -m pytest tests/test_tool_runtime.py tests/test_kitty_builder.py -q --tb=short`
- Fallback (if strict blocked by known metadata guard):
  - `venv/bin/python -m pytest tests/test_tool_runtime.py tests/test_kitty_builder.py -q --tb=short --noconftest`

---

## Stop Conditions (Mandatory)

Stop and escalate if any of these happen:

- Required file ownership overlaps another active lane.
- A task needs broader refactor than its card permits.
- Tests fail outside owned surface and no safe isolation exists.
- Token budget exceeds target without objective progress.

## Completion Definition

Phase 2 low-capability packet succeeds when:

1. `2C` task cards are executed with evidence.
2. Runtime alignment artifacts are test-backed.
3. Token usage stays within budget policy or exceptions are documented.
4. Continuity docs are current and takeover-ready.
