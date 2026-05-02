# Kitty Project Standup — 2026-05-01 (evening)
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
### Hooks — which tools auto-load this standup?
There is **no single universal hook system** across every AI coding tool. Today Kitty wires **two** native paths:
| Tool | Config file | What happens |
|------|-------------|----------------|
| **Claude Code** (CLI) | `.claude/settings.json` | **SessionStart** runs `scripts/kitty-standup` (prints full file). **Stop** runs `kitty-standup --reminder`. Type `/hooks` in Claude Code to verify. |
| **Cursor** (Agent / Composer / cloud agents on this repo) | `.cursor/hooks.json` | **sessionStart** injects `docs/STANDUP.md` into context as `additional_context`. **stop** sends a short follow-up nudge to update this file. |

**Everyone else** (Codex, Gemini CLI, OpenCode, Goose, Aider, …): usually **no** Claude-compatible hooks. **Easiest habit:** open Terminal and type **`standup`** (one word — a shell alias in Jacob’s `~/.zshrc` that runs `scripts/kitty-standup`). Same as reading this file; no path to memorize. Or point each tool at “read `docs/STANDUP.md` first” in whatever instruction file it respects (varies by product). Folding those into one consistent story is part of **Layer 0 config convergence** (Section 6).

### Terminal vs Cursor / OpenCode / Claude Code — what order?
**No required order.** If you use **Cursor** or **Claude Code** with `~/Projects/kitty` open, hooks inject this standup automatically — you do **not** need to type anything first. **`standup`** in Terminal prints the **same** `docs/STANDUP.md` for you to read — it is not a different document; it’s the same source of truth the hooks use.

### Voice corpus — Jacob’s own words (for style / retrieval later)
This is tractable; no custom ML training or GPUs for a first version.

**Script in-repo (run from `~/Projects/kitty`):** `scripts/build_voice_corpus.py` — combines **outbound iMessage** (rows where `is_from_me` and the `text` column is filled) and one or more **Gmail Takeout `.mbox`** files into a single UTF-8 text file (default `data/voice_corpus/jacob_voice.txt`, under `data/` which is gitignored).

```bash
cd /Users/jacobbrizinski/Projects/kitty
python3 scripts/build_voice_corpus.py --out data/voice_corpus/jacob_voice.txt
```

**Gmail (Sent only) — you run this in a browser once:** [takeout.google.com](https://takeout.google.com) → deselect all → Gmail → **Include all messages** → switch to **Sent only** → export → download → unzip → pass the path to `--mbox` (repeat `--mbox` if Takeout split files):

```bash
cd /Users/jacobbrizinski/Projects/kitty
python3 scripts/build_voice_corpus.py \
  --mbox "$HOME/Downloads/takeout-XXXX/Mail/Sent.mbox" \
  --out data/voice_corpus/jacob_voice.txt
```

*(Adjust the `.mbox` path to wherever Takeout put it.)*

**iMessage caveats:** Terminal (or Cursor’s terminal) needs **Full Disk Access** to read `~/Library/Messages/chat.db` — **System Settings → Privacy & Security → Full Disk Access** → add Terminal (and Cursor if you run the script from there). Many newer macOS messages store body only in **`attributedBody`** not `text`; those rows are skipped until we add a richer parser — the script prints how many were skipped.

**Optional:** `brew install imessage-exporter` for full HTML/txt exports if you need messages that skip in SQLite.

**In Kitty:** Retrieval over this corpus before she writes on Jacob’s behalf lets her echo his phrasing — pattern match against **his** words, not fine-tuning.

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
### Rule 11: Show your work
When you say you finished something, paste a piece of evidence — test output, file diff, command result, or a screenshot. "Done" without proof doesn't count. This protects Jacob's trust in the team and lets him approve outcomes without reviewing code himself.
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
This is not a productivity tool. This is a companion. It should feel warm, present, and trustworthy. How Kitty speaks is defined in **`docs/COMPANION_VOICE_CHARTER.md`** (living doc — agents update it as tone evolves). Until then, every line of dialogue you write should make Jacob feel known, not processed.
The mission: "So that no one becomes themselves alone." The first person who must feel that is Jacob.
---
## Handoff (replace this whole section when you leave)

**Last agent:** Claude (Cursor), 2026-05-02.

**What I did:** Shipped `scripts/build_voice_corpus.py` — one text file from **outbound iMessage** (`is_from_me` + `text` column) + **Gmail Sent** Takeout `.mbox` (strips `>` quote lines). Documented in Section 2 with copy-paste; ran a local test: **463** iMessage lines included, **22,890** skipped (attributedBody-only — expected on newer macOS). **Committed** `f0549a2`.

**Next agent:** Optional: parse `attributedBody` or merge `imessage-exporter` output for full iMessage coverage. Wire `data/voice_corpus/jacob_voice.txt` into retrieval when Memory work starts.

**One thing I learned (optional):** One doc (`standup` / hooks) and one script name beat long explanations.
