---
name: execution
description: Use when implementing features, fixing bugs, or executing any code change
---

# Execution (4-Phase Pipeline)

Select the phase that matches your situation. They compose naturally.

---

## Phase Selection Guide

| Situation | Start With |
|-----------|-----------|
| Building new feature from spec | Phase 1 (TDD) |
| User says "add X" / "fix Y", wants speed | Phase 2 (Vibe) |
| Feature works but needs polish | Phase 3 (Production) |
| Following a written plan | Phase 4 (Plan) |
| Bug fix | Phase 1 (write failing test first) |
| Shipping to production | Phase 3 after any phase |

---

## Phase 1: TDD

**No production code without a failing test first.**

Write one failing test → make it pass → refactor → repeat.

**Cross-refs:** `test-driven-development` (full procedure, anti-patterns)

## Phase 2: Autonomous Execution

Implement → test → self-repair → verify. No step-by-step permission needed.

**Parallel dispatch** when 2+ tasks are independent (different files, different subsystems). Don't parallelize when failures are related or agents would edit the same files.

**Cross-refs:** `vibe-coding` (autonomous ownership), `dispatching-parallel-agents` (parallel dispatch), `systematic-debugging` (when self-repair fails)

## Phase 3: Production Readiness

Run after feature works, before claiming completion: cleanup → optimize → verify.

**Cross-refs:** `code-cleanup` (debug artifacts, formatting, imports), `code-optimization` (performance, security, edge cases), `verification-before-completion` (evidence before claims)

## Phase 4: Plan-Based Execution

Execute a written plan task by task. No skipping. No placeholders. If blocked, stop and document why.

**Cross-refs:** `writing-plans` (creating plans), `executing-plans` (inline batch execution), `subagent-driven-development` (per-task subagent dispatch), `finishing-a-development-branch` (completion handoff)
