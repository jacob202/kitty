---
date: 2026-06-20
topic: Workflow Optimization Rollout (15 items)
status: PARTIALLY_IMPLEMENTED
---

# Plan — 15 workflow optimizations, sequenced

Rolls out all 15 ideas from the brainstorm. Grouped by dependency and ROI so
nothing blocks behind a decision. Each item: what it does, files touched,
effort, dependencies, risks, exit criteria.

## Status (as of 2026-06-24)

Tracked against the commit log + `git status`. "Done" means the work landed;
"Partial" means some parts landed; "Pending" means not started in this branch.

| # | Item | Status | Where |
|---|------|--------|-------|
| 1.1 | Dotfiles repo for `~/.claude/` | Done | Prior session (out-of-repo) |
| 1.2 | Handoff doc lifecycle cleanup | Partial | `.claude/HANDOFF.md` removed; catchup SKILL not yet updated |
| 1.3 | Project profile lazy-loader | Partial | `.claude/profile.md` + `settings.json` wired in `f15697d` |
| 2.1 | Cost circuit-breaker hook | Pending | — |
| 2.2 | Voice glossary in CLAUDE.md | Done | `f15697d` |
| 2.3 | `/spike` skill | Pending | — |
| 3.1 | Daily morning brief | Pending | — |
| 3.2 | MEMORY.md auto-prune | Partial | `docs/memory-stale.md` exists; cron not yet wired |
| 3.3 | Self-improving skill loop | Partial | `docs/skill-improvement-queue.md` exists; script not yet written |
| 3.4 | Migration audit cron | Done | `cd23197` |
| 4.1 | Test-failure → ticket auto-creator | Pending | — |
| 4.2 | GitHub Action: PR description checker | Done | `f480677` |
| 4.3 | macOS `mods` integration | Partial | `f480677` mentions "mods" |
| 4.4 | iOS Shortcut to send Kitty a note | Partial | `gateway/inbox_watcher.py` in `81262c4` |
| 4.5 | Apple Watch kitty status glance | Done | `81262c4` + `GET /status/glance` |

**Net status:** 5 done, 6 partial, 4 pending. The deepening program is now the
priority; remaining items will be picked up after Phase 6.

**Total estimated effort:** ~4-6 hours done well, ~2-3 hours quick-and-dirty.

---

## Phase 1 — Foundation (unblocks others, 45 min)

These come first because every other phase touches files they touch.

### 1.1 Dotfiles repo for `~/.claude/` (item #11) — 10 min

- `cd ~/.claude && git init`
- `.gitignore`: secrets, cache, sessions, telemetry, statusline-debug.json, security_warnings_state_*.json, *.bak
- Initial commit with the cleaned-up state
- Push to a private GitHub repo (`jacob-brizinski/dotclaude` or similar)

**Files**: `~/.claude/.gitignore`, `~/.claude/.git/`
**Effort**: 10 min
**Risk**: secrets in stats-cache or telemetry — must audit before first push
**Exit**: clone on a fresh machine restores full Claude Code config in 60s

### 1.2 Handoff doc lifecycle cleanup (item #3) — 10 min

Decide on ONE handoff path and stick with it. Right now you have:
- `docs/AGENT_HANDOFF.md` (committed, multi-session continuity)
- `.claude/HANDOFF.md` (project-local, per-session, in `.gitignore`)

**Decision needed from you**: keep both with distinct roles (committed = sticky decisions, local = working state), or collapse to one?

**Recommendation**: keep both, but rewrite the catchup skill so it explicitly explains the split. Add a one-line comment to each.

**Files**: `docs/AGENT_HANDOFF.md` header note, `~/.claude/skills/catchup/SKILL.md` clarification
**Effort**: 10 min
**Exit**: catchup output cleanly distinguishes "long-term context" vs "in-flight state"

### 1.3 Project profile lazy-loader (item #6) — 25 min

Port the aurakit profile concept to clean English at `~/.claude/hooks/load-profile.sh`:

- On SessionStart, look for `$CWD/.claude/profile.md` (or `$CWD/CLAUDE.md` as fallback)
- If found, echo a one-line summary: project name, primary language, recent activity area, one open question
- If missing, suggest running `/scout-profile` to generate one (would be a new skill, deferred)

Write the initial kitty profile manually to seed the pattern.

**Files**: `~/.claude/hooks/load-profile.sh`, `~/Projects/kitty/.claude/profile.md`, `~/.claude/settings.json` (wire hook)
**Effort**: 25 min
**Exit**: opening a fresh session in kitty echoes a 3-line orient block

---

## Phase 2 — Quality of life (90 min, do same day as Phase 1)

### 2.1 Cost circuit-breaker hook (item #4) — 20 min

PreToolUse hook that reads session token usage from the harness JSON and emits a warning when usage > 80%:

- `~/.claude/hooks/budget-warn.sh`: reads `CLAUDE_SESSION_USAGE_PCT` env var if exposed, else parses from `.statusline-debug.json` (already exists)
- If >80% and no warning fired this session, echo `[budget] 80%+ used — /ship to wrap, /catchup handoff to save state`
- Idempotent within a session (flag file in `/tmp/`)

**Files**: `~/.claude/hooks/budget-warn.sh`, `~/.claude/settings.json` hooks block
**Effort**: 20 min
**Risk**: env var availability — fall back to parsing the debug JSON
**Exit**: cross the 80% threshold in a test session → see the warning once

### 2.2 Voice glossary in CLAUDE.md (item #1) — 15 min

Add a `## Voice Glossary` section to `~/Projects/kitty/CLAUDE.md` mapping spoken shorthand to actual paths/symbols:

```markdown
## Voice Glossary
- "the gateway" → gateway/
- "the chat thing" / "the UI" → gateway/kitty-chat/
- "the agent" → gateway/agent.py
- "the storage thing" → gateway/storage_router.py + gateway/memory_graph.py
- "the routing thing" → gateway/llm_client.py
- "phase B" → docs/PHASE_B_PLAN.md (current focus)
- "Goose" → external chat tool, not part of kitty runtime
- "Honcho" → external mirror service for weekly summaries
```

**Files**: `~/Projects/kitty/CLAUDE.md`
**Effort**: 15 min
**Exit**: voice-dictated "fix the agent" routes you to gateway/agent.py without correction

### 2.3 `/spike` skill (item #8) — 30 min

New global skill at `~/.claude/skills/spike/SKILL.md`. Compresses worktree → experiment → keep-or-discard into one ritual:

- `/spike "try X"` → creates worktree `feat/spike-<kebab>`, opens shell there
- On exit (Stop event), the skill detects: did anything get committed?
  - Yes → suggest `/ship`
  - No → suggest `/worktree clean feat/spike-<kebab>` (auto-yes after timer)
- Adds a `## Flow` line: this is the casual experiment path, no plan/spec required

**Files**: `~/.claude/skills/spike/SKILL.md`
**Effort**: 30 min
**Dependencies**: existing `/worktree` (already done)
**Exit**: `/spike` end-to-end run leaves no orphan worktree

### 2.4 Cleanup decision point — 25 min

Before moving to Phase 3, run `/audit` on the changes from Phase 1+2 to catch
mismatches. Commit. Push the `~/.claude/` dotfiles repo with phase 1+2 state.

---

## Phase 3 — Automation rituals (set + forget, ~2 hours total)

### 3.1 Daily morning brief (item #5) — 45 min

**Decision needed from you**: delivery channel.
- Email (Gmail SMTP — simple, no extra app)
- Telegram (you have an MCP for it, currently dead — could revive)
- macOS Notification Center (no setup but ephemeral)
- Email + write to `docs/MORNING_BRIEF.md` (most resilient — kitty can ingest it)

**Recommendation**: write to `~/Documents/morning-brief.md` AND macOS notif. Both ephemeral and persistent.

Script at `~/.claude/scripts/morning-brief.sh`:
- 8am via launchd plist (more macOS-native than cron)
- Pulls: open PRs (`gh pr list --author @me`), failing CI (`gh run list --status failure`), top 3 TODO from latest handoff, top 5 lines from `docs/PHASE_B_PLAN.md`'s "next" section
- Writes structured markdown
- `osascript -e 'display notification ...'` for the alert

**Files**: `~/.claude/scripts/morning-brief.sh`, `~/Library/LaunchAgents/com.kitty.morning-brief.plist`
**Effort**: 45 min
**Exit**: 8am tomorrow → brief lands in Documents/ + Mac notif

### 3.2 MEMORY.md auto-prune (item #2) — 15 min

Weekly skill that scans `~/.claude/projects/-Users-jacobbrizinski-Projects-kitty/memory/MEMORY.md`:
- For each entry, find its file's last-modified date
- Flag any entry whose file hasn't been touched in 60 days
- Generate a markdown list of "stale candidates" with first-line context
- Email/notify or write to `docs/memory-stale.md`

**Files**: `~/.claude/scripts/memory-prune.sh`, launchd plist for weekly
**Effort**: 15 min
**Exit**: weekly review item lands in Documents/ — you skim and delete

### 3.3 Self-improving skill loop (item #15) — 30 min

Weekly `/improve skill` cron on each global skill:
- launchd plist runs `~/.claude/scripts/self-audit-skills.sh` weekly
- Script iterates `~/.claude/skills/*/SKILL.md`
- For each: counts unmotivated MUSTs, line count, presence of `## Flow`
- If any skill exceeds thresholds (>5 bare MUSTs, >250 lines, no Flow), writes a finding
- All findings → `docs/skill-improvement-queue.md`
- Does NOT auto-fix — surfaces to you for `/improve skill <name>` invocation

**Files**: `~/.claude/scripts/self-audit-skills.sh`, launchd plist
**Effort**: 30 min
**Risk**: false positives — keep thresholds conservative
**Exit**: queue gets populated weekly; you fix top entry in 10 min

### 3.4 Migration audit cron (item #14) — 20 min

Builds on Phase B SQLite work. Periodically (weekly):
- Run `python -c "from gateway import db; db.migrate()"` against a test DB
- Verify idempotency by running twice — second run should be no-op
- Check schema_migrations matches files in `gateway/db_migrations/`
- Report to `docs/migration-health.md`

**Files**: `~/Projects/kitty/scripts/migration-audit.sh`, launchd plist
**Effort**: 20 min
**Dependencies**: Phase B branch already merged (DONE per session context)
**Exit**: weekly green check confirms migrations stay safe

---

## Phase 4 — Cross-system (45-90 min each, do over a week)

These touch more than Claude Code — GitHub, iOS, watchOS, etc. Pick whichever you'd actually use.

### 4.1 Test-failure → ticket auto-creator (item #7) — 30 min

Modify `~/.claude/skills/tdd-loop/SKILL.md`:
- On 10-iter escalation OR same-error-3x escalation, in addition to surfacing to user, run `gh issue create`
- Title: `tdd-loop stuck: <test path>`
- Body: failure log, hypothesis, last commit, paste tail of session
- Label: `auto-tdd`, `needs-investigation`

**Files**: skill file + maybe a helper script
**Effort**: 30 min
**Risk**: spam — add a "don't create if open issue exists for same test" check
**Exit**: triggered escalation creates 1 issue; manual re-run doesn't dupe

### 4.2 GitHub Action: PR description checker (item #12) — 45 min

`.github/workflows/pr-description-check.yml`:
- Triggers on `pull_request` opened/edited
- Validates body contains: `## Summary`, `## Test plan`, at least one bullet per section
- Fails CI if missing
- Comments on PR with the missing pieces

**Files**: `.github/workflows/pr-description-check.yml`
**Effort**: 45 min
**Risk**: rigid format — keep checks loose (just header names + 1 bullet)
**Exit**: a PR without these gets a friendly CI failure with instructions

### 4.3 macOS `mods` integration (item #9) — 20 min

`mods` is a TUI LLM CLI (https://github.com/charmbracelet/mods).

- `brew install mods`
- Configure with your Anthropic key
- Add shell aliases:
  - `alias refine='pbpaste | mods "Refine this into expert register: " | pbcopy'`
  - `alias review='pbpaste | mods "Review this for issues: "'`

**Files**: `~/.zshrc` or `~/.config/zsh/aliases.zsh`
**Effort**: 20 min
**Risk**: minimal — these are just shell aliases
**Exit**: copy text → `refine` in any terminal → refined text in clipboard

### 4.4 iOS Shortcut to send Kitty a note (item #10) — 45 min

Voice-trigger inbox.

1. iCloud Drive: create `inbox/` folder
2. iOS Shortcuts app:
   - New shortcut "Tell Kitty"
   - Voice: "Hey Siri, tell Kitty"
   - Action: Dictate text → save to `inbox/YYYY-MM-DD-HHMM.md` in iCloud
3. Kitty side: add a watcher script that processes new files in `inbox/`, ingests to memory_graph, deletes the file
4. Wire watcher into `./kitty up` or a launchd job

**Files**: macOS launchd plist, `gateway/inbox_watcher.py`, iCloud `inbox/` dir
**Effort**: 45 min
**Risk**: iCloud sync latency — typically <30s
**Exit**: voice-trigger "Hey Siri tell Kitty Phase C should use Postgres" → next session catchup mentions it

### 4.5 Apple Watch kitty status glance (item #13) — 60 min

- Gateway endpoint: `GET /status/glance` returns `{phase: "B", tests: "167/167", branch: "main", uncommitted: 0}`
- Expose via Tailscale (already on Jacob's network per CLAUDE.md context)
- Watch face widget options:
  - **Easy**: iOS Shortcut on watch hits the endpoint, displays in Shortcut UI
  - **Polished**: build a tiny SwiftUI widget via Xcode
  - **Free**: use a "smart" generic widget app like Widgetsmith pointing at the endpoint

**Recommendation**: start with the Shortcuts route — 15 min, no Xcode. Upgrade later if you actually use it.

**Files**: `gateway/routes/status.py`, Shortcuts entry on watch
**Effort**: 60 min including SwiftUI, 15 min Shortcuts-only
**Risk**: Tailscale flake — fall back to local-only with a "no connection" state
**Exit**: glance the watch → see phase + test status

---

## Decisions you need to make before execution

| Decision | Options | Default if you say "go" |
|----------|---------|------------------------|
| Handoff doc strategy (1.2) | One path / two paths | Two paths with clear roles |
| Brief delivery channel (3.1) | Email / Telegram / Notif / Drive | Drive + macOS notif |
| Apple Watch route (4.5) | Shortcuts / SwiftUI / generic | Shortcuts (fastest) |
| Dotfiles repo location (1.1) | Private GitHub / GitLab / Codeberg | Private GitHub |
| Skip any items? | — | Default: do all 15 |

---

## Execution order summary

1. **Phase 1 (45 min)**: dotfiles repo, handoff cleanup, profile loader → foundation
2. **Phase 2 (90 min)**: cost hook, voice glossary, `/spike`, audit checkpoint
3. **Phase 3 (~2 hr)**: morning brief, memory prune, self-audit skills, migration audit → automation
4. **Phase 4 (one-per-day)**: tdd-loop tickets, PR action, mods, iOS Shortcut, watch glance

**Sequencing rule**: 1 before 2 before 3 before 4. Within phase, parallel-safe.

## Net effect

After all 15:
- ~25k token savings per session (already done)
- Auto-recovery from compaction (already done)
- Daily brief replaces 15 min/morning of context-rebuilding (~75 min/week saved)
- Voice glossary cuts dictation-correction loops (~5 corrections/session saved)
- Inbox shortcut captures ideas that currently get lost
- Watch glance answers "are tests passing?" without opening laptop
- Self-improving skills compound — skills you write today won't rot

**Cumulative time saved estimate after 1 month**: ~10-15 hours of friction-reduction value vs ~5 hours invested. Net win.
