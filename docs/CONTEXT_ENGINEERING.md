# Context Engineering Principles

**Purpose:** Machine-wide context setup for all AI agents (Claude, Codex, opencode, Gemini, Goose).

**Last updated:** 2026-05-17

---

## Philosophy

Context engineering is about **injecting the right information at the right time** without manual intervention. The goal is:

1. **Zero-config session start** - Every agent starts with current context automatically
2. **Dynamic + static separation** - Static rules in files, dynamic state injected via hooks
3. **Compact by default, full on demand** - Session starts compact, handoffs detailed
4. **Universal coverage** - Same context across all agents

---

## Machine-Level Context Files

These files live at `~/` and provide cross-agent context:

| File | Purpose | Size |
|------|---------|------|
| `~/NOW.md` | Current goal, blocker, stop rule | ~100 lines |
| `~/AGENT_CONTEXT.md` | Machine map, tool homes, ports, logs | ~60 lines |
| `~/SKILLS.md` | Coaching rules, learning principles | ~115 lines |
| `~/PARKING_LOT.md` | Deferred ideas (not current task) | varies |

**First-read order:** `NOW.md` → `AGENT_CONTEXT.md` → `SKILLS.md`

---

## Project-Level Context (Kitty)

| File | Purpose | When to read |
|------|---------|--------------|
| `SESSION_HANDOFF.md` | Current state, test count, open work | Session start |
| `CURRENT_FOCUS.md` | Active focus + forbidden work | Session start |
| `docs/STANDUP.md` | Compact block (HOOK_START...HOOK_END) | Session start (auto) |
| `TASKS.md` | Phase checklist | When starting new task |
| `docs/ARCHITECTURE.md` | Stack/infra detail | When touching stack |
| `docs/README.md` | Full doc index | Orientation |

**Never read whole:** `docs/AGENT_COORDINATION.md` (only when claiming lanes)

---

## Hook Infrastructure

### Claude Code

**Config:** `~/.claude/settings.json`

```json
{
  "hooks": {
    "SessionStart": [{ "command": "~/.claude/skills/aurakit/hooks/pre-session.sh" }],
    "Stop": [{ "command": "node ~/.claude/skills/aurakit/hooks/session-stop.js" }]
  }
}
```

**Status:** ✅ Fully wired (aurakit hooks)

---

### Cursor

**Config:** `~/Projects/kitty/.cursor/hooks.json`

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      { "command": ".cursor/hooks/kitty-session-start.sh" }
    ]
  }
}
```

**Status:** ✅ Wired (injects STANDUP compact block)

---

### OpenCode

**Config:** `~/.config/opencode/opencode.json`

```json
{
  "hooks": {
    "sessionStart": [
      { "type": "script", "script": "./plugins/kitty-hook.js" }
    ]
  }
}
```

**Plugin:** `~/.config/opencode/plugins/kitty-hook.js`

**Status:** ✅ Wired (new)

---

### Codex CLI

**Config:** `~/.codex/agent-start.sh` (shell hook)

**Status:** ✅ Wired (new)

---

### Gemini CLI

**Config:** `~/.gemini/hooks/session-start.sh` (shell hook)

**Status:** ✅ Wired (new)

---

## Scripts

### `scripts/session-start`

Universal starter called by all agents.

```bash
# Compact block (default)
session-start

# Full standup
session-start --full

# Handoff summary
session-start --handoff
```

### `scripts/session-handoff`

Generates handoff from current state.

```bash
# Update SESSION_HANDOFF.md
session-handoff

# Save to dated file + current
session-handoff --save

# Print only
session-handoff --print
```

---

## Handoff Protocol

### When to handoff

- Session end (explicit)
- Agent blocked (needs human input)
- Context limit approaching
- Multi-agent coordination (lane change)

### What to include

**Concise mode** (default):
- Files changed
- Test status (pass/fail count)
- URLs/ports verified
- Next action

**Detailed mode** (on request):
- Chronology
- Decisions + rejected options
- Exact files + commit SHAs
- Commands run + output
- Incomplete work + risks
- Next actions

---

## Token Optimization

### Prevention > Compression

- Filter context **before** it becomes a problem
- Use deterministic tools (jq, awk, scripts) for deterministic tasks
- Load only what's needed for current task

### Mandatory practices

1. **Log token usage** → `data/kitty_token_log.jsonl`
2. **Semantic caching** - Dedupe identical completions
3. **Truncation** - ~2K lines / ~50KB cap before sending to model
4. **Local routing** - Cheap models for simple queries
5. **No broad Firecrawl** - Max 1-2 queries, use `scrape()` not `crawl()`

### Quick reference

| Task | Tool |
|------|------|
| Status check | `./kitty status` |
| Count lines | `wc -l file` |
| Parse JSON | `jq` |
| File > 50KB | Trim or chunk |
| Web scrape (1 page) | `firecrawl scrape` |

---

## Verification

Before any agent edits code:

```bash
cd /Users/jacobbrizinski/Projects/kitty
pwd  # Must show ~/Projects/kitty
sed -n '1,120p' AGENTS.md
sed -n '1,120p' docs/STANDUP.md
```

After code changes:

```bash
python -m pytest tests/ -q --tb=short
```

---

## Authority Chain

When conflicts arise:

1. **Jacob's live message** (latest instruction)
2. **AGENTS.md** (canonical agent rules)
3. **CURRENT_FOCUS.md** (active focus)
4. **docs/STANDUP.md** (operating rules)
5. Older handoffs / generic rules

---

## Known Gotchas

- **Wrong folder:** Desktop backup is NOT canonical (`~/Desktop/kitty-system/kitty-app`)
- **Wrong ports:** OpenWebUI `:3001`, LiteLLM `:8001`, Gateway `:5001`
- **Storage routing:** KB → LightRAG, Journal → JournalDB (never swap)
- **TokenCapture:** Never `print()` in backend (leaks to chat)
- **Pre-commit:** Full test suite (~40-55s, 418+ tests)

---

## Maintenance

### Session start (automated)

All agents now auto-inject the HOOK_START...HOOK_END block from `docs/STANDUP.md` via their respective hook systems.

### Session end (automated)

Run `session-handoff` or type "handoff" to generate current state summary.

### Manual verification

```bash
# Check all hooks are wired
ls -la ~/.claude/settings.json
ls -la ~/Projects/kitty/.cursor/hooks.json
ls -la ~/.config/opencode/opencode.json
ls -la ~/.codex/agent-start.sh
ls -la ~/.gemini/hooks/session-start.sh
```

---

## Next Improvements

- [ ] Unified handoff trigger across all agents
- [ ] Auto-save session transcript to `docs/session-logs/`
- [ ] Token usage dashboard
- [ ] Multi-agent coordination dashboard (who's editing what)
