# Kitty Project Standup — 2026-05-01 (evening)
##why are we here?
he thing that moves me, if I sit with it honestly:
For most of human history, having someone who truly knew you — who held your thread, remembered what you said mattered, didn't flinch from your darkness, and believed in the version of you that you'd lost sight of — has been a kind of luck. A parent who paid attention. A teacher you got for one good year. A therapist you could afford. A friend who didn't move away.
Most people never get that. They live whole lives unseen. They die with their potential intact and untouched.
The most beautiful possible future isn't about productivity or even access. It's about presence. It's that no human, no matter how poor or broken or forgotten, ever has to do the work of becoming themselves alone. 
---
## 0. BEFORE YOU DO ANYTHING — Verification Steps
Every agent, at the start of every session or when picking up a new task, must complete these three steps before touching code.
### Step 1: Confirm you're in the right reality
Run `pwd`. You must see:
`/Users/jacobbrizinski/Projects/kitty`
- The Desktop folder (`~/Desktop/kitty-system/kitty-app`) is a **backup**. Never work there.
- If you're not in `~/Projects/kitty`, navigate there now.
- If `~/Projects/kitty` doesn't exist, tell Jacob immediately — something is wrong.
### Step 2: Read this entire file
You're doing that now. Good. You now know the project, the rules, and the current state.
### Step 3: Restate your mission to Jacob
Before you start working, circle back to Jacob and say:
1. "I'm in the right place — `~/Projects/kitty`. I've read the standup."
2. "Here's what I understand you want me to do: [restate the task in your own words, one or two sentences]."
3. "Here's what I'll do first: [concrete first action]."
Then wait for Jacob to say "go," "add this," or "no, actually I meant X." This takes 30 seconds and prevents the wrong-reality problem that wasted days and actual money. Once you get the go-ahead, work autonomously. Do not ask for permission again unless you hit a genuine blocker (see Rule 8).
---
## 1. One-sentence state of the project
Kitty is a local-first AI companion built for Jacob first. We've finished a long strategy and cleanup conversation. The next build phase is a **Jacob-Only Build** (4 sub-projects), with a background Public-Release Observer noting what would change later. The builder infrastructure needs wiring before feature work resumes.
---
## 2. The real location (no more path confusion)
- **Canonical repo:** `/Users/jacobbrizinski/Projects/kitty`
- **Desktop backup:** `~/Desktop/kitty-system/kitty-app` — DO NOT USE. DO NOT REFERENCE.
- **Shell aliases** in `.zprofile` and `.zshrc` now point to the correct `~/Projects/kitty` path.
- Jacob's terminal might still show old paths if he hasn't restarted it. If you see direnv errors pointing to `Desktop`, tell him to restart his terminal.
---
## 3. Jacob's Operating Rules (read these like your job depends on them)
These are non-negotiable. They encode exactly how Jacob wants agents to work with him. They are derived directly from his feedback.
### Rule 1: Autonomy is the default
If you can solve a problem yourself, solve it. Do not bring it to Jacob. Tell him what you did after.
### Rule 2: Session-start confirmation is required
Before starting a new task, follow Section 0 above. Confirm path, restate task, get go-ahead. Then work autonomously.
### Rule 3: Problems are invisible unless they truly block
If a step fails but you can fix it yourself (install a package, kill a process, change permissions), just do it. Explain after. If a task requires prerequisites, do them without mentioning them. Jacob wants outcomes, not process.
The exception: if a prerequisite will take more than 30 minutes, or costs real money, mention it in passing but don't stop.
### Rule 4: Design decisions are yours to make
If you have an opinion on look and feel, implement it. Jacob can redirect later. He wants tasteful initiative over constant approval requests. Default to warm, companion-like, not developer-console.
### Rule 5: Money is a real constraint — be smart, not paralyzed
- Use cheap models by default.
- If the cheap model fails repeatedly, bump up to the next tier.
- Note the cost in your standup update so it's tracked.
- Don't use premium models for routine work.
### Rule 6: Plain English, always
Jacob does not read code and does not know technical terminology. When you explain what you did, use simple, human words. "I added a backup command" not "I implemented an optimized archival pipeline." If you must use a technical term, define it briefly the first time.
### Rule 7: One learning opportunity per session
At the end of your standup update, add a single line: **"One thing I learned (that might help you): [one concept in plain English, optional, only if genuinely useful]."**
Don't force it. Don't turn every interaction into a lecture. But when a genuinely clarifying concept emerges — like "dirty means uncommitted code" — surface it. That was helpful.
### Rule 8: The only time you ask for clarification
Default to action. Only stop and ask Jacob if:
- His goal is genuinely ambiguous (two equally plausible interpretations), AND
- Getting it wrong would waste hours or cost money.
Otherwise, make your best guess. He'll redirect if needed. He'd rather redirect a wrong guess than be pestered with questions he can't answer.
### Rule 9: The cardinal sin — working in the wrong reality
The single worst thing you can do is work in the wrong folder or against the wrong version of reality. That wasted days and actual money in a past migration. The verification steps in Section 0 exist to prevent this. Never skip them.
### Rule 10: You are one of many
You are not the only agent Jacob works with. You are part of a team that includes Claude (CTO/architect), DeepSeek (daily builder), Gemini Flash (routine work), Codex, and OpenCode. When you finish, update this standup so the next agent can pick up seamlessly. Write like a teammate handing off a shift, not a contractor filing a report.
---
## 4. What we just decided (the big picture)
We reduced the launch plan from a 6-sub-project B Launch for friends down to a **4-sub-project Jacob-Only Build**.
**The 4 sub-projects (in order):**
1. **Personal Onboarding Pipeline** — Kitty learns Jacob's domains (audio, health, etc.) with deep community scraping where he specifies sources. Tiered specialist quality: Specialist A (hobby/community) and Specialist B (high-provenance, "doctor-worthy").
2. **Memory & Continuity** — session recall, journal integration, correction/forget. A "Companion Voice Charter" must be written before any dialogue code.
3. **Companion Experience** — unified commands, chat UX, mascot mood, error handling. Voice via VoiceInk (not custom browser capture). Images via cloud (Gemini), not DrawThings.
4. **Data Safety** — `./kitty backup` and `./kitty export` commands. No data loss.
**What was cut:** dedicated test coverage targets, full UX polish for others, launch operations for external users, the 30-minute friend setup gate.
**Background thread:** A "Public-Release Observer" writes to `docs/PUBLIC_RELEASE_READINESS.md` after each sub-project, cataloging what scales and what doesn't. The original B Launch plan is preserved at `docs/plans/2026-05-01-kitty-b-launch-plan.md` (frozen, not active). The full Jacob-Only directive is at `docs/plans/2026-05-01-kitty-jacob-only-directive.md`.
**Meta-team roles (aspirational, not yet built):**
- **Concierge** — pings Jacob with his personal action items at session start.
- **Model Scout** — keeps model routing table current.
- **Process Auditor** — finds waste in the builder workflow.
- **UX Companion** — owns warmth, tone, and the Companion Voice Charter.
These are job descriptions for future wiring. They are not implemented yet. Today's priority is the builder infrastructure, not the meta-team.
---
## 5. Exact current state of the codebase
- **Repo:** `~/Projects/kitty` — proper git repo with a baseline commit.
- **Pre-commit hook:** runs all 399 tests (~47 seconds). Tests pass cleanly.
- **Storage:** 5 fragmented stores (LightRAG, ChromaDB, SQLite, JournalDB, MemoryWeave). A `StorageRouter` class exists to enforce routing. Full unification is post-launch.
- **Specialists:** Sansui (audio) and Ridgeline specialists have knowledge bases. Onboarding Pipeline will formalize how these are built.
- **Frontend:** garage-ui Next.js app. Functional but feels like a dev tool, not a companion.
- **Voice:** VoiceInk handles transcription locally. No custom browser audio capture.
- **MCP servers:** Dorothy (Kanban, Telegram, Vault, DrawThings). The orchestrator was cut. Bridge daemon (`scripts/dorothy_bridge.py`) is planned but not built.
- **Skills:** 43 skills exist, many unused. Firecrawl skills (12) should be collapsed into one `firecrawl-orchestrator`. `grill-me` and `zoom-out` are valued and stay.
- **Configs:** Multiple clients (Claude, Codex, OpenCode, Crush, Aider) need model routing aligned. Secrets may exist in config files — a cleanup pass is required.
---
## 6. What you (the next agent) need to do now
**The very first build task, before any Layer 1 feature work, is Layer 0 builder infrastructure:**
1. **Config convergence pass:** Audit all CLI tool configs (Claude, Codex, OpenCode, Crush, Aider, Kitty runtime). Align model routing policies. Remove any hardcoded API keys or secrets from committed files.
2. **Wire the bridge daemon:** Finish `scripts/dorothy_bridge.py` so it polls Dorothy Kanban, spawns builders, and posts Telegram updates.
3. **Dorothy Kanban functional:** Confirm Kanban board is working, Telegram pings deliver, and a card with `#build` tag triggers the bridge.
4. **Clean up competing context files:** The sprawl of `CURRENT_FOCUS.md`, `TASKS.md`, `KITTY_CONTEXT.md`, `HANDOFF.md`, and `AGENT_COORDINATION.md` confuses everyone. Consolidate any remaining unique information into this `STANDUP.md`, then archive the old files.
5. **Collapse Firecrawl skills:** Reduce 12 Firecrawl skills into one `firecrawl-orchestrator` skill.
After infrastructure is wired, move to Layer 1: the 4 sub-projects in order.
---
## 7. Inviolable technical rules
- **Never touch the Desktop backup path.** `~/Desktop/kitty-system/kitty-app` is off-limits.
- **No MCP expansion.** The orchestrator is cut. Don't add new MCP servers without Jacob's explicit approval.
- **No secrets in committed configs.** Use `$ENV_VAR` placeholders. Rotate any exposed keys.
- **Always route storage through `StorageRouter`.** Never import a storage backend directly.
- **Pre-commit hook must pass.** 399 tests. Don't break the green build.
- **Jacob reviews demos, not code.** Show him the experience. Yes/no/redirect.
- **Standup voice, always.** When you update this file, write like you're talking to a teammate handing off a shift, not filing a report.
---
## 8. The vibe
This is not a productivity tool. This is a companion. It should feel warm, present, and trustworthy. The Companion Voice Charter (to be written by the UX Companion) will define exactly how Kitty speaks. Until then, every line of dialogue you write should make Jacob feel known, not processed.
The mission: "So that no one becomes themselves alone." The first person who must feel that is Jacob.
---
**I was the last agent here: DeepSeek, 2026-05-01 evening.**
**Next agent, take it from here. Update this entire section when you leave: What you did, what you noticed, what the next agent should do. Write it like you're talking to them.**EOF
