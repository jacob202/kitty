---
name: planning
description: Use when starting any multi-step feature or project that needs structured planning
---

# Planning

End-to-end planning workflow covering the full lifecycle from idea to merged feature.

---

## Stage 1: Brainstorming & Design

**No implementation before design approval. Hard gate.**

### Design Flow (9 Steps)

1. **Explore project context** — check files, docs, recent commits
2. **Offer visual companion** (if visuals will help) — own message, no other content
3. **Ask clarifying questions** — one at a time, understand purpose/constraints/success criteria
4. **Propose 2-3 approaches** — with trade-offs and your recommendation
5. **Present design** — in sections scaled to complexity, get approval after each
6. **Write design doc** — save to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
7. **Spec self-review** — check for placeholders, contradictions, ambiguity, scope
8. **User reviews written spec** — wait for approval before proceeding
9. **Transition to writing-plans** — the only skill invoked after brainstorming

### Hard Gate

Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it.

**Anti-pattern:** "This is too simple to need a design." — Every project goes through this process. Simple projects get short designs, but they still get designs.

**Cross-refs:** `brainstorming` (full 9-step procedure with flow diagram)

---

## Stage 2: Writing Implementation Plans

**Bite-sized tasks. Complete code. No placeholders.**

### Scope Check

If the spec covers multiple independent subsystems, it should have been broken into sub-project specs during brainstorming. If it wasn't, suggest breaking into separate plans.

### File Structure

Before defining tasks, map which files will be created/modified and what each one does. Design units with clear boundaries and well-defined interfaces.

### Bite-Sized Tasks

Each step is one action (2-5 minutes):
- *"Write the failing test"* — step
- *"Run it to make sure it fails"* — step
- *"Implement the minimal code to make the test pass"* — step
- *"Run the tests and make sure they pass"* — step
- *"Commit"* — step

### No Placeholders Rule

Every step must contain the actual content an engineer needs. Never:
- "TBD", "TODO", "implement later"
- "Add appropriate error handling" (without specifics)
- "Similar to Task N" (repeat the code)
- Steps that describe what to do without showing how

**Cross-refs:** `writing-plans` (task structure, self-review checklist, header format)

---

## Stage 3: Worktree Isolation (Optional)

**Create isolated feature workspaces when working on multiple features.**

- Keeps branches independent
- Allows parallel feature work
- No risk of interleaving changes

**Cross-refs:** `using-git-worktrees` (creation, management, cleanup)

---

## Stage 4: Execution

**Execute the plan using disciplined workflows.**

After saving the plan, choose execution approach:

- **Subagent-Driven (recommended):** Fresh subagent per task + two-stage review. Fast iteration, isolated context.
- **Inline Execution:** Execute in current session with batch checkpoints for review.

**Cross-refs:** `executing-plans` (inline batch execution), `subagent-driven-development` (per-task subagent dispatch), `requesting-code-review` (review between tasks/batches)

---

## Stage 5: Code Review

**Review early, review often.**

### When to Request

- After each task in subagent-driven development
- After completing major feature
- Before merge to main
- When stuck (fresh perspective)

### Act on Feedback

- Fix Critical issues immediately
- Fix Important issues before proceeding
- Note Minor issues for later
- Push back if reviewer is wrong (with reasoning)

**Cross-refs:** `requesting-code-review` (full procedure, code-reviewer subagent dispatch), `receiving-code-review` (when you're the reviewee)

---

## Stage 6: Finishing the Branch

**Verify tests → Present options → Execute → Clean up.**

### The 4 Options

1. **Merge back to base branch locally** — switch to base, pull latest, merge, verify tests, delete feature branch, clean up worktree
2. **Push and create Pull Request** — push branch, create PR with gh, keep worktree
3. **Keep branch as-is** — preserve everything, no cleanup
4. **Discard this work** — typed confirmation required, force-delete branch, clean up worktree

### Pre-Flight Check

Always verify tests pass before presenting options. Never proceed with failing tests.

**Cross-refs:** `finishing-a-development-branch` (full procedure for each option, cleanup details)

---

## Quick Reference

| Stage | Key Activity | Output |
|-------|-------------|--------|
| 1. Brainstorm | Explore, question, design, approve | Design doc |
| 2. Write Plans | Decompose into tasks, no placeholders | Implementation plan |
| 3. Worktree | Isolate feature workspace | Git worktree |
| 4. Execute | Subagent or inline per-task implementation | Working code, tests passing |
| 5. Review | Code review between tasks/batches | Issues addressed |
| 6. Finish | Test → option → cleanup | Merged, PR'd, or preserved |

## Design Notes

This skill is an **overlay layer** — it references existing skills as deep-dive resources, not replaces them. Existing skills remain available for standalone use when you need to go deep on one stage.

Stages are sequential but flexible: simple features may skip worktree isolation (Stage 3). Tiny fixes may jump straight to execution (Stage 4). The hard gate at Stage 1 (no implementation without design approval) is non-negotiable.
