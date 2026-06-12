# Kitty Project Standup — 2026-05-01 (evening)

<!-- HOOK_START -->
## Session hook summary (compact)

**Repo:** `/Users/jacobbrizinski/Projects/kitty` only. Never `~/Desktop/kitty-system/kitty-app`.

**Authority:** Jacob’s live message → `AGENTS.md` → `CLAUDE.md` → `docs/LAYER0_CONTROL_PLANE.md` → `CURRENT_FOCUS.md`. Open `docs/AGENT_COORDINATION.md` only when claiming or overlapping lanes (do not load the whole file for routine work).

**Checks:** `pwd` must show `~/Projects/kitty` before edits. After Python/config/hook changes: `venv/bin/python -m pytest tests/ -q --tb=short`.

**Quick commands (no LLM needed):**
- `./kitty quick status` — server check
- `./kitty quick test` — run tests
- `./kitty quick index <pattern>` — file search
- `./kitty quick health` — API check
- `bash gateway/status_all.sh` — Gateway `:5001` + LiteLLM `:8001` + kitty-chat UI `:3000` health (same triangle as `docs/ARCHITECTURE.md`)

**Stack triangle (one line):** Browser **kitty-chat UI `:3000`** talks to the **Gateway `:5001`** (Kitty’s FastAPI app), which routes models through **LiteLLM `:8001`** (`kitty-*` models).

**Key docs (start here):**
- `docs/UNIFIED_IMPLEMENTATION_PLAN.md` — phased feature roadmap (Phases 1–10)
- `docs/ARCHITECTURE.md` — live stack, ports, gateways, scripts
- `docs/README.md` — doc index / authority order
- Root: `CURRENT_FOCUS.md`, `TASKS.md`, `SESSION_HANDOFF.md` — session state
- Storage & data flow: `docs/DATA_ROUTING.md` (when touching KB/journal/routing)

**Depth:** Voice corpus, Jacob’s rules, runbook, Handoff template — read the rest of this file when needed; hooks send this block only.
<!-- HOOK_END -->

## Doc Map (What Lives Where)
- `docs/STANDUP.md`: current operating reality, rules, and latest concise handoff.
- `SESSION_SUMMARY.md`: recent implementation continuity and verification snapshots.
- `docs/handoffs/HANDOFF-YYYY-MM-DD.md`: dated detailed handoffs and chronology.
- `docs/SESSION_LOG.md`: append-only long-form session history.

## Why are we here?
The thing that moves me, if I sit with it honestly:
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
### Step 2: Read what you need from this file
- **First time today / new task type:** skim **§0** (reality), **§9** (runbook: Handoff + tests + git), then the sections that match your work (**§2** voice corpus, **§3–7** rules and tech).
- **Same session, same topic:** do not re-consume the whole doc every turn — you already have it from **sessionStart** / hooks. Jump to the section you are changing.
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
### Hooks — which tools auto-load this standup?
There is **no single universal hook system** across every AI coding tool. Today Kitty wires **two** native paths:
| Tool | Config file | What happens |
|------|-------------|----------------|
| **Claude Code** (CLI) | `.claude/settings.json` | **SessionStart** runs `scripts/kitty-standup --hook` (compact block between `HOOK_START` / `HOOK_END` in this file). Humans: `kitty-standup` or `standup` prints the **full** standup. **Stop** runs `kitty-standup --reminder`. Type `/hooks` in Claude Code to verify. |
| **Cursor** (Agent / Composer / cloud agents on this repo) | `.cursor/hooks.json` | **`sessionStart` only:** injects the **compact** block from `docs/STANDUP.md` (`<!-- HOOK_START -->` … `<!-- HOOK_END -->`). **`stop` is intentionally not wired** (avoids repeating “§9 Handoff?” after every agent turn). Use **`handoff`** / a **real session end** for §9. |

**Cursor — nag still repeating?** Check **user/global** hooks too: `~/.cursor/hooks.json` sometimes defines a **`stop`** entry. Remove **`stop`** there if you want silence between turns; this repo’s `.cursor/hooks.json` only registers **`sessionStart`**.

**Everyone else** (Codex, Gemini CLI, OpenCode, Goose, Aider, …): usually **no** Claude-compatible hooks. **Easiest habit:** open Terminal and type **`standup`** (one word — a shell alias in Jacob’s `~/.zshrc` that runs `scripts/kitty-standup`). Same as reading this file; no path to memorize. Or point each tool at “read `docs/STANDUP.md` first” in whatever instruction file it respects (varies by product). Folding those into one consistent story is part of **Layer 0 config convergence** (Section 6).

### Terminal vs Cursor / OpenCode / Claude Code — what order?
**No required order.** If you use **Cursor** or **Claude Code** with `~/Projects/kitty` open, hooks inject this standup automatically — you do **not** need to type anything first. **`standup`** in Terminal prints the **same** `docs/STANDUP.md` for you to read — it is not a different document; it’s the same source of truth the hooks use.

### Voice corpus — Jacob’s own words (for style / retrieval later)
This is tractable; no custom ML training or GPUs for a first version.

**Do this first — full iMessage export (all conversations, all sides):** `imessage-exporter` reads `chat.db` directly (including **`attributedBody`** bodies that `build_voice_corpus.py` skips). No conversation filter = **everything**. Output stays under `data/` (gitignored).

1. **Full Disk Access:** **System Settings → Privacy & Security → Full Disk Access** → enable **Terminal** (and **Cursor** if you use its terminal).
2. **Export (TXT, canonical path on this machine):**

```bash
cd /Users/jacobbrizinski/Projects/kitty
mkdir -p data/voice_corpus/imessage_export_full
imessage-exporter -f txt -o data/voice_corpus/imessage_export_full
```

*(Optional: `-s YYYY-MM-DD` / `-e YYYY-MM-DD` to trim dates; `-t name` only if you want **fewer** threads later — for “all messages first,” omit `-t`.)*

**After that — one file: your iMessage lines + Gmail Sent:** `scripts/build_voice_corpus.py` reads **`--imessage-export-dir`** (every conversation `.txt`), keeps only blocks whose sender line is **`Me`**, then appends **Gmail Takeout Sent** `.mbox` bodies. Use **`--skip-imessage`** so you do not double-count SQLite `text` rows.

```bash
cd /Users/jacobbrizinski/Projects/kitty
python3 scripts/build_voice_corpus.py \
  --skip-imessage \
  --imessage-export-dir data/voice_corpus/imessage_export_full \
  --mbox "$HOME/Downloads/Takeout/Mail/Sent.mbox" \
  --out data/voice_corpus/jacob_voice.txt
```

*(Repeat `--mbox` for each extra Sent split file. If you used **`imessage-exporter --use-caller-id`**, pass **`--imessage-sender-label "Your Phone"`** or whatever appears on the second line of each block.)*

**Gmail (Sent only) — browser once:** [takeout.google.com](https://takeout.google.com) → deselect all → Gmail → **Sent only** → export → unzip (example path: **`~/Downloads/Takeout/Mail/Sent.mbox`**).

**SQLite-only path (no exporter yet):** same script without **`--imessage-export-dir`** pulls outbound rows from **`chat.db`** (many modern bodies missing from `text` — exporter path above is better).

```bash
cd /Users/jacobbrizinski/Projects/kitty
python3 scripts/build_voice_corpus.py --out data/voice_corpus/jacob_voice.txt
```

**`brew install imessage-exporter`** if the command is missing.

**In Kitty:** Retrieval over **`jacob_voice.txt`** before she writes on Jacob’s behalf lets her echo his phrasing — pattern match against **his** words, not fine-tuning. The **exporter dump** still contains other people in the raw `.txt` files; **`jacob_voice.txt`** built as above is **Me + Sent mail** only.

### Opening the repo in Cursor (human step — agents cannot click menus)
An assistant **cannot** open Cursor or choose **File → Open Folder…** on your machine. Jacob (or anyone at the keyboard) has to open **`/Users/jacobbrizinski/Projects/kitty`** once; after that, project hooks and paths line up. Until then, agents may still run commands against the wrong folder if the workspace root is the Desktop backup — Section 0 matters.
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
- If spend was **material**, note it **once** in the **session-end Handoff** (not every reply).
- Don't use premium models for routine work.
### Rule 6: Plain English, always
Jacob does not read code and does not know technical terminology. When you explain what you did, use simple, human words. "I added a backup command" not "I implemented an optimized archival pipeline." If you must use a technical term, define it briefly the first time.
### Rule 7: One learning opportunity per session
Optional **one line** in the **session-end Handoff** only — **"One thing I learned: …"** — when it would genuinely help the next agent. Skip if nothing landed.
### Rule 8: The only time you ask for clarification
Default to action. Only stop and ask Jacob if:
- His goal is genuinely ambiguous (two equally plausible interpretations), AND
- Getting it wrong would waste hours or cost money.
Otherwise, make your best guess. He'll redirect if needed. He'd rather redirect a wrong guess than be pestered with questions he can't answer.
### Rule 9: The cardinal sin — working in the wrong reality
The single worst thing you can do is work in the wrong folder or against the wrong version of reality. That wasted days and actual money in a past migration. The verification steps in Section 0 exist to prevent this. Never skip them.
### Rule 10: You are one of many
You are not the only agent Jacob works with. You are part of a team (Claude, DeepSeek, Gemini Flash, Codex, OpenCode, …). **Handoff:** see **§9** — **one** short block when the **session** truly ends, when Jacob says **`handoff`**, when you’re **blocked**, or when context is about to **drop**. **Cursor** has **no stop hook**: nothing auto-reminds §9 between turns — that’s intentional (no spam).

### Rule 11: Show your work
Evidence before “done”: tests, diff, command output, or screenshot. **How much test:** see **§9** (full suite for real code; skip or narrow for doc-only STANDUP nits; always full suite before **commit** / CI per `CLAUDE.md`).
### Rule 12: Assume Jacob does not write code for a living
Unless he says otherwise, assume **no** prior comfort with terminals, git, JSON, hooks, or MCP. Same plain English as Rule 6 — outcomes first, jargon only on request with a one-line plain definition.
### Rule 13: Do it first, teach second
If you can run the command, apply the edit, or check the path from this environment, **do it** — then summarize what you did for Jacob. Optional: one short sentence on how he could repeat it himself. **Do not** leave him a pile of manual steps for work you could finish here (same spirit as Rule 1 and Rule 3).
### Rule 14: Homework is copy-paste blocks only
If Jacob must personally do something (browser login, OS permission, one command only he can run), **after** you’ve done everything you can from here: give **one fenced block** he can copy wholesale — command(s), one line on what “good” looks like, optional “if it fails” line. No scavenger hunt through paragraphs.
---
## 4. What we just decided (the big picture)
We reduced the launch plan from a 6-sub-project B Launch for friends down to a **4-sub-project Jacob-Only Build**.
**The 4 sub-projects (in order):**
1. **Personal Onboarding Pipeline** — Kitty learns Jacob's domains (audio, health, etc.) with deep community scraping where he specifies sources. Tiered specialist quality: Specialist A (hobby/community) and Specialist B (high-provenance, "doctor-worthy").
2. **Memory & Continuity** — session recall, journal integration, correction/forget. Keep **`docs/COMPANION_VOICE_CHARTER.md`** aligned as dialogue code lands.
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
- **Pre-commit hook:** runs the full test suite (~40–55s on this machine; **240+** tests at last audit). Keep green before push.
- **Storage:** 5 fragmented stores (LightRAG, ChromaDB, SQLite, JournalDB, MemoryWeave). **`memory_graph`** is the read seam for prompt/search context. Direct backend imports remain OK for writes; a full `StorageRouter` is post-launch.
- **Specialists:** Sansui (audio) and Ridgeline specialists have knowledge bases. Onboarding Pipeline will formalize how these are built.
- **Frontend:** kitty-chat Next.js app. Functional but feels like a dev tool, not a companion.
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
4. **Orientation is intentional:** roadmap → `docs/UNIFIED_IMPLEMENTATION_PLAN.md`; session execution → root `TASKS.md` + `CURRENT_FOCUS.md`; compact handoffs → `SESSION_HANDOFF.md` + `docs/HANDOFF_AND_COMPACT.md`. Coordinating overlapping agents → `docs/AGENT_COORDINATION.md` only when needed (keep entries short).
5. **Collapse Firecrawl skills:** Reduce 12 Firecrawl skills into one `firecrawl-orchestrator` skill.
After infrastructure is wired, move to Layer 1: the 4 sub-projects in order.
---
## 7. Inviolable technical rules
- **Never touch the Desktop backup path.** `~/Desktop/kitty-system/kitty-app` is off-limits.
- **No MCP expansion.** The orchestrator is cut. Don't add new MCP servers without Jacob's explicit approval.
- **No secrets in committed configs.** Use `$ENV_VAR` placeholders. Rotate any exposed keys.
- **Route HTTP handlers through `gateway/routes/`** via `register_routes(app)` in `gateway/app.py`. Keep `app.py` for lifespan, middleware, and `/health` + `/mood` only.
- **Reads for prompt/search context go through `memory_graph`.** Direct backend imports are OK for write paths until StorageRouter exists.
- **Pre-commit hook must pass.** Full `pytest`; don’t ship on red.
- **Jacob reviews demos, not code.** Show him the experience. Yes/no/redirect.
- **Standup voice, always.** When you update this file, write like you're talking to a teammate handing off a shift, not filing a report.
---
## 8. The vibe
This is not a productivity tool. This is a companion. It should feel warm, present, and trustworthy. How Kitty speaks is defined in **`docs/COMPANION_VOICE_CHARTER.md`** (living doc — agents update it as tone evolves). Until then, every line of dialogue you write should make Jacob feel known, not processed.
The mission: "So that no one becomes themselves alone." The first person who must feel that is Jacob.
---
## 9. Agent runbook — speed without sloppiness

**Handoff (bottom of file):** **Max once per real session end** — or when Jacob types **`handoff`** / **`update handoff`**, or you must checkpoint a **blocker** / **crash**. Keep it **≤20 lines**: shipped · one proof line · **3** next steps · optional learning. **Do not** rewrite Handoff with **zero** new repo facts.

**Tests:** touched **Python / hooks / config** → run **`venv/bin/python -m pytest tests/ -q --tb=short`** before claiming done. **Markdown-only STANDUP** → **no** full suite just to “prove” a Handoff. **Always** full suite before **push** (pre-commit).

**Git:** **Commit** small batches so Handoff does not re-paste the same **`git status`** forever. **Never commit** `data/` voice corpus.

**Search:** stay under **`~/Projects/kitty`** (and **`kitty-system`** if Jacob names it) — no unbounded **`$HOME`** globs.

**Why this exists:** Milestone Handoffs = high signal. Per-message Handoffs = expensive noise.

**Open cleanup:** Section 7 **`StorageRouter`** line vs code; optional machine-readable log later.

---
## Handoff _(fill at session end only — rules in §9)_
**Last agent:** Claude Sonnet 4.6, 2026-05-10.
**Shipped:** Phase 17 full — merged to main at `61855b4`. 121 tests passing.
- `gateway/parts.py` — Skeptic/Champion/Pragmatist/Observer, external toggle + auto-trigger
- `gateway/self_review.py` — drift/reaction/session arc logs → `data/kitty/*.jsonl`; auto-writes `config/SOUL_SCRATCHPAD.md` on drift
- `gateway/journal.py` — themed interview openers, prompt generator, synthesis persisted to `data/journal_entries.jsonl`; ambient trigger wired into `/ask`
- `gateway/context_builder.py` — concurrent memory+knowledge fetch, `(soul_prompt, dynamic_context)` tuple, `return_exceptions=True`, `build_worker_context` sync alias for brief.py
- `gateway/paths.py` — LITELLM_BASE/KEY now env-driven, no hardcoded values
- `gateway/app.py` — FastAPI lifespan (no deprecation warnings), body-size middleware, Pydantic models for troubleshoot/tasks/learn endpoints, duplicate routes removed
- `config/SOUL.md` — full behavioral rewrite; `config/SOUL_SCRATCHPAD.md` — two-layer evolution
- `AGENTS.md` — multi-agent coordination protocol + Phase 17 code patterns added
**Proof:** `121 passed, 2 deselected` on main at `61855b4`.
**Cleanup:** Removed all worktrees (phase-17, phase-11-backup, phase-9-pdf) and all stale branches (feature/phase-17, phase-11-backup, phase-9-pdf, parked/mcp-agent-bundle-20260429). Repo is clean — one branch, `main`.
**Dirty:** Clean.
**Next:** 1) Phase 18 candidates: model digest feed, specialist KB training, Honcho weekly mirror. 2) Wire journal into kitty-chat as a named model or shortcut.
**Learning:** Hooks rewrite files mid-session — always re-read before editing. Multi-agent conflict resolved by worktree isolation + AGENTS.md protocol. `brief.py` uses `chat()` not `call_llm()` — patch `gateway.llm_client.chat` in tests.
