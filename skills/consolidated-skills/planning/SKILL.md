---
name: planning
description: Use when starting any multi-step feature or project that needs structured planning
---

# Planning

Six stages, sequential. Skip only if trivial.

---

## Hard Gate

**No implementation before design approval.** Every project gets at least a short design. Simple projects get short designs; they still get designs.

---

## Stages

1. **Brainstorm & Design** — Explore, question, propose approaches, get approval.
   **Cross-ref:** `brainstorming`

2. **Write Plan** — Bite-sized tasks with real content. No "TBD", no "add appropriate error handling".
   **Cross-ref:** `writing-plans`

3. **Worktree (optional)** — Isolate the feature if you'd be uncomfortable merging half-done.
   **Cross-ref:** `using-git-worktrees`

4. **Execute** — One task at a time (or batch with checkpoints). Each task completes fully before moving on.
   **Cross-refs:** `executing-plans` (inline), `subagent-driven-development` (per-task agents)

5. **Review** — After each task batch or major feature. Fix critical issues immediately.
   **Cross-refs:** `requesting-code-review`, `receiving-code-review`

6. **Finish** — Verify tests pass, then merge locally, create PR, or keep as-is.
   **Cross-ref:** `finishing-a-development-branch`
