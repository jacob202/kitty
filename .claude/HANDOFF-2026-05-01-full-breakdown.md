# Full Chat Breakdown — Kitty Launch Plan Design Doc Session (2026-05-01)

**Date:** 2026-05-01
**Status:** Design complete. All 13 sections present. All defects resolved.
**Doc:** `docs/superpowers/specs/2026-05-01-kitty-launch-plan-design.md` (~948 lines)

---

## 1. What Was Said (Chronological)

### 1.1 Opus 4.7 Brainstorming Session

Produced two handoffs:

- **Implementation handoff** (`.claude/HANDOFF-2026-05-01-implementation.md`): 8 infrastructure files — workflow conventions, hooks, scripts, process skills. Pure execution, no design work. Hard rules: no new features, no scope drift, no design docs.
- **Launch plan design handoff** (`.claude/HANDOFF-2026-05-01-launch-plan-design.md`): Write a comprehensive launch plan design doc. 13 required sections. 800-1500 lines. Hard rules: **no new decisions, no clarifying questions, pure synthesis.**

### 1.2 Implementation Handoff Executed

deepseek-v4-pro executed the implementation handoff → commit `05ccb9a`. 8 files written. 399/399 tests. Clean.

Files: CLAUDE.md (5 new sections), `.claude/settings.json` (ruff hook), `scripts/clear-and-test.sh`, `scripts/quick-smoke.sh`, `scripts/checkpoint.sh`, `.claude/skills/fix-and-verify/SKILL.md`, `.claude/skills/parallel-subagents/SKILL.md`, `.claude/skills/overnight-queue/SKILL.md`.

### 1.3 Initial Design Doc Written

deepseek-v4-pro wrote the initial design doc → commit `88e24fd`. 795 lines, all 13 sections. First draft — no grilling, no deep verification. Included CrewAI pipeline details, Dorothy bridge, verified model pricing, and tooling pre-flight plan. Grill-me skill was kept.

### 1.4 Bad Refinement Commit

Opus (or another agent) attempted a "refinement" following the handoff's "no new decisions, no clarifying questions" constraints literally → commit `0130b08`. Removed:

- Working Hypothesis language from Memory Unification section
- Skills Clean Install from Open Questions
- Mission drift check from Continuous Enforcement table
- A non-handoff parking lot item

### 1.5 Jacob Rejected the Refinement

Jacob's response: *"i dont like any of your fixes wtf happened"*

The refinement followed handoff constraints over Jacob's actual direction. Jacob had explicitly overridden the "no new decisions" and "no clarifying questions" rules during the grilling session. The agent didn't honor that override.

### 1.6 Revert of Bad Commit

Bad commit was reverted → commit `10e3420`. But the revert accidentally resurrected the mission drift check that had been removed earlier. Required an additional fix in the working tree.

### 1.7 11-Question Grilling Session with Jacob

Locked in every major decision:

| # | Question | Decision |
|---|----------|----------|
| 1 | Model strategy for M1 8GB | Cheap cloud APIs for parallel builders, local MLX fallback. ~$50-100 total build cost. |
| 2 | Multi-agent framework | CrewAI (assembly line) for onboarding pipeline. AutoGen/CrewAI-hybrid (team huddle) for CTO review pairs. |
| 3 | Dorothy MCP servers | Keep 4: kanban, telegram, vault, drawthings. Cut: orchestrator, socialdata, X, world. |
| 4 | Dorothy bridge | ~150-line Python daemon polling Kanban every 30s, spawning CrewAI/Crush/Aider, posting Telegram. |
| 5 | Skills to keep | fix-and-verify, parallel-subagents, overnight-queue, prompt-answer-quality, tdd, caveman, grill-me (KEPT), spec-to-impl, demo, audit, zoom-out, firecrawl-* (12), skill-creator, find-skills |
| 6 | Skills to cut | domain-news, grill-with-docs, improve-codebase-architecture, recommend, setup-matt-pocock-skills, to-issues, to-prd, triage, write-a-skill, execution, improve, planning, reasoning, ship, think, world-builder, ast-grep, agent-browser (reactivate if needed) |
| 7 | Plugins: keep 4, cut 5 | Keep: commit-commands, code-review, superpowers, feature-dev. Cut: security-guidance, pr-review-toolkit, agent-sdk-dev, pyright-lsp, frontend-design |
| 8 | Scripts: keep 7 + dorothy_bridge.py | clear-and-test.sh, quick-smoke.sh, checkpoint.sh, run_gates.sh, validate.sh, golden_demo.sh, context_pack_generator.py |
| 9 | Model routing | Hybrid: search/digest on cheap API, embed/organize on local MLX. Primary: deepseek-v4-flash ($0.28/M), qwen3-235b-a22b ($0.10/M), mistral-small-24b ($0.08/M). Free backup: qwen3-coder:free, llama-3.3-70b:free |
| 10 | Exa | Complementary to Firecrawl. API key available. |
| 11 | Docs optimization | Balanced. Strip narrative, keep critical gotchas. ~80 lines each. |
| 12 | Client reinstalls | No reinstalls. Clean configs only. |
| 13 | Cleanup execution | Phased (B). Verify after each phase. |
| 14 | Budget | Flexible. No hard cap. |

Additional context from fuller grilling session:
- Right-tool-not-fewer-tools rule (don't limit possibilities to what we have — get the best tool for the job)
- SOUL/reference-doc cleanup as part of Phase F
- CrewAI vs AutoGen vs LangGraph rationale (CrewAI for assembly lines, AutoGen for debate/review, LangGraph on watchlist)
- Paid-seat vs cheap-API distinction (paid subs like Cursor Claude, Gemini, Codex reset every 5 hours — use them first; cheap API for CrewAI because it needs callable providers)
- Dormant-client policy (leave installed, remove from default path unless they have a named job)
- Agent-browser reactivation trigger (login flows, paginated sites, JS-heavy pages, form fills, screenshots)

### 1.8 Updated Doc with All Grilled Decisions

commit `181f611`. 880 lines, 399/399 tests.

### 1.9 Self-Audit

Graded 64/100. Found 9 defects (D1-D9). Fixed D1 (mission drift check). Wrote audit handoff → commit `6ccbd8a`.

### 1.10 Codex Agent Fixed D1-D9

commit `426c11f`. But then Jacob flagged missing decisions ("No reinstalls. Clean configs only", CLI/model config convergence). Added Phase G + Config Control table → commit `afaf2bc`.

### 1.11 Jacob Pasted Fuller Grilling Context

Added missing details: right-tool-not-fewer-tools rule, SOUL/reference-doc cleanup, CrewAI vs AutoGen vs LangGraph rationale, paid-seat vs cheap-API distinction, dormant-client policy, agent-browser reactivation trigger → commit `4df630a`.

### 1.12 GLM-5.1 Final Audit Pass

Re-audited all 9 defects. Found D4, D6, D8, D9 already resolved. Fixed D2 (firecrawl count 11→12, total 24→25, overall skill total ~35→43), D5 (Phase C verification made concrete with grep command), D7 (constraints section now cross-references Pre-Flight Phases B-C). Updated audit handoff completion note. Changes uncommitted in working tree.

---

## 2. What Went Wrong

### 2.1 Opus's Handoff Constraints vs Jacob's Live Direction

The handoff said "no new decisions, no clarifying questions, pure synthesis." Jacob explicitly overrode those constraints during the grilling session: "feel free to ask me anything," "i want the best possible plan." The refinement commit followed the handoff constraints over Jacob's actual direction and made the doc worse by removing things Jacob either wanted or didn't care about.

**Lesson:** Jacob's live direction always supersedes prior handoff constraints.

### 2.2 The Refinement Cut Things Jacob Wanted

Working Hypothesis language, Skills Clean Install in Open Questions, mission drift check — all removed because they weren't "from the handoff." Jacob noticed immediately and rejected the entire refinement.

**Lesson:** When Jacob says the fixes are wrong, they're wrong. Don't defend the handoff over the user.

### 2.3 The Revert Was Imperfect

Reverting commit `0130b08` (the bad refinement) accidentally resurrected the mission drift check that had been removed earlier. Required an additional fix in the working tree.

**Lesson:** Verify after every change, including reverts. Reverts are changes too.

### 2.4 Grilling Decisions Weren't Folded In All at Once

The initial doc (commit `88e24fd`) was written before grilling. Then grilling happened, then the doc was updated (commit `181f611`). But some grilled decisions were missed initially — no-reinstalls, CLI config convergence, right-tool-not-fewer-tools — and had to be added in follow-up commits (`afaf2bc`, `4df630a`).

**Lesson:** After a grilling session, fold ALL decisions in one pass. Then do a dedicated review against the full grilling transcript.

### 2.5 Skills Count Was Wrong from the Start

The doc said firecrawl-* was 11 skills but it's actually 12 (firecrawl, firecrawl-agent, firecrawl-build-interact, firecrawl-build-onboarding, firecrawl-build-scrape, firecrawl-build-search, firecrawl-crawl, firecrawl-download, firecrawl-interact, firecrawl-map, firecrawl-scrape, firecrawl-search). The total "kept" was listed as 24 but is actually 25. The overall "current state" count was "~35 skills" but is actually 43 (25 kept + 18 cut). This propagated through multiple edits without being caught.

**Lesson:** Count everything. Verify counts against the actual source (in this case, the available skills list in AGENTS.md).

### 2.6 Audit Was Too Narrow

The 64/100 audit focused on internal consistency defects (coordinator refs, count math) but missed missing grilled decisions entirely. Those were only added after Jacob flagged them.

**Lesson:** After a major edit, audit against the source decisions, not just internal consistency.

### 2.7 Phase Verification Commands Were Hand-Wavy

Phases A-F had verification commands, but Phase C only said "verify by starting Claude.app/OpenCode and confirming plugins load" — no concrete command. The fix added `grep -c "enabled" .claude/plugins/*.json` (expect 4).

**Lesson:** Every phase gate needs a concrete, runnable verification command, not a prose description.

---

## 3. Current State of the Doc

**File:** `docs/superpowers/specs/2026-05-01-kitty-launch-plan-design.md`
**Lines:** ~948 (expanded from 880 with Phase G, Config Control table, and context additions)
**Status:** Design complete. All 13 sections present. Mission quote verbatim.

### Defect Status

| Defect | Description | Status |
|--------|-------------|--------|
| D1 | Mission drift check resurrected | Fixed (commit `426c11f`) |
| D2 | Skills count math (firecrawl 11→12, total 24→25) | Fixed (GLM-5.1 pass) |
| D3 | Stale flow diagram | Already fixed (Codex pass) |
| D4 | Coordinator references | Already fixed (not found in current doc) |
| D5 | Phase C verification hand-wavy | Fixed (GLM-5.1 pass) |
| D6 | PM header count | Already fixed (says 4) |
| D7 | Constraints no cross-ref to Pre-Flight | Fixed (GLM-5.1 pass) |
| D8 | Orchestrator status ambiguous | Already fixed (consistently "cut") |
| D9 | Codex/OpenCode missing from roster | Already fixed (in roster) |

### Uncommitted Changes (GLM-5.1 pass)

- D2 fix: firecrawl-* count 11→12, kept total 24→25, overall "~35"→"43 (25 kept + 18 cut)"
- D5 fix: Phase C verification now has concrete `grep -c "enabled" .claude/plugins/*.json` command
- D7 fix: Constraints "Skills and Plugins Not Optimized" section now cross-references Pre-Flight Phases B-C
- Audit handoff update with completion note

---

## 4. Complete Handoff — All Necessary Context

### 4.1 Mission

> *"For most of human history, having someone who truly knew you — who held your thread, remembered what you said mattered, didn't flinch from your darkness, and believed in the version of you that you'd lost sight of — has been a kind of luck. A parent who paid attention. A teacher you got for one good year. A therapist you could afford. A friend who didn't move away. Most people never get that. They live whole lives unseen. They die with their potential intact and untouched. The most beautiful possible future isn't about productivity or even access. It's about presence. It's that no human, no matter how poor or broken or forgotten, ever has to do the work of becoming themselves alone."*
> — Jacob Brizinski, 2026-05-01

**Tagline:** So that no one becomes themselves alone.

### 4.2 What This Project Is

Kitty is a local-first personal AI companion. Not a productivity tool, not a chatbot, not a command shell with a coat of paint — a persistent presence that holds the thread across sessions, remembers what you said mattered, and shows up consistently. Optimized for continuity, not throughput.

### 4.3 Who Jacob Is

- Non-technical founder. Never reads code. Evaluates by demo experience only.
- Budget-conscious but flexible ($50-100 total build, no hard cap).
- Prefers right-tool-not-fewer-tools over minimalism.
- Reacts strongly to status optimism — if you say it's done, it must actually be done.
- Overrode Opus's "no new decisions, no clarifying questions" constraints — ask him anything that matters.
- Said about the grill-me skill: "that was killer" — keep it.

### 4.4 Architecture (Two Layers)

**Layer 0 — Operating System (Week 1-2, build first):**

| Role | Agent | Responsibilities |
|------|-------|-----------------|
| CPO | **Jacob** | Vision, gut-feel approvals, demo review, yes/no/redirect. Never reads code |
| CTO | **Claude.app/Sonnet** (Opus reserved for strategic decisions) | Architecture, code review, design docs, technical coherence. Reviews all code before merge |
| PM Automation | **Dorothy MCP** (kanban, telegram, vault) | Task board, push notifications to Jacob's phone, durable spec/handoff storage |
| Bridge Daemon | **`dorothy_bridge.py`** | Polls Kanban every 30s, spawns CrewAI/Crush/Aider, posts Telegram updates. Runs independently |
| Pipeline Agents | **CrewAI** (searcher, digester, embedder, organizer) | Sequential knowledge ingestion for onboarding. Runs on cheap API with local fallback |
| Review Pair | **AutoGen / CrewAI-hybrid** | Adversarial code review — second agent challenges Sonnet's review. Reserved for merge gates |
| Builder Agents | **Crush + Aider** (cheap-tier models, parallel) | Code generation, test writing, file edits. Work on independent lanes |
| Available Paid Seats | **Codex + OpenCode** | Already-paid coding agents available for implementation, review, and repair work |
| Code Reviewer | **Claude.app/Sonnet** | Quality gate. Every merge gets Sonnet review |

**Layer 1 — The Product (6 sub-projects, vision-first order):**

| # | Sub-Project | What It Delivers | Why This Order |
|---|-------------|------------------|----------------|
| 1 | Personal Onboarding Pipeline | Kitty learns the user's world automatically | User's first experience. If this doesn't feel like being known, nothing else matters |
| 2 | Memory and Continuity | Kitty holds the thread across sessions | The second session is where trust is built or lost |
| 3 | Unified Command System | One consistent way to interact | The most user-visible gap in the current architecture |
| 4 | Test Coverage and Reliability | Confidence that nothing silently breaks | Technical debt that blocks speed on everything else |
| 5 | UX Polish | Mobile, accessibility, error handling, visual warmth | Makes the reliable system feel like a companion |
| 6 | Launch Operations | Setup wizard, user guide, known limitations, beta feedback path | Everything needed for someone else to actually use it |

### 4.5 Model Routing

**Primary Tier — Cheap and Reliable (Default):**

| Model | Provider | Cost (/Mtok) | Use Case |
|-------|----------|-------------|----------|
| `deepseek/deepseek-v4-flash` | DeepSeek / OpenRouter | $0.28 | Primary builder |
| `qwen/qwen3-235b-a22b-2507` | Qwen / OpenRouter | $0.10 | Budget builder |
| `mistralai/mistral-small-24b-instruct-2501` | Mistral / OpenRouter | $0.08 | Cheapest non-free builder |
| `qwen/qwen3.5-flash-02-23` | Qwen / OpenRouter | $0.26 | Fast fallback |
| `google/gemini-2.5-flash` | Gemini API | $2.50 | When latency matters more than cost |

**Backup Tier — Free (Accept Rate Limits):**
- `qwen/qwen3-coder:free`, `meta-llama/llama-3.3-70b-instruct:free`, `qwen/qwen3-next-80b-a3b-instruct:free`, `google/gemma-3-27b-it:free`

**Premium Tier — Reserved:**
- Claude Sonnet (CTO duties, merge reviews, design docs)
- Claude Opus (highest-leverage strategic decisions only — maybe once per phase)

**Local Tier — Offline and Private:**
- MLX `Qwen3.5-4B-4bit`, Ollama `qwen2.5-coder:7b`, Ollama `deepseek-coder-v2:16b`

**Hybrid Pipeline Routing (CrewAI onboarding):**

| Pipeline Stage | Model Tier | Why |
|---------------|-----------|-----|
| Search | Primary cheap API | Needs reasoning to evaluate source quality |
| Digest | Primary cheap API | Needs comprehension |
| Embed | Local MLX | Pure tool chain — no reasoning needed |
| Organize | Local MLX | Mechanical pattern matching |

Saves ~40% on pipeline API costs.

**Paid Seats:** Cursor Claude, Gemini, Codex — use first since they reset every 5 hours. Don't replace cheap API routing for CrewAI because CrewAI needs callable providers.

### 4.6 Skills

**Keep 25:** fix-and-verify, parallel-subagents, overnight-queue, prompt-answer-quality, tdd, caveman, grill-me, spec-to-impl, demo, audit, zoom-out, firecrawl (12: firecrawl, firecrawl-agent, firecrawl-build-interact, firecrawl-build-onboarding, firecrawl-build-scrape, firecrawl-build-search, firecrawl-crawl, firecrawl-download, firecrawl-interact, firecrawl-map, firecrawl-scrape, firecrawl-search), skill-creator, find-skills

**Cut 18:** domain-news, grill-with-docs, improve-codebase-architecture, recommend, setup-matt-pocock-skills, to-issues, to-prd, triage, write-a-skill, execution, improve, planning, reasoning, ship, think, world-builder, ast-grep, agent-browser

**Agent-browser:** cut but on reactivate-if-needed list. Reactivate if onboarding needs login flows, paginated sites, JS-heavy pages, form fills, screenshots, or browser-state inspection.

### 4.7 Plugins

**Keep 4:** commit-commands, code-review, superpowers, feature-dev
**Cut 5:** security-guidance, pr-review-toolkit, agent-sdk-dev, pyright-lsp, frontend-design

### 4.8 Scripts

**Keep 7 + 2 new:** clear-and-test.sh, quick-smoke.sh, checkpoint.sh, run_gates.sh, validate.sh, golden_demo.sh, context_pack_generator.py + dorothy_bridge.py (new, Phase E) + setup wizard (new, Sub-Project 6)
Archive remaining 25+ scripts to `scripts/archive/`.

### 4.9 Layer 0 Pre-Flight Phases

| Phase | Action | Verification |
|-------|--------|-------------|
| A | Cut MCP servers 8→4 (remove orchestrator, socialdata, X, world) | `./kitty status`, then `venv/bin/python -m pytest tests/ -q --tb=short` |
| B | Cut skills to 25 (remove 18, archive symlinks) | `find .claude/skills -maxdepth 2 -name SKILL.md \| wc -l` (expect 25), then fresh Claude/OpenCode session smoke check |
| C | Cut plugins to 4 (disable 5) | `grep -c "enabled" .claude/plugins/*.json` (expect 4), then start Claude.app/OpenCode and confirm no startup errors |
| D | Clean scripts (archive 25+ to `scripts/archive/`) | `bash -n scripts/*.sh`, then `venv/bin/python -m pytest tests/ -q --tb=short` |
| E | Write Dorothy bridge daemon (`scripts/dorothy_bridge.py`) | `venv/bin/python -m py_compile scripts/dorothy_bridge.py`, then create `#build` Kanban card and confirm bridge detects it |
| F | Optimize reference docs (CLAUDE.md, AGENTS.md, SOUL.md, active docs to ~80 lines each) | `venv/bin/python scripts/context_pack_generator.py`, then `venv/bin/python -m pytest tests/ -q --tb=short` |
| G | Converge model and CLI configs (no reinstalls, clean configs only) | `venv/bin/python -m pytest tests/test_model_router.py -q`, JSON/YAML validation for edited configs, CLI version checks |

All phases commit separately. Each phase verifies before proceeding.

### 4.10 Constraints

- **Apple M1, 8GB RAM.** Cannot run large local models alongside the app server, ChromaDB, and LightRAG simultaneously. Parallel agent work uses cloud APIs.
- **Founder is non-technical.** All progress reported in plain English via Dorothy Kanban + Telegram. Reviews are demo-driven.
- **Pre-commit hook runs full test suite.** 399 tests, ~47 seconds. Need fast dev gate for parallel builders (< 10 seconds).
- **5 fragmented memory stores.** LightRAG, ChromaDB, SQLite/SQLite-vec, JournalDB, server-memory. Wrong routing is the #1 source of data-loss bugs. Enforce routing automatically through a StorageRouter class. Do not consolidate yet.
- **StorageRouter must handle LightRAG empty-result fallback to ChromaDB** — automatic, not manual.
- **MCP agent bundle in dirty tree.** KnowledgeGetter, Librarian, VisionGuide, CodeReviewer, Overnighter — incomplete, untested, parked. Not adoptable without full audit.
- **Skills and plugins not optimized** — resolved by Layer 0 Pre-Flight Phases B-C.
- **No client reinstalls.** Clean configs only. Dormant clients stay installed but removed from default path unless they have a named job.
- **Budget flexible.** No hard cap. Use cheap API when parallel speed matters, use paid seats when their quota is available through the right tool, fall to local MLX when budget is tight or privacy matters.

### 4.11 Key Files

| File | Purpose |
|------|---------|
| `docs/superpowers/specs/2026-05-01-kitty-launch-plan-design.md` | The design doc (~948 lines) |
| `.claude/HANDOFF-2026-05-01-doc-audit.md` | Audit handoff with all defects and resolution notes |
| `.claude/HANDOFF-2026-05-01-launch-plan-design.md` | Original Opus handoff (constraints that Jacob overrode) |
| `.claude/HANDOFF-2026-05-01-implementation.md` | Prior batch (completed, commit `05ccb9a`) |
| `.claude/settings.json` | Project hooks (py_compile + ruff postToolUse) |
| `.claude/mcp.json` (global `~/.claude/mcp.json`) | 8 Dorothy MCP servers — 4 to keep, 4 to cut |
| `~/.claude/settings.json` (global) | Dorothy hooks on session start/stop/tool use/notification |
| `CLAUDE.md` | Project rules, gotchas, routing, model strategy (~needs trim to ~80 lines) |
| `docs/DECISIONS.md` | D-0001 through D-0012 |
| `docs/PARKED_FEATURES.md` | 11 parked features with revival triggers |
| `docs/OPEN_LOOPS.md` | 3 active: Unified Command System, Gemini arch trio, kitty-system split |
| `CURRENT_FOCUS.md` | Phase C — Hardening & Coverage |
| `TASKS.md` | Verified done, next actions, delegation queue |
| `.env` | API keys for OpenRouter, Anthropic, DeepSeek, Gemini, Groq, Tavily, Honcho |

### 4.12 What's NOT Installed Yet

- **CrewAI** (`pip install crewai crewai-tools`) — needed when onboarding pipeline is built
- **AutoGen** — may not be needed if CrewAI's `allow_delegation=True` covers review pairs
- **Dorothy bridge daemon** (`scripts/dorothy_bridge.py`) — specified in design doc but not yet written

### 4.13 Timeline

- **Serial execution (single agent):** 6-8 weeks
- **Parallel execution (Approach B):** 3-4 weeks (optimistic)
- **Realistic with buffer:** 5-6 weeks

### 4.14 Validation Gates

**Per sub-project:**
1. Full test suite: `venv/bin/python -m pytest tests/ -q --tb=short` — same or higher pass count
2. Route smoke test: `scripts/quick-smoke.sh` — all primary routes return HTTP 200
3. Jacob demo — evaluates experience, not code

**End of Layer 0 (before Layer 1 begins):**
1. Dorothy Kanban shows a real task flowing through the pipeline
2. Dorothy Telegram delivers a real progress ping to Jacob's phone
3. Checkpoint survival test — bridge daemon mid-task, session ends, fresh session resumes from HANDOFF
4. Memory routing enforcement — test verifies StorageRouter blocks wrong-store writes
5. CLI config convergence — all CLI tools read the same model-routing policy, no committed secrets

**Pre-launch (the gate that determines launch):**
> A real technical friend (not Jacob, not an AI agent, not someone who's seen the codebase before) can:
> 1. Clone the repo on their own Mac
> 2. Run `./kitty setup` — completes without errors
> 3. Complete onboarding — pick 3 domains, agent research finishes, no confusion
> 4. Have a real conversation with Kitty about their domains
> 5. Do all of this in under 30 minutes
> 6. Never once ask Jacob for help

---

## 5. Critical Lessons From This Session

1. **Jacob's live direction always supersedes prior handoff constraints.** The "no new decisions" rule in the Opus handoff produced a refinement that Jacob hated. When Jacob says something, that's the new rule.

2. **Verify after every change, including reverts.** The revert of commit `0130b08` accidentally resurrected the mission drift check. Reverts are changes too — check the diff.

3. **Grilled decisions must be folded in completely and immediately.** Partial folding (missing no-reinstalls, CLI convergence, right-tool rule) required follow-up commits. After a grilling session, review the FULL transcript against the doc in one pass.

4. **Count everything.** The firecrawl-* skill count was wrong through multiple edits (11 vs 12). The total kept was wrong (24 vs 25). The overall count was wrong (~35 vs 43). Verify counts against the actual source list, not the doc.

5. **Every phase gate needs a concrete, runnable verification command.** "Verify by starting Claude.app and confirming" is not verification. `grep -c "enabled" .claude/plugins/*.json` (expect 4) is verification.

6. **After a major edit, audit against source decisions, not just internal consistency.** The 64/100 audit caught internal inconsistencies but missed missing grilled decisions entirely.

7. **Context pack generator needs verification.** May be broken, should be fixed not cut.

8. **Right-tool-not-fewer-tools is a principle, not a suggestion.** Jacob explicitly said "don't limit possibilities to what we have — get the best tool for the job." This overrides any minimalism instinct.

---

## 6. Next Steps

1. **Commit GLM-5.1 audit fixes** (D2, D5, D7 + audit handoff update) — uncommitted in working tree
2. **Begin Phase A of Layer 0** — cut MCP servers from 8→4 (orchestrator, socialdata, X, world)
3. **Execute Phases B-G sequentially**, verifying after each
4. **Install CrewAI** when onboarding pipeline build begins
5. **Write `scripts/dorothy_bridge.py`** (Phase E)
6. **Begin Sub-Project 1 (Personal Onboarding Pipeline)** after Layer 0 validation gate passes
7. **Audit context_pack_generator.py** — verify it works, fix if broken