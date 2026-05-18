# Generic Autonomy Tune Skill
---
name: autonomy_tune
description: >
  Tune any AI system's autonomy loop. Identify why it stalls or loops infinitely
  after task completion. Fix the execution flow to reach 80%+ success.
  Works for: kittybuilder, opencode, claude, any agent with a loop.
---

# Autonomy Tune (Generic)

Tune ANY AI system's autonomy loop to reach 80%+ success rate.

## The Problem Pattern

Most AI systems with autonomy loops share this failure mode:

1. **Tool execution WORKS** - model emits tools, they're parsed and executed
2. **TASK COMPLETES** - file created, command ran, goal achieved
3. **LOOP STALLS** - after success, system keeps looping or nudging infinitely

## Diagnosis Protocol

Run the failing task and observe:
```
[Tool Call] write_file(...)
[Tool Result] File created. py_compile: OK.
[Kitty iter 2/8] (model says "Done.")
[Stall Guard] Action required. Please call a tool...
[Kitty iter 3/8] Action required...
❌ STALLED - task done but loop keeps going
```

## Root Causes (common)

| Cause | Location | Fix |
|-------|----------|-----|
| `auto_continue_on_success=True` | chat() default | Set to False |
| No completion detection | after tool success | Check for "Done", "OK", "success" keywords |
| Stall Guard too aggressive | nudges on empty | Only nudge on actual stalls, not post-success |
| Goal verifier logic | post-execution | Exit early if goal passes |

## The Fix Protocol

1. **Identify the loop function** - find where `max_iters` or similar is used
2. **Add exit on success** - after tool success, break before nudging
3. **Test with simple task** - create file, run command
4. **Verify 80%+** - run 6 times, 5+ should exit cleanly

## Test Template

```bash
cd /project/path
echo 'create test_file.py with def test(): print("ok")' | timeout 60 ./system -i
# Watch for: "File created" then clean exit
# Bug shows: "Action required" repeated nudges
```

## Success Criteria

- Simple task completes AND loop exits gracefully
- No repeated nudges after success
- 80%+ success rate (5/6+ passes)