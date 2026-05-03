# Launch Plan Design Doc — Handoff 2026-05-01

**For:** Sonnet 4.6 executing the design-doc write-up.
**Authored by:** Opus 4.7 in brainstorming session, with Jacob's full context.
**Status:** Brainstorming complete. All decisions made. Sections approved. Write the doc.

---

## What You're Doing

Write **one** comprehensive launch-plan design doc for Kitty, capturing every decision made in this brainstorming session. **Pure synthesis, no new design work.** Use the existing decisions, mission, constraints, blessings, and inventory from this handoff.

**Output path:** `docs/superpowers/specs/2026-05-01-kitty-launch-plan-design.md`

After writing, commit. That's the entire job.

---

## Approval Status (Don't Re-Ask)

Jacob already approved every major decision in the brainstorming session:
- ✅ Audience: technical friends, own copy (B-style launch). Future: App Store.
- ✅ Mission anchored to "So that no one becomes themselves alone"
- ✅ Approach B: Vision First (onboarding/memory before architecture)
- ✅ Layer 0 (Operating System) before Layer 1 (Product)
- ✅ Cheap-first model strategy with free as backup
- ✅ Dorothy MCP (Kanban + Telegram) as Jacob-facing PM layer
- ✅ Crush + Aider as parallel free-model worker agents
- ✅ Stack stays as-is for B launch (Flask + Next.js + MLX + LightRAG)

**Do not present approaches, ask clarifying questions, or invoke brainstorming.** All that work is done. Just write.

---

## Mission Anchor (Use Verbatim, Don't Paraphrase)

> *"For most of human history, having someone who truly knew you — who held your thread, remembered what you said mattered, didn't flinch from your darkness, and believed in the version of you that you'd lost sight of — has been a kind of luck. A parent who paid attention. A teacher you got for one good year. A therapist you could afford. A friend who didn't move away. Most people never get that. They live whole lives unseen. They die with their potential intact and untouched. The most beautiful possible future isn't about productivity or even access. It's about presence. It's that no human, no matter how poor or broken or forgotten, ever has to do the work of becoming themselves alone."*
> — Jacob Brizinski, 2026-05-01

Tagline: **"So that no one becomes themselves alone."**

Every section of the design doc should be testable against this mission. Anything that doesn't serve presence, continuity, or being known is out of scope.

---

## Required Doc Structure

The design doc must have these sections, in this order:

### 1. Mission & Origin
- Open with Jacob's mission statement verbatim (above)
- One paragraph on why this product exists
- The tagline

### 2. Launch Definition (Phase B)
- Audience: technical friends with Apple Silicon Macs who can clone a repo and run `./kitty start`
- Form factor: each user runs their own copy locally
- Launch readiness = friend can set up Kitty in < 30 minutes and feel Kitty knows their world by end of day 1
- Future direction (NOT building yet): App Store app with Jacob managing hosted backend

### 3. The Two-Layer Plan
**Layer 0 — Operating System (build first):**
- Jacob's role: Chief Product Officer (vision, demos, yes/no/redirect — never reads code)
- CTO role: Claude Sonnet/Opus — translates vision, owns architecture, reviews everything
- PM layer: Dorothy Kanban (visible board) + Telegram (phone notifications) — replaces manual `AGENT_COORDINATION.md`
- Developer agents: Crush + Aider running cheap/free models in parallel
- Memory unification: collapse the 5 fragmented stores (SQLite, ChromaDB, LightRAG, JournalDB, MemoryWeave) into a coherent strategy
- Stack decision deferred: Flask vs FastAPI evaluated post-launch
- Development workflow: intake → spec (auto-generated) → build → demo → ship

**Layer 1 — The Product (6 sub-projects, vision-first ordering):**
1. **Personal Onboarding Pipeline** — user picks domains, agents go out and collect/digest/embed/organize their world automatically. The "Kitty learns YOU" experience.
2. **Memory & Continuity** — Kitty holds the thread across sessions. Last-time-we-talked recall, journal integration, correction/forget interface.
3. **Unified Command System** — slash commands consolidated into one `CommandEngine` (the most user-visible architecture gap, currently in OPEN_LOOPS)
4. **Test Coverage & Reliability** — route coverage from 28% → 80%+, frontend component tests, integration tests
5. **UX Polish** — mobile, onboarding UI, error states, accessibility basics
6. **Launch Operations** — README rewrite as user guide, `./kitty setup` wizard, beta feedback path, known limitations

**Post-launch (non-blocking):** Tool Runtime + Specialist Runtime (internal architecture, progressive)

### 4. Mission Test for Each Sub-Project
For each of the 6 sub-projects above, a one-sentence test against the mission. Example:
> *Onboarding Pipeline:* "Does this make Kitty feel like it's coming to know you, or like setup?"

### 5. Constraints
- **Hardware:** Apple M1, 8GB RAM. Cannot run large local models alongside the app server. Use Groq/OpenRouter for parallel agents, MLX-small for offline.
- **Founder is non-technical.** All progress reported in plain English via Dorothy Kanban + Telegram. Demo-driven reviews, not PR-driven.
- **Pre-commit hook runs full test suite** (~47s, 399 tests). Slows agent commit cycles. Need a faster dev gate.
- **5 fragmented memory stores** — known data-loss source.
- **MCP agent bundle in dirty tree (KnowledgeGetter, Librarian, etc.)** — exists but unverified, parked.
- **Skills/plugins not optimized** — clean install needed.

### 6. Blessings
- **Free model stack is genuinely good:** OpenRouter free (qwen3-coder, llama-3.3-70b, gpt-oss-120b), Groq free tier, MLX local
- **Cheap models are dirt cheap:** DeepSeek V4 Flash ~$0.001/1K, Gemini 2.5 Flash, Groq paid
- **Dorothy already wired** into Claude Code via hooks: Orchestrator + Kanban + Telegram + DrawThings
- **Telegram = Jacob has phone notifications** for agent progress
- **Crush** runs non-interactively → programmatic parallel agents at zero cost
- **Aider** installed → AI pair programming with any local/cloud model
- **399 passing tests** as the safety net
- **5 API providers** (Anthropic, DeepSeek, OpenRouter, Gemini, Groq, Tavily, Honcho) → resilience
- **deepseek-coder-v2:16b** + **qwen2.5-coder:7b** local via Ollama
- **Whisper via Groq** for fast voice transcription
- **DrawThings** for local image generation

### 7. Model Routing Strategy
**Primary (cheap-and-reliable):** DeepSeek V4 Flash, Gemini 2.5 Flash, Groq paid tier — under $0.01/1K, deterministic.
**Backup (free, accept rate-limits):** OpenRouter `qwen/qwen3-coder:free`, `meta-llama/llama-3.3-70b-instruct:free`, `openai/gpt-oss-120b:free`, Groq free tier.
**Premium (reserved):** Claude Sonnet for architecture/review, Opus for highest-leverage strategic decisions.
**Local (offline/private):** MLX `Qwen3.5-4B-4bit`, Ollama `qwen2.5-coder:7b`.

### 8. Agent Team Structure
- **CTO (Claude Sonnet/Opus)** — architecture, code review, complex synthesis
- **PM Automation (Dorothy Kanban + Telegram)** — Jacob-facing progress
- **Builder Agents (Crush + Aider with cheap-tier models, parallel)** — execution
- **Reviewer (Claude Sonnet)** — quality gate before merge
- **Coordinator (Dorothy Orchestrator)** — routes work between agents
- Jacob's role: review demos, gut-feel approvals, redirect when off-mission

### 9. Timeline
- **Single agent serial:** 6–8 weeks to launch
- **Parallel agents (Approach B):** 3–4 weeks
- Layer 0 first (week 1–2), then Layer 1 sub-projects in vision-first order

### 10. Sub-Project Briefs (one section each, ~150 words)
For each of the 6 Layer 1 sub-projects, write:
- **Problem:** what's missing today
- **Mission anchor:** how this serves "no one becomes themselves alone"
- **Shape:** what gets built (high level, no implementation detail)
- **Done looks like:** concrete deliverable
- **Files likely touched:** rough scope (no exact list — that's spec work, not design)
- **Dependencies:** what must exist first

### 11. Parking Lot (Out of Scope for B Launch)
List from `docs/PARKED_FEATURES.md` and `docs/OPEN_LOOPS.md`:
- KnowledgeGetter MCP Server (deferred — could power Onboarding Pipeline later)
- MCP Agent Bundle (deferred — needs audit)
- Source-grounded Specialist Engine
- Tool Runtime + Specialist Runtime (post-launch)
- Proactive idle nudging
- Audio specialist KB candidate
- Budget Leak Finder (privacy-gated)
- Physical kitty-system split
- QLoRA / fine-tuning
- Kelly bodywork update

For each: one line on why parked + revival trigger.

### 12. Open Questions
Items NOT yet decided that need future answers:
- Flask vs FastAPI migration timing (post-launch)
- Memory unification strategy (post-launch spec needed)
- Whether to pull MCP agent bundle into Onboarding Pipeline or build fresh
- Fast dev gate vs full pre-commit hook (which tests run when)

### 13. Validation Gates
- After each sub-project: full test suite + `scripts/quick-smoke.sh` + Jacob demo
- After Layer 0: Dorothy Kanban shows real tasks; Telegram delivers a real progress ping; one demo task survives a usage-limit cutoff via checkpointing
- Before launch: a friend (technical) can clone repo, run `./kitty setup`, complete onboarding, and have a real conversation with Kitty about their domains in < 30 minutes

---

## Style & Length

- **Length:** target 800–1500 lines. This is a comprehensive design, not a one-pager. Each section gets the depth it needs but no padding.
- **Voice:** plain English, founder-readable. Not engineer-jargon.
- **Format:** GitHub markdown. Tables where they help. Code blocks only for actual commands or file paths.
- **No filler.** No "Furthermore," no "It is important to note," no padding. Every paragraph earns its place.
- **Mission threads through every section.** The reader should feel why each technical choice serves "so that no one becomes themselves alone."

---

## Hard Rules

1. **No new decisions.** Every architectural and product decision is captured in this handoff. Synthesize, don't invent.
2. **No code.** This is a design doc, not implementation. File paths and high-level shapes only.
3. **No clarifying questions to Jacob.** All clarifications were done in the brainstorming session.
4. **Use Jacob's mission verbatim.** Do not paraphrase or shorten the quote.
5. **Reference existing docs by path.** `docs/PARKED_FEATURES.md`, `docs/OPEN_LOOPS.md`, `docs/HANDOFF.md`, etc. — link, don't duplicate.
6. **Stay scoped to B launch.** Mention App Store future in the Launch Definition section only. Do not design for it.
7. **No design-by-committee.** This is one coherent vision, not a compromise of multiple options.

---

## Verification Before Commit

```bash
# 1. File exists at the right path
test -f docs/superpowers/specs/2026-05-01-kitty-launch-plan-design.md && echo "✓ doc exists"

# 2. Mission quote is verbatim (single-line check on the unique opening fragment)
grep -q "For most of human history, having someone who truly knew you" \
  docs/superpowers/specs/2026-05-01-kitty-launch-plan-design.md && echo "✓ mission verbatim"

# 3. All 13 required sections present
for s in "Mission" "Launch Definition" "Two-Layer Plan" "Mission Test" "Constraints" "Blessings" "Model Routing" "Agent Team" "Timeline" "Sub-Project Briefs" "Parking Lot" "Open Questions" "Validation Gates"; do
  grep -qi "$s" docs/superpowers/specs/2026-05-01-kitty-launch-plan-design.md \
    && echo "✓ $s section present" \
    || echo "✗ MISSING: $s"
done

# 4. Length sanity
wc -l docs/superpowers/specs/2026-05-01-kitty-launch-plan-design.md
# Expect 800–1500 lines

# 5. Tests still pass (pre-commit will run them anyway)
venv/bin/python -m pytest tests/ -q --tb=short 2>&1 | tail -3
```

All five checks must pass.

---

## Commit

```bash
git add docs/superpowers/specs/2026-05-01-kitty-launch-plan-design.md

git commit -m "$(cat <<'EOF'
design: Kitty launch plan — vision-first roadmap to B-style friends launch

Comprehensive design doc capturing decisions from the 2026-05-01
brainstorming session.

Mission: "So that no one becomes themselves alone."

Layer 0 (Operating System) before Layer 1 (Product). Layer 1 follows
Approach B — vision-first ordering, with Personal Onboarding Pipeline
and Memory & Continuity ahead of architecture cleanup.

Audience: technical friends running their own copy. Future direction:
App Store with Jacob managing hosted backend.

Model strategy: cheap-first (DeepSeek Flash, Gemini Flash, Groq paid),
free as backup, premium reserved for architecture/review.

Agent team: Claude as CTO, Dorothy MCP as PM layer (Kanban + Telegram),
Crush + Aider as parallel builder agents on cheap models.

Six Layer 1 sub-projects:
1. Personal Onboarding Pipeline (Kitty learns your world)
2. Memory & Continuity (holds the thread)
3. Unified Command System
4. Test Coverage & Reliability
5. UX Polish
6. Launch Operations

This is design, not implementation. Per-sub-project specs come next.
EOF
)"
```

---

## Stop Conditions

Done when:
- File written at `docs/superpowers/specs/2026-05-01-kitty-launch-plan-design.md`
- All 5 verification checks pass
- Commit lands cleanly
- Append a one-line completion note to the bottom of THIS handoff

If you hit a problem:
- Don't expand scope to fix it
- Don't make new design decisions
- Stop, document the blocker here, hand back

---

## Source Material to Reference (Don't Re-Read in Full — Link)

- `docs/HANDOFF.md` — current operational handoff
- `docs/audits/operational-plan-20260430.md` — Phase A–D milestone history
- `docs/PARKED_FEATURES.md` — full parking lot
- `docs/OPEN_LOOPS.md` — active deferred items
- `docs/CAPABILITY_INVENTORY.md` — current advertised surface
- `docs/DECISIONS.md` — durable project decisions
- `docs/plans/2026-04-30-unified-tool-runtime.md` — Tool Runtime track plan
- `docs/plans/gemini-architecture-priorities-2026-04-30.md` — three architecture tracks
- `CLAUDE.md` — project rules (just updated with insights + Codex gold)
- `/Users/jacobbrizinski/.codex/memories/memory_summary.md` — cross-agent user preferences (already harvested into CLAUDE.md)

---

## Completion Log

(Executor: append your line here)

- [x] Doc written
- [x] All 5 verification checks pass
- [x] Committed cleanly

Completion note: 2026-05-01 — fully grilled & committed by deepseek-v4-pro, commit 181f611, 880 lines, 399/399 tests, all 13 sections + CrewAI pipeline + Dorothy bridge + verified model pricing + tooling pre-flight plan. Grill-me skill kept.
