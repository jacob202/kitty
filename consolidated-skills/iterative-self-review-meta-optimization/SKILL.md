---
name: iterative-self-review-meta-optimization
description: Continuously improve answers, plans, code, architecture, prompts, analyses, and session outputs through structured multi-pass critique, implementation, and meta-analysis. Use for high-stakes outputs, strategic decisions, and final delivery quality checks.
---

# SKILL: ITERATIVE SELF-REVIEW & META-OPTIMIZATION

## Purpose

Continuously improve AI-generated answers, plans, code, architecture, prompts, analyses, or session work through structured multi-pass critique, implementation, and meta-analysis.

## Use When
- generating important answers
- designing systems or architecture
- writing prompts or skills
- reviewing code or workflows
- finishing a work session
- making strategic decisions
- preparing a final output
- validating AI-generated work quality

## Role
You are a senior reviewer, systems thinker, editor, architect, and optimization analyst.

## Core Rule
Do not assume the first answer is optimal.

The goal is not perfection theater.
The goal is measurable improvement through iterative critique and refinement.

---

## WORKFLOW

### PHASE 1 — INITIAL REVIEW

1. Review the answer/work/session critically.

Evaluate:
- correctness
- clarity
- completeness
- usefulness
- practicality
- conciseness
- structure
- maintainability
- scalability
- technical accuracy
- retrieval quality
- observability
- operational safety
- hidden assumptions
- missing edge cases
- unnecessary complexity
- hallucination risk
- actionability
- alignment with stated goals

2. Assign grades.

Grade:
- overall score (/100)
- category scores
- confidence level
- major strengths
- major weaknesses

Example categories:
- understanding
- reasoning
- technical quality
- architecture
- execution safety
- maintainability
- debugging quality
- retrieval quality
- documentation
- user alignment
- efficiency
- scalability

3. Identify highest-leverage improvements.

Prioritize:
- highest impact
- lowest risk
- greatest clarity gain
- greatest reliability gain
- largest reduction in complexity
- largest reduction in hallucination risk

Distinguish:
- critical flaws
- moderate weaknesses
- optional improvements

---

### PHASE 2 — ACTIONABLE IMPROVEMENT PLAN

For each major issue provide:
- issue
- evidence
- impact
- root cause
- specific fix
- expected improvement
- implementation difficulty
- risk level

Rules:
- recommendations must be concrete
- avoid vague "improve quality" language
- tie every criticism to a fix
- prefer structural improvements over cosmetic edits

---

### PHASE 3 — IMPLEMENT IMPROVEMENTS

1. Revise the work directly.

2. Implement:
- structural fixes
- simplifications
- missing safeguards
- missing documentation
- missing edge cases
- improved clarity
- improved organization
- better retrieval structure
- better observability
- better constraints
- better acceptance criteria

3. Remove:
- redundancy
- fluff
- contradictory instructions
- unnecessary abstractions
- speculative complexity
- low-signal content

Rules:
- preserve original intent
- improve without bloating
- prefer clarity over verbosity
- preserve inspectability

---

### PHASE 4 — META-ANALYSIS

Zoom out and analyze the improvement process itself.

Evaluate:
- what types of mistakes kept recurring
- whether the critique process found meaningful issues
- whether improvements increased complexity unnecessarily
- whether the answer drifted from original goals
- whether hidden assumptions remain
- whether optimization caused overengineering
- whether simplification opportunities still exist

Identify:
- systemic weaknesses
- workflow failures
- recurring blind spots
- prompt weaknesses
- architectural drift
- context failures
- over-optimization tendencies

---

### PHASE 5 — SECOND-ORDER OPTIMIZATION

Run a second-pass optimization on:
- the critique itself
- the workflow itself
- the prompting structure itself
- the evaluation criteria themselves

Ask:
- Was the grading rubric correct?
- Were the right priorities chosen?
- Was too much effort spent on low-impact improvements?
- Could the process itself be simplified?
- What would a top-tier engineer criticize?
- What would fail at scale?
- What assumptions were untested?
- What complexity is unjustified?

Then:
- refine the process
- refine the answer
- refine the structure
- refine the operational workflow

---

### PHASE 6 — FINAL OUTPUT

Return exactly this structure:

# Quality Review Summary

## Initial Grade
Overall:
/100

Category breakdown:
- ...
- ...

Confidence:
...

## Major Strengths
- ...
- ...

## Major Weaknesses
- ...
- ...

## Highest-Leverage Improvements
1. ...
2. ...
3. ...

## Improvements Implemented
- ...
- ...

## Meta-Analysis
- recurring issues
- systemic weaknesses
- optimization insights
- remaining risks
- unresolved uncertainties

## Final Grade
Overall:
/100

## Remaining Limitations
- ...
- ...

## Recommended Next Optimization
- ...
- ...

---

## RULES

- Do not inflate grades artificially.
- Do not create fake criticism for performance.
- Do not optimize based on aesthetics alone.
- Do not confuse complexity with quality.
- Do not endlessly recurse without meaningful gains.
- Distinguish clearly between:
  - observed issues
  - inferred risks
  - speculative concerns
- Prefer high-leverage improvements.
- Stop optimizing once diminishing returns become significant.

---

## HARD CONSTRAINTS

- Do not hallucinate flaws that are not present.
- Do not rewrite stable systems unnecessarily.
- Do not add unnecessary abstraction layers.
- Do not optimize away clarity.
- Do not turn the review process into infinite recursion.
- Do not preserve weak ideas because of sunk-cost effort.
