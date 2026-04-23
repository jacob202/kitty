---
name: reasoning
description: Use when performing any non-trivial analysis, debugging, or implementation task that requires structured reasoning
---

# Reasoning (7-Stage Pipeline)

A single integrated reasoning workflow that weaves Karpathy principles, CGI lens-building, systematic debugging, critical review, and verification into one flow. Not toggled modes — one pipeline, all stages.

Works for: debugging, analysis, planning, implementation, code review, research.

---

## Stage 1: Understand Before Acting

**Surface assumptions. Name what's unclear. Establish context grammar.**

Before any action:

- State your assumptions explicitly: *"What do I think I know about this?"*
- Name what's unclear: *"What don't I know yet?"*
- Draw from Karpathy *Think Before Coding*: don't assume, don't hide confusion, surface tradeoffs
- If multiple interpretations exist, present them — don't pick silently
- If a simpler approach exists, say so — push back when warranted
- Establish a *context grammar* (CGI-inspired): what are the rules, patterns, and expectations of this domain?

**Cross-refs:** `karpathy-guidelines` (Think Before Coding), `socratic-lens/chains/CGI-1-GRAMMAR` (context grammar)

---

## Stage 2: Build a Lens / Trace Root Cause

**Learn the context before evaluating. Or trace backward from symptom to root cause.**

Two paths depending on the task:

### Path A: Analysis (build a lens)

Construct a "lens" — what patterns/expectations does this domain have? Use CGI-inspired framing:

- Extract context grammar from the available information
- Find positive examples (what works/transforms)
- Find negative examples (what's mechanical/doesn't work)
- Synthesize: what question would reveal the truth here?

### Path B: Debugging (trace root cause)

Backward-trace from symptom to root cause, one link at a time:

1. Read error messages carefully (don't skip)
2. Reproduce consistently
3. Check recent changes (git diff, recent commits)
4. Gather evidence at component boundaries
5. Trace data flow backward to the source

**Cross-refs:** `socratic-lens/chains/CGI-4-LENS` (lens synthesis), `systematic-debugging` (Root Cause Investigation phase), `karpathy-guidelines` (Simplicity First)

---

## Stage 3: Form Hypothesis, Test Minimally

**One hypothesis at a time. No shotgun debugging.**

- State clearly: *"I think X is the root cause/solution because Y"*
- Make the SMALLEST possible test of that hypothesis
- Isolate one variable — never change multiple things at once
- Write a failing test first (TDD) when possible
- If the hypothesis fails, form a NEW hypothesis — don't add "fixes" on top

**Cross-refs:** `systematic-debugging` (Hypothesis and Testing phase), `test-driven-development` (RED: write failing test first)

---

## Stage 4: Implement with Discipline

**Surgical changes. Minimal code. Test-first.**

- Change one thing, see what happens
- Write minimal code to pass the test — nothing speculative
- No features beyond what was asked
- Touch only target files — don't refactor adjacent code
- No "while I'm here" improvements
- Match existing style, even if you'd do it differently

**Cross-refs:** `surgical-coding` (all principles), `karpathy-guidelines` (Surgical Changes, Simplicity First, Goal-Driven Execution), `test-driven-development` (GREEN: minimal code)

---

## Stage 5: Critical Review

**Review for: correctness, completeness, edge cases, security, assumptions.**

Evaluate the implementation through the lens built in Stage 2:

- **Correctness:** Does it do what the request asks?
- **Completeness:** Does it handle all stated requirements?
- **Edge cases:** Empty states, error conditions, boundary values
- **Security:** Any injection vectors, data leaks, auth bypasses?
- **Assumptions:** Were any implicit assumptions wrong?

Rate issues using deployment-safety-review taxonomy:
- **P0 (Critical):** Blocks shipping — must fix now
- **P1 (Important):** Should fix before proceeding
- **P2 (Minor):** Note for later
- **P3 (Cosmetic):** Style, preference only

Only P0/P1 block. P2/P3 noted.

**Cross-refs:** `deepseek-reasoning-review` (deep critical analysis), `deployment-safety-review` (severity taxonomy), `socratic-lens/chains/CGI-5-SCAN` (scanning through a lens)

---

## Stage 6: Verify Before Claiming

**Iron Law: no completion claim without fresh verification evidence.**

1. Identify: what command proves this claim?
2. Run: execute the FULL command (fresh, complete)
3. Read: full output, check exit code, count failures
4. Does output confirm the claim? If yes, claim WITH evidence. If no, state actual status.

Red flags: using "should", "probably", "seems to" — any expression of satisfaction before verification.

**Cross-refs:** `verification-before-completion` (full procedure)

---

## Stage 7: Optional Reflect

**What patterns emerged? What should the human decide?**

- What patterns emerged in this work?
- Did the lens hold? Where did it struggle?
- What should the human decide, not the system? (CGI rule: final verdict always human)
- Meta: Did this analysis itself shift anything?

**Cross-refs:** `socratic-lens/chains/CGI-6-SOCRATIC` (Socratic Reflection), `receiving-code-review` (when receiving feedback)

---

## Quick Reference

| Stage | Key Activity | Success Criteria |
|-------|-------------|------------------|
| 1. Understand | Surface assumptions, establish grammar | Know what you know and don't know |
| 2. Build Lens / Trace | Construct lens or trace root cause | Clear theory of the domain or root cause |
| 3. Hypothesize | One hypothesis, minimal test | Confirmed or refuted hypothesis |
| 4. Implement | Surgical change, test-first | Minimal working solution |
| 5. Review | Correctness, security, edge cases | Issues rated P0-P3, P0/P1 fixed |
| 6. Verify | Fresh verification evidence | Evidence confirms completion |
| 7. Reflect | Patterns, human decisions | Insights captured, human empowered |

## Design Notes

This skill is an **overlay layer** — it references existing skills as deep-dive resources, not replaces them. Existing skills remain available for standalone use when you need to go deep on one stage.

**CGI Integration:** The CGI system (from socratic-lens) maps directly:
- GRAMMAR → Stage 1 (context grammar)
- POSITIVE + NEGATIVE + LENS → Stage 2 (lens construction)
- SCAN → Stage 5 (review through the lens)
- SOCRATIC → Stage 7 (reflection)

Cardinal CGI rule observed: NEVER classify without a lens first. The system is a MIRROR, not a judge. Final verdict always human.
