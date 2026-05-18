# Tune Skill (Generic)
---
name: tune
description: >
  Tune ANY behavior of ANY AI system. Ask user what to change, then do it.
  Works with: opencode, claude, aider, any CLI agent.
  Not tied to any specific tool - just asks and executes.
---

# How to Use

1. Run `/tune`
2. I'll ask: "What do you want to tune?"
3. You say: "make responses shorter" or "add a tool" or "change the loop behavior"
4. I'll find and modify the relevant code
5. Test it works

## Examples

- "Make output JSON not Markdown"
- "Add a count_lines tool"
- "Change the loop to exit faster"
- "Use cheaper model for delegation"

## What I'll Ask

1. Which system? (opencode, claude, kittybuilder, etc)
2. Current behavior?  
3. Desired behavior?
4. How to test?

---

**Just run `/tune` and tell me what you want to change.**