---
name: kitty-optimizer
description: >
  Automated token-optimization agent for Kitty. Runs via launchd without invocation.
  Reviews token usage, build logs, project scope, planned vs implemented work. 
  Uses Firecrawl for auto-research. Surfaces actionable feedback to reduce 
  token spend and increase workflow effectiveness. MUST trigger whenever:
  - Jacob mentions "token" or "cost" or "spend" or "wasted"
  - Jacob says "why did that cost so much" or "optimize" or "feedback"
  - A session ends and handoff is written (auto-triggers for post-session review)
  - Jacob explicitly says "run optimizer" or "review tokens"
---

# Kitty Optimizer — Automated Token & Effectiveness Agent

## What This Does

Runs as a **launchd agent** (always-on, no invocation needed). Every time it runs (scheduled or on-demand), it:

1. **Scans** `logs/`, `docs/handoffs/`, git log, and `data/kitty_token_log.jsonl`
2. **Analyzes** token usage patterns, what was planned vs implemented
3. **Researches** better approaches via Firecrawl (auto-enabled)
4. **Produces** actionable feedback: what to stop doing, what to start, how to reduce token spend

## Running As launchd Service

The agent runs as a macOS launchd service. It wakes up on a schedule (every 6 hours) or when triggered by a git commit.

```bash
# After creating the plist (see below), load it:
launchctl load ~/Library/LaunchAgents/com.kitty.optimizer.plist

# Check status:
launchctl list | grep kitty.optimizer

# View recent runs:
tail -20 /tmp/kitty-optimizer.log
```

## First Run: Full Meta-Analysis

When first created, the agent does a **full project meta-analysis**:

1. **Scope review**: reads all docs (STANDUP.md, CURRENT_FOCUS.md, TASKS.md, plan files)
2. **Build log analysis**: reads test outputs, commit history, what passed/failed
3. **Planned vs implemented**: compares plan files with actual commits
4. **Token audit**: reads `data/kitty_token_log.jsonl`, identifies top-cost operations
5. **Actionable feedback**: writes `docs/optimizer/feedback-latest.md`

## Output Format (Token-Optimized)

ALL output goes to `docs/optimizer/feedback-latest.md` in this structure:

```markdown
# Kitty Optimizer Report — YYYY-MM-DD

## Executive Summary
2-3 sentences. What changed. Top finding.

## Token Audit (Top 5 Cost Drivers)
| Operation | Avg Tokens | Frequency | Monthly Cost | Fix |
|-----------|-------------|-----------|--------------|-----|
| ... | ... | ... | ... | ... |

## Planned vs Implemented
| Planned | Status | Gap | Action |
|---------|--------|-----|--------|
| ... | ... | ... | ... |

## Build Health
- Tests: X passed, Y failed
- Last 5 commits: summary
- Blocked items: list

## Actionable Recommendations (Prioritized)
1. [HIGH] Stop doing X — saves ~Y tokens/session
2. [MED] Start doing Y — increases effectiveness by Z%
3. [LOW] Consider Z — nice to have

## Firecrawl Research (Auto-Enabled)
### Finding: Better approach to [topic]
Source: https://...
Recommendation: ...
```

## Using Firecrawl for Auto-Research

The agent has `firecrawl` CLI auto-enabled. When it finds a gap or opportunity, it auto-searches:

```bash
# Inside the agent script, automatically:
firecrawl search "cheapest LLM API 2026 token efficiency" --json -o /tmp/optimizer/research.json
firecrawl search "Claude API pricing per token 2026" --json -o /tmp/optimizer/pricing.json
```

## Running On-Demand

Even though it's launchd-scheduled, you can also trigger manually:

```bash
# Quick token check:
python3 /Users/jacobbrizinski/.agents/skills/kitty-optimizer/scripts/optimizer.py --quick

# Full analysis:
python3 /Users/jacobbrizinski/.agents/skills/kitty-optimizer/scripts/optimizer.py --full

# Focus on specific topic:
python3 /Users/jacobbrizinski/.agents/skills/kitty-optimizer/scripts/optimizer.py --focus "ingestion pipeline"
```

## What Gets Optimized

| Area | What It Checks | Action |
|------|-----------------|--------|
| Token spend | token_log.jsonl, per-call costs | Switch models, batch ops, use cheaper tier |
| Build effectiveness | Tests pass/fail, what was planned | Close gaps, remove dead code |
| Plan execution | Plan files vs git log | Re-align scope, drop stale items |
| Skill usage | Which skills trigger, which don't | Fix descriptions, retire unused |
| Workflow | How tasks flow, where time is wasted | Remove friction, batch operations |
| Research | Auto-Firecrawl for better approaches | Surface cheaper/better alternatives |

## Token-Efficient Design

This skill itself is optimized for low token usage:

- Outputs go to a file, not the conversation
- Uses `jq`/`awk` for JSONL processing (not LLM calls to "summarize this log")
- Firecrawl searches are targeted (1-2 queries per run, not broad sweeps)
- Feedback is prioritized (HIGH/MED/LOW) so Jacob can scan in 30 seconds
- The `--quick` mode runs in <10s, `--full` in <2min

## First-Time Setup

```bash
# 1. Make sure firecrawl CLI is available
which firecrawl || echo "Install: npm install -g firecrawl-cli"

# 2. Create the launchd plist (see scripts/com.kitty.optimizer.plist)
# 3. Load the service:
launchctl load ~/Library/LaunchAgents/com.kitty.optimizer.plist

# 4. Trigger first run manually:
python3 /Users/jacobbrizinski/.agents/skills/kitty-optimizer/scripts/optimizer.py --full

# 5. Check output:
cat /Users/jacobbrizinski/Projects/kitty/docs/optimizer/feedback-latest.md
```

## Manual Trigger Phrases

Even though it runs automatically, you can say:
- "run optimizer" → triggers full analysis
- "quick token check" → `--quick` mode
- "why did that cost $14" → investigates the last expensive operation
- "optimize the ingestion pipeline" → `--focus "ingestion pipeline"`

## Output Location

All feedback → `/Users/jacobbrizinski/Projects/kitty/docs/optimizer/feedback-latest.md`
Run logs → `/tmp/kitty-optimizer.log`
Search cache → `/tmp/optimizer/research-*.json`
