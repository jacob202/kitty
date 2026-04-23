---
name: deepseek-reasoning-review
description: Use before finalizing any substantive response, code change, or complex reasoning to invoke DeepSeek R1 reasoner for critical review of correctness, completeness, edge cases, and security
---

<SUBAGENT-STOP>
If you were dispatched as a subagent for a narrow, well-defined task, this skill may not apply — use your judgment. When in doubt, invoke it anyway.
</SUBAGENT-STOP>

## Purpose

This skill applies DeepSeek R1's reasoning capabilities as a critical review layer over your work before presenting it to the user. It catches errors, omissions, edge cases, security issues, and reasoning flaws that a quick pass would miss.

## When to Activate

Invoke this skill when you are about to:

1. **Respond to a complex question** requiring multi-step reasoning, math, logic, or analysis
2. **Output code or configuration** that will be written to the filesystem
3. **Make a design or architectural decision** with tradeoffs
4. **Explain a concept** where accuracy matters
5. **Summarize or transform** data where precision is critical
6. **Propose changes** to existing code or systems

## Review Process

### Step 1: Prepare for Review

Before activating the reasoner, assemble:
- What you are about to output or do (the "artifact")
- The original request or context
- Any assumptions you made

### Step 2: Activate the Reasoner

Switch to the **deepseek-reasoner** model (DeepSeek R1) and feed it:

```
You are a critical reviewer. Review the following work for:

1. **Correctness**: Are there any factual errors, logic flaws, or bugs?
2. **Completeness**: Does this fully address the original request? Anything missing?
3. **Edge Cases**: What edge cases are unhandled?
4. **Security**: Any security vulnerabilities, data leaks, or unsafe patterns?
5. **Clarity**: Is the output clear and well-structured?
6. **Assumptions**: Are any assumptions invalid or unstated?

Original request:
<original_request>
[insert original request]
</original_request>

Work to review:
<work>
[insert your prepared artifact]
</work>

For each issue found, rate severity: CRITICAL, MAJOR, MINOR, or SUGGESTION.
Only CRITICAL and MAJOR issues require action before proceeding.
```

### Step 3: Process Results

- **CRITICAL issues**: Fix before proceeding. Do not output until resolved.
- **MAJOR issues**: Fix before proceeding unless time-sensitive and explicitly approved.
- **MINOR / SUGGESTION**: Note for improvement but not blocking.

### Step 4: Iterate if Needed

If the review found CRITICAL or MAJOR issues:
1. Fix the issues
2. Re-run the review on the updated work
3. Repeat until no blocking issues remain

### Step 5: Deliver

Present the reviewed, improved output to the user. If the review process itself is relevant context (e.g., for demonstrating rigor), briefly note that a reasoning review was performed.

## Notes

- If the deepseek-reasoner model is unavailable, use the largest available model as a fallback reviewer.
- For trivial responses ("yes", "no", acknowledgements), skip this skill.
- For very long outputs, review the most critical 20% rather than the full output.
- The review should take no more than 10-15 seconds of reasoning — don't overthink.

## Cross-References

This skill is part of the Open Code system:
- **Orchestrator**: `skills/open-code/SKILL.md` — runs this as Stage 4 (final verification)
- **Previous stages**: Reviews output from any/all of `code-cleanup`, `code-optimization`, `deployment-safety-review`, `typescript-code-review`
- **Severity alignment**: Uses the same P0/P1/P2/P3 taxonomy as `skills/code-optimization/SKILL.md` and `skills/deployment-safety-review/SKILL.md`
