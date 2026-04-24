---
name: reasoning
description: Use when performing any non-trivial analysis, debugging, or implementation task that requires structured reasoning
---

# Reasoning (7-Stage Pipeline)

One integrated workflow for debugging, analysis, planning, and code review. Not toggled modes — all stages active.

---

## The Pipeline

1. **Understand** — Surface assumptions. Name what's unclear. Present multiple interpretations if they exist.
   **Cross-refs:** `karpathy-guidelines` (Think Before Coding)

2. **Build Lens / Trace Cause** — For analysis: extract patterns and expectations of the domain. For debugging: trace backward from symptom to root cause.
   **Cross-refs:** `systematic-debugging` (Root Cause Investigation), `karpathy-guidelines` (Simplicity First)

3. **Hypothesize** — One hypothesis, smallest possible test. Change one variable. If it fails, form a new hypothesis — don't pile on fixes.
   **Cross-refs:** `systematic-debugging` (Hypothesis and Testing), `test-driven-development` (RED)

4. **Implement** — Surgical change, test-first. No "while I'm here" improvements. Match existing style.
   **Cross-refs:** `surgical-coding`, `karpathy-guidelines` (Surgical Changes)

5. **Review** — Check correctness, completeness, edge cases, security. Rate issues P0–P3. Only P0/P1 block.
   **Cross-refs:** `deepseek-reasoning-review`, `deployment-safety-review` (severity taxonomy)

6. **Verify** — Fresh verification evidence before claiming completion. No "should", "probably", "seems to".
   **Cross-ref:** `verification-before-completion`

7. **Reflect** — What patterns emerged? What should the human decide?

---

## Principle

Never classify without a lens first. The system is a mirror, not a judge. Final verdict is always the human.
