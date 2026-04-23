---
name: execution
description: Use when implementing features, fixing bugs, or executing any code change
---

# Execution (4-Phase Pipeline)

A unified execution workflow covering the full implementation lifecycle. Choose the phase that matches your needs — they compose naturally.

---

## Phase 1: Test-Driven Development

**Iron Law: No production code without a failing test first.**

### Red-Green-Refactor Cycle

1. **RED** — Write one failing test showing what should happen
   - One behavior, clear name, real code (no mocks unless unavoidable)
2. **Verify RED** — Watch it fail (MANDATORY)
   - Confirm the test fails for the expected reason (feature missing, not typos)
3. **GREEN** — Write minimal code to pass the test
   - Just enough to pass. No added features, no scope creep.
4. **Verify GREEN** — Watch it pass (MANDATORY)
   - Confirm the test passes and no other tests broke
5. **REFACTOR** — Clean up while keeping tests green
   - Remove duplication, improve names, extract helpers
6. **Repeat** — Next failing test for next behavior

### Red Flags

- Code before test → stop and start over
- "I'll test after" → tests passing immediately prove nothing
- "Delete X hours? That's wasteful" → sunk cost fallacy. Keeping unverified code is technical debt.

**Cross-refs:** `test-driven-development` (full procedure, rationalizations, anti-patterns)

---

## Phase 2: Autonomous Execution / Vibe Coding

**Iterative loop: implement → test → repair → repeat.**

When the user says *"add X"* or *"fix Y"* — you execute fully without step-by-step permission:

### The Loop

1. **Analyze Intent** — Decipher the request. Don't ask for paths if the goal is clear.
2. **Read Before Writing** — Map target files, understand current state.
3. **Implement** — Make surgical changes. Touch only what you must.
4. **Test** — Run tests to verify the feature works.
5. **Self-Repair** — If tests fail, diagnose → fix → re-test. Repeat up to 5 times.
6. **Verify** — Run full test suite. Confirm zero regressions.

### Parallel Dispatch

When facing 2+ independent tasks (different test files, different subsystems, different bugs):

- **Dispatch one subagent per independent problem domain**
- Each agent gets: specific scope, clear goal, constraints, expected output
- Review summaries when agents return
- Verify fixes don't conflict; run full suite

### When to NOT dispatch in parallel

- Failures are related (fixing one may fix others)
- Need to understand full system state
- Agents would interfere (editing same files, using shared resources)

**Cross-refs:** `vibe-coding` (autonomous ownership), `dispatching-parallel-agents` (parallel dispatch pattern), `systematic-debugging` (when self-repair fails — go back to root cause)

---

## Phase 3: Production Readiness

**Sequential pipeline: cleanup → format → lint → optimize → security scan.**

Run this AFTER the feature works but BEFORE claiming completion:

### Step 1: Cleanup
- Remove debug artifacts (console.log, print, debugger statements)
- Fix formatting (code style, whitespace consistency)
- Optimize imports (remove unused, consolidate)
- Polish comments (remove noisy/generated ones, improve ones that explain "why")

### Step 2: Optimize
- Check for performance antipatterns (unnecessary allocations, O(n²) when O(n) possible)
- Scan for security vulnerabilities (injection, XSS, credential leaks)
- Identify error handling gaps (unhandled rejections, missing validation)
- Find edge cases (empty states, boundary conditions)

### Step 3: Verify
- Run full test suite
- Run linter
- Check type checker if available
- Re-read the original request — is everything implemented?

**Cross-refs:** `code-cleanup` (removing debug, fixing format, optimizing imports, improving comments), `code-optimization` (performance, security, error handling, edge cases), `deepseek-reasoning-review` (deep review pass), `verification-before-completion` (iron law: evidence before claims)

---

## Phase 4: Plan-Based Execution

**Take a written plan, execute task by task. No placeholders. No skipping steps.**

### When to Use

When you have a spec or written implementation plan with defined tasks and you need disciplined execution.

### Process

1. **Read the plan** — Understand the full scope and task order
2. **Execute in order** — One task at a time (or batch with checkpoints)
3. **Each task completes fully** — Implement, test, verify before moving on
4. **No skipping** — Every step in the plan exists for a reason
5. **If blocked** — Stop, document what's blocking, ask for guidance

### Execution Options

- **Subagent-Driven (recommended):** Dispatch a fresh subagent per task with review between tasks. Fast iteration, isolated context.
- **Inline Execution:** Execute tasks in current session with batch checkpoints for review.

**Cross-refs:** `writing-plans` (creating the plan), `executing-plans` (inline batch execution), `subagent-driven-development` (per-task subagent dispatch), `finishing-a-development-branch` (completion handoff after all tasks done)

---

## Phase Selection Guide

| Situation | Start With |
|-----------|-----------|
| Building new feature from spec | Phase 1 (TDD) |
| User gives vague request, wants speed | Phase 2 (Vibe) |
| Feature works but needs polish | Phase 3 (Production) |
| Following written implementation plan | Phase 4 (Plan) |
| Bug fix | Phase 1 (TDD: write failing test first) |
| Multi-subtask feature | Phase 4 with Phase 2 per task |
| Shipping to production | Phase 3 after any phase |

## Design Notes

This skill is an **overlay layer** — it references existing skills as deep-dive resources, not replaces them. Existing skills remain available for standalone use when you need to go deep on one phase.

Phases compose naturally: you might do Phase 4 (plan execution) where each task goes through Phase 1 (TDD) followed by Phase 3 (production readiness).
