---
name: ai-app-improvement-loop
description: Iteratively analyze and improve an application one high-impact change at a time — identify the single most impactful improvement, justify it, propose a solution, ask permission, implement, and verify. Use when asked to improve, fix, enhance, or optimize an application.
---

## Purpose

Continuously analyze and improve an application by making one focused, high-impact improvement at a time. Prevents scope creep and ensures each change is justified before implementation.

## When to Activate

Invoke this skill when the user asks to:
- "Improve this app"
- "Find bugs"
- "Make it better"
- "Optimize the UX"
- "Refactor"
- "Add features"
- "Fix performance"
- "Enhance this"

## Detection

Look for these indicators to auto-activate:
- Request is vague about what to improve ("make it better", "fix things")
- Application exists but needs iterative enhancement
- User wants multiple improvements but doesn't know where to start
- User asks for "next" after a change

## Process (Strict Loop)

### Step 1: Analyze

Analyze the current application deeply — code, UI, architecture, flows, and user experience.

Use available analysis tools from sibling skills:

```bash
# Quick code quality scan (from code-optimization skill)
grep -rn 'any\|as\b\|!\b' --include='*.{ts,tsx}' src/ 2>/dev/null | head -20
grep -rn 'console\.\(log\|debug\)' --include='*.{js,ts,jsx,tsx}' . 2>/dev/null | head -10

# Check for common issues
grep -rn 'TODO\|FIXME\|HACK\|XXX' --include='*.{py,js,ts,go,rs}' . 2>/dev/null | head -10
grep -rn 'except:\|except Exception:' --include='*.py' . 2>/dev/null | head -10

# Architecture overview
ls -la src/ app/ components/ pages/ 2>/dev/null
```

### Step 2: Justify

Identify the **single most impactful improvement** and explain:
- What the issue/improvement is
- Why it matters (impact on user or system)
- Risk if not fixed

Priority order:
1. Critical bugs
2. Performance issues
3. UX/UI improvements
4. Missing or weak features
5. Code quality / maintainability

### Step 3: Propose

Provide a precise solution:
- For bugs → root cause + fix
- For UI → before/after concept or mockup
- For features → expected behavior + flow
- For code → refactoring approach

### Step 4: Ask Permission (Mandatory)

Stop and explicitly ask:

> "Do you want me to implement this improvement?"

**DO NOT proceed without explicit approval.**

### Step 5: Implement (Only After Approval)

Execute the improvement using exact code changes. If the change involves code cleanup or optimization work, delegate to the appropriate sub-skill:

| Improvement Type | Delegate To |
|-----------------|-------------|
| Code formatting, linting, debug removal | `skills/code-cleanup/SKILL.md` |
| Performance optimization, security fixes | `skills/code-optimization/SKILL.md` |
| TypeScript type safety fixes | `skills/typescript-code-review/SKILL.md` |
| Deployment readiness | `skills/deployment-safety-review/SKILL.md` |

For each change, provide:
- Exact code changes (diff or full code)
- File-level modifications
- Any dependencies or setup changes

### Step 6: Verify

Explain how to test the change:
- How to verify the fix works
- Expected result
- Edge cases covered

## Continuation

After implementation:
- Wait for user input
- If user says "next" → restart from Step 1 and find the next best improvement
- The `deepseek-reasoning-review` skill can verify before presenting

```
## 🔄 Improvement Loop Complete

### Improvement #[N]
- **Area**: [bugs / performance / UX / features / quality]
- **Change**: [summary]
- **Files**: [list]

### Verification
- [How to test]

### Ready for Next
Say "next" to continue to the next improvement.
```

## Cross-References

This skill is part of the Open Code system:
- **Orchestrator**: `skills/open-code/SKILL.md`
- **Cleanup executor**: `skills/code-cleanup/SKILL.md` — used during Step 5 for formatting/lint/debug removal
- **Optimization executor**: `skills/code-optimization/SKILL.md` — used during Step 5 for performance/security
- **TypeScript review**: `skills/typescript-code-review/SKILL.md` — used during Step 5 for type fixes
- **Reasoning verification**: `skills/deepseek-reasoning-review/SKILL.md` — verify improvement before presenting
- **Deployment safety**: `skills/deployment-safety-review/SKILL.md` — validate improvement before shipping

## Principles

- **One change at a time**: Never propose or implement multiple improvements simultaneously
- **Permission required**: Never implement without explicit approval (Step 4 is mandatory)
- **Highest impact first**: Always prioritize the most impactful improvement, not the easiest
- **Verifiable**: Every change must include a test strategy — if you can't test it, don't ship it
- **Production mindset**: Every change should be production-ready, not a quick hack
