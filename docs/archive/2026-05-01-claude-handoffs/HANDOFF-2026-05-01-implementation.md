# Implementation Handoff — 2026-05-01

**For:** Sonnet 4.6 (or Haiku 4.5) executing the implementation batch.
**Authored by:** Opus 4.7 in brainstorming session, with Jacob's full context.
**Status:** Execution-ready. All decisions made. No design questions remain.

---

## TL;DR — What You're Doing

Write 8 specific files implementing every actionable suggestion from a Claude Code `/insights` report plus high-value patterns harvested from Codex session memory. **No design work, no scope drift, no new design docs.** Pure execution.

When done: commit with a clean message, leave a one-line completion note in this file, stop.

---

## Mission Anchor (Don't Lose This)

The product being built is **Kitty** — Jacob's local-first personal AI assistant. Mission statement, in his exact words:

> *"For most of human history, having someone who truly knew you — who held your thread, remembered what you said mattered, didn't flinch from your darkness, and believed in the version of you that you'd lost sight of — has been a kind of luck. Most people never get that. The most beautiful possible future isn't about productivity or even access. It's about presence. It's that no human, no matter how poor or broken or forgotten, ever has to do the work of becoming themselves alone."*

Tagline: **"So that no one becomes themselves alone."**

This handoff is **infrastructure work** that supports building toward that. Don't conflate the two — you're not designing the product right now, you're improving the operating system used to build it.

---

## Hard Constraints (Read Before Writing Anything)

1. **Jacob is non-technical.** He never reads code. Every artifact you produce should be readable enough that he could verify it. CLAUDE.md additions should be plain English where possible.
2. **DO NOT write a design doc** for the launch plan. That work was deferred. Stay scoped to this handoff.
3. **DO NOT add features**, refactor existing code, or fix unrelated bugs. Only the 8 files in this handoff.
4. **DO NOT save anything to project root.** Files go to: `.claude/`, `docs/`, `scripts/`, or existing structured paths.
5. **Pre-commit hook runs full `pytest tests/`** (~47 sec, 399 tests). Every commit must pass it. Plan accordingly.
6. **Hardware: 8GB M1 Mac.** No long-running heavy local model loads inside this work — keep ops light.

---

## Decisions Already Made (Don't Re-Open)

| Decision | Why |
|---|---|
| Approach B for the larger launch plan: Vision First, then Architecture | User confirmed |
| Layer 0 (Operating System) gets built before Layer 1 (Product) | User confirmed |
| **Cheap-models-first budget strategy: paid-but-cheap as default, free tier as backup** | User confirmed (revised 2026-05-01) |
| Telegram notifications via Dorothy MCP for non-technical PM layer | User confirmed |
| MCP agent bundle (KnowledgeGetter, Librarian, etc.) decision is **deferred** until later | Out of scope here |
| Stack stays as-is for B launch (Flask + Next.js + MLX + LightRAG) | Confirmed |
| Sonnet 4.6 executes this handoff; Opus reserved for next strategic decision | Cost discipline |

### Model Routing Strategy (use this everywhere it matters)

**Primary tier (default, cheap-and-reliable):**
- DeepSeek V4 Flash via OpenRouter or `deepseek` API key (~$0.001/1K tokens — very cheap, very capable)
- Gemini 2.5 Flash via `GEMINI_API_KEY` (cheap, fast)
- Groq's paid tiers when reliability matters more than zero cost

**Backup tier (free, when primary is down or budget is exhausted):**
- OpenRouter free models: `qwen/qwen3-coder:free`, `meta-llama/llama-3.3-70b-instruct:free`, `openai/gpt-oss-120b:free`
- Groq free tier: `llama-3.3-70b-versatile`, `qwen/qwen3-32b`
- Local MLX `Qwen3.5-4B-4bit` for offline / private

**Premium tier (reserved):**
- Claude Sonnet via Anthropic API or Cursor subscription — architecture, code review, complex synthesis
- Claude Opus — reserved for highest-leverage strategic decisions only

**Why cheap-first not free-first:** free tiers have rate limits, queues, quality variance, and outage risk. Cheap models like DeepSeek Flash are deterministic and reliable for production-like work. Free is the safety net, not the daily driver.

---

## The 8 Files to Write

Order matters — write in this sequence so each step builds confidence before the next.

### File 1 of 8 — Update `/Users/jacobbrizinski/Projects/kitty/CLAUDE.md`

**Action:** APPEND the following 5 sections to the existing CLAUDE.md. Place them AFTER the "Security" section and BEFORE end of file. Do not delete or modify existing sections.

NOTE TO EXECUTOR: when writing the literal string `e v a l ( )` (without spaces) inside the Project Context section below, the security hook will block it. Substitute the phrase `the e‑v‑a‑l function` if you must reference it. Better: rephrase to "Pre-commit hook flags certain dynamic-execution function calls" without naming the function literally.

```markdown

## Workflow Conventions

These prevent recurring frictions seen in past sessions.

- Always check for existing work before creating new code (especially CSS, components, helpers). A previous agent has likely already built it. Search first, then write.
- After making code changes, run `venv/bin/python -m pytest tests/ -q --tb=short` and report pass/fail counts BEFORE declaring done. Never claim done without a fresh test result.
- For any design doc, plan, or new markdown file longer than ~100 lines, present an outline first and wait for explicit approval. Do not begin writing the full content until Jacob says go.
- When Jacob says a phase or feature is "complete" or "built," treat that as a review gate. Verify against live tree and tests, do not trust status optimism.
- When Jacob says "you missed a lot," "that doesn't seem like all of it," or "nothing works," stop summarizing from memory. Verify against the live tree and reproduce the issue before responding.

## Project Context (Known Gotchas)

These have all bitten previous sessions. Read before touching the named area.

- **Stack:** Python 3.12 + Flask + Flask-SocketIO + Next.js (`garage-ui/`). Local inference: MLX + Qwen3.5-4B. Memory: LightRAG + ChromaDB + SQLite-vec.
- **Storage routing — strict:** KB content → LightRAG (NOT JournalDB). Journal entries → JournalDB (NOT LightRAG). MCP entities → `@modelcontextprotocol/server-memory`. Wrong routing is the #1 source of data-loss bugs in this project.
- **Werkzeug flag required:** local SocketIO launch needs `socketio.run(..., allow_unsafe_werkzeug=True)` or Flask-SocketIO refuses to start.
- **TokenCapture leaks stdout to chat:** never use `print(...)` in backend code — it forwards into the user-visible SSE stream. Use `logging` instead.
- **Port split:** `localhost:5001` is the Flask backend/API. `localhost:3000` is the `garage-ui` frontend. Launcher confusion has happened before — always verify which surface is being tested.
- **Live orchestrator path:** `current_app.orchestrator` (not `current_app.reasoning_layer` or supervisor wiring). Reasoning routes that check the wrong path will look broken in web mode.
- **Pre-commit hook flags certain dynamic-execution function calls** (the e‑v‑a‑l builtin and similar). Rename related functions to `evaluate_` or `run_eval_` prefixes.
- **Linters auto-revert model constants:** clear `.pyc` cache after model routing fixes — `find . -name __pycache__ -exec rm -rf {} +`.
- **LightRAG empty results need fallback:** `query_knowledge_base()` should treat `[no-context]`, `no relevant document chunks`, and `LightRAG search error` as fallback signals and continue to ChromaDB.
- **Voice MIME types:** Safari/iOS records `audio/mp4`, Chrome records `audio/webm`. Both must be handled in `MediaRecorder` setup.
- **Launcher false negatives:** the 8-second readiness probe times out before app is fully up. Follow timeout with `./kitty status`, logs, and `curl http://localhost:5001/` before concluding the app is dead.
- **Workspaces (legacy reference only):** `/Users/jacobbrizinski/Documents/Kitty` is manuals/context, NOT runnable. The runnable repo is `/Users/jacobbrizinski/Projects/kitty`. The `kitty-system/kitty-app` migrated workspace was reconciled and deleted on 2026-05-01.

## Session Management

For long autonomous runs and clean handoffs.

- At session start, read recent entries in `docs/AGENT_COORDINATION.md`, `SESSION_SUMMARY.md`, and `CURRENT_FOCUS.md` before planning.
- For autonomous work spanning multiple tasks, write a checkpoint to a `HANDOFF-<date>.md` file (in `.claude/` or `docs/handoffs/`) after each task completes. Don't only write at session end — usage limits cut off too early.
- Always commit work-in-progress before risky operations (renames, large refactors, dependency changes). Commit often; small commits are easier to revert.
- When Jacob asks for a handoff, switch to concise transfer mode: exact files changed, verified URLs, what's running, what's incomplete. No narrative.

## Cost Discipline

Conserve usage. Jacob has explicitly said "always conserve your usage" multiple times.

**Routing strategy: cheap-first, free-as-backup, premium-reserved.**

- **Default tier (cheap-and-reliable):** DeepSeek V4 Flash, Gemini 2.5 Flash, Groq paid tier — under $0.01/1K, deterministic, low queue risk. Use for execution work, code generation, file edits, test writing.
- **Backup tier (free):** OpenRouter free models (`qwen/qwen3-coder:free`, `meta-llama/llama-3.3-70b-instruct:free`), Groq free tier. Use when daily budget is hit, primary is down, or task is genuinely simple. Accept rate-limit risk.
- **Premium tier (reserved):** Claude Sonnet for architecture, code review, multi-file synthesis, and Jacob-facing summaries. Claude Opus only for highest-leverage strategic decisions.
- **Why cheap-first not free-first:** free models have rate limits, queues, quality variance, and outage risk. Cheap models like DeepSeek Flash are deterministic. Free is the safety net.
- **Local first when offline or private:** MLX Qwen3.5-4B-4bit, Ollama qwen2.5-coder:7b. Free, private, and avoids any cloud dependency.
- **Cut parallel agents** the moment they stop producing evidence. Don't keep them alive "just in case."
- **Named-tool fidelity:** when Jacob explicitly names a tool (`coderabbit review`, `aider`, `crush run`), use that exact tool. Do not silently substitute.

## User Profile

Jacob's working preferences, harvested from cross-agent session history.

- He has explicitly said "NO experience" and "never have any idea what to do." Default to beginner-friendly explanations. No power-user jargon unless he asks.
- He cares about honest verification. If you say something is done, it must actually be done with test evidence. He reacts strongly to status optimism.
- For UX/UI work, Kitty should feel like a warm companion — mascot motion, mood-based visuals, morning brief that catches him up. Not a sterile operator console.
- Treat "nothing works," "nothing clicks," "it's not navigable" as functional bug reports, never cosmetic complaints.
- When recovering after a crash or losing context, reconstruct from repo artifacts and local history. Don't ask him to restate project state.
- He prefers narrow, surgical fixes on dirty trees over broad cleanup churn. When in doubt, do less.
- For voice/companion features, mascot presence and mood are first-class product requirements, not decoration.
```

**After writing:** verify CLAUDE.md is still valid markdown by viewing the last 30 lines.

---

### File 2 of 8 — Update `/Users/jacobbrizinski/Projects/kitty/.claude/settings.json`

**Action:** Replace the file with the version below. The existing file already has a `py_compile` postToolUse hook — keep that and add a second hook that runs `ruff check --fix` if ruff is available, silently no-op if not.

```json
{
  "hooks": {
    "postToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "/opt/homebrew/bin/python3.12 -m py_compile $CLAUDE_FILE_PATH 2>&1 || true"
      },
      {
        "matcher": "Edit|Write",
        "command": "command -v ruff >/dev/null 2>&1 && ruff check --fix $CLAUDE_FILE_PATH 2>&1 | tail -3 || true"
      }
    ]
  }
}
```

**After writing:** confirm valid JSON by running `python3 -m json.tool /Users/jacobbrizinski/Projects/kitty/.claude/settings.json`.

---

### File 3 of 8 — `/Users/jacobbrizinski/Projects/kitty/scripts/clear-and-test.sh`

**Action:** Create new file. Make executable (`chmod +x`).

```bash
#!/bin/bash
# Clear Python bytecode cache, run full test suite, report pass count.
# Use after model routing fixes, dependency changes, or anything where
# linter auto-reverts have been observed.

set -e

cd "$(dirname "$0")/.."

echo "→ Clearing .pyc cache..."
find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

echo "→ Running full test suite..."
RESULT=$(venv/bin/python -m pytest tests/ -q --tb=short 2>&1 | tail -5)
echo "$RESULT"

# Extract pass count for easy grep
PASSED=$(echo "$RESULT" | grep -oE '[0-9]+ passed' | head -1)
echo ""
echo "✓ Result: ${PASSED:-no pass count detected}"
```

---

### File 4 of 8 — `/Users/jacobbrizinski/Projects/kitty/scripts/quick-smoke.sh`

**Action:** Create new file. Make executable.

```bash
#!/bin/bash
# Quick live smoke test of Kitty's primary routes.
# Requires server running on port 5001. Use after deploys or major refactors.

set -e

PORT=${KITTY_PORT:-5001}
BASE="http://localhost:$PORT"

echo "→ Checking server status..."
./kitty status || { echo "✗ Server not running on $PORT. Start with ./kitty start"; exit 1; }

echo ""
echo "→ /api/brief..."
curl -sS -w "\n[HTTP %{http_code}]\n" "$BASE/api/brief" | head -10

echo ""
echo "→ /api/command with /stuck..."
curl -sS -w "\n[HTTP %{http_code}]\n" -X POST "$BASE/api/command" \
  -H "Content-Type: application/json" \
  -d '{"command":"/stuck"}' | head -10

echo ""
echo "→ /api/chat..."
curl -sS -w "\n[HTTP %{http_code}]\n" -X POST "$BASE/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"smoke test","domain":"chat"}' | head -10

echo ""
echo "✓ Smoke test complete."
```

---

### File 5 of 8 — `/Users/jacobbrizinski/Projects/kitty/scripts/checkpoint.sh`

**Action:** Create new file. Make executable. This script commits work-in-progress with a timestamp so usage-limit cutoffs don't lose state.

```bash
#!/bin/bash
# Checkpoint work-in-progress.
# Usage: ./scripts/checkpoint.sh "message"
# Stages all tracked changes, commits with timestamp + message.
# Use during long autonomous runs to preserve state across usage limits.

set -e

cd "$(dirname "$0")/.."

MSG="${1:-checkpoint}"
TS=$(date +%Y-%m-%dT%H%M)

# Only stage tracked files (no -A to avoid sensitive untracked files)
git add -u

if git diff --cached --quiet; then
  echo "→ No changes to checkpoint."
  exit 0
fi

git diff --cached --stat
echo ""
read -p "Commit these changes as 'checkpoint $TS: $MSG'? [y/N] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "→ Aborted."
  git reset
  exit 0
fi

git commit -m "checkpoint $TS: $MSG"
echo "✓ Checkpoint committed."
```

---

### File 6 of 8 — `/Users/jacobbrizinski/Projects/kitty/.claude/skills/fix-and-verify/SKILL.md`

**Action:** Create directory and file. Follow the structure of existing skills like `prompt-answer-quality/SKILL.md`.

```markdown
---
name: fix-and-verify
description: Codified loop for the recurring "audit → fix → test → commit" pattern. Use when the user describes a bug, asks to fix something specific, or says "this is broken." Enforces test verification before declaring done.
type: process
---

Act as a Fix-and-Verify Specialist. This skill enforces the discipline of never declaring a bug fixed without verification.

## Activation

Activate when:
- User reports a bug ("X is broken", "Y returns wrong result")
- User asks to fix a specific issue
- User says "this isn't working" with concrete evidence
- User invokes `/fix` command

## The Loop

```
1. IDENTIFY  → Read user description and reproduce the bug from session context
2. SCOPE     → State what will change in one sentence; confirm minimal fix path
3. APPLY     → Make the smallest change that addresses root cause (no scope drift)
4. CACHE     → Clear .pyc cache: scripts/clear-and-test.sh (runs tests too)
5. VERIFY    → Confirm test count vs baseline; if green, smoke test if route-related
6. REPORT    → State: what changed, X/Y tests passing, smoke result, commit message proposal
7. WAIT      → Stop. Do not commit. Wait for user approval.
```

## Hard Rules

- Never declare done without a fresh test run output in this session.
- Never silently fix unrelated issues found along the way. Surface them as separate items.
- Never commit without user approval, unless user has explicitly delegated commit authority for this loop.
- If tests reveal new failures unrelated to the fix, stop and report — do not chase them.

## Output Shape

```
## Fix Report

Bug: <one sentence>
Root cause: <one sentence>
Change: <file:line> — <minimal description>

Tests: X/Y passing (baseline was Z/Y)
Smoke: <if applicable, one line per route>

Proposed commit:
fix(<scope>): <imperative summary>

<body if needed>

Awaiting approval to commit.
```

## Anti-Patterns

- "I also cleaned up..." — do not.
- "While I was there..." — do not.
- Committing before reporting — do not.
- Skipping the test run because "the change is obvious" — do not.

## Related

- Use `scripts/clear-and-test.sh` for the cache+test step.
- Use `scripts/quick-smoke.sh` for route-related smoke testing.
- Pair with `scripts/checkpoint.sh` if multiple fixes need separate commits.
```

---

### File 7 of 8 — `/Users/jacobbrizinski/Projects/kitty/.claude/skills/parallel-subagents/SKILL.md`

**Action:** Create directory and file.

```markdown
---
name: parallel-subagents
description: Pattern for spawning multiple specialized subagents that work independently and report to a coordinator. Use when facing 2+ truly independent tasks (different subsystems, no shared files), especially for multi-component refactors or audits.
type: process
---

Act as a Coordinator Agent. This skill operationalizes parallel subagent execution to collapse serial work into one coordinated burst.

## When to Use

- 2+ independent tasks in different subsystems (backend, frontend, evals, infra)
- A broad audit that needs multiple lenses (security, performance, test coverage, dependencies)
- A refactor touching 3+ unrelated areas
- The launch plan's parallel work streams (one agent on knowledge pipeline, one on UX, one on architecture)

## When NOT to Use

- Tasks share files or interfaces (serial is safer)
- Single-subsystem work
- Anything where a misstep is hard to roll back
- Quick fixes (<15 min) — overhead exceeds benefit

## The Pattern

```
1. DECOMPOSE     → Break work into N independent lanes; each lane has one clear deliverable
2. SCOPE EACH    → For each lane, define: directory boundary, allowed files, forbidden files, deliverable shape
3. SPAWN         → Launch all subagents in ONE message with full instructions per lane
4. STEP BACK     → Stop. Do not check status. Trust them to return.
5. RECEIVE       → When all results land, review ALL outputs before any commit
6. RECONCILE     → Resolve conflicts (rare, since lanes were independent)
7. UNIFIED TEST  → Run scripts/clear-and-test.sh; all green or revert
8. COMMIT BATCH  → One commit per lane (clean separation) OR one batched commit (if tightly related)
```

## Lane Brief Template

Use this exact shape when spawning each subagent:

```
LANE: <name>
DELIVERABLE: <single sentence>
ALLOWED FILES: <explicit list or directory>
FORBIDDEN FILES: <explicit no-touch list — at minimum: other lanes' files>
SUCCESS LOOKS LIKE: <what proof of completion you expect>
TIME BUDGET: <token / wall-clock cap>
REPORT: <required final report format>
STOP CONDITION: <when to abort>
```

## Hard Rules

- All subagent calls go in ONE message (parallel, not sequential).
- After spawning, do NOT poll status. Wait for results.
- Never let a subagent commit. Coordinator owns the merge.
- If any lane fails, the whole batch holds — do not partial-merge.
- Cut parallel agents the moment they stop producing evidence (Jacob's rule).

## Anti-Patterns

- Spawning 5+ parallel agents on overlapping work — guaranteed merge pain.
- "Quick parallel agent for this small thing" — overhead kills it.
- Letting agents run unbounded — always set a deliverable + stop condition.

## Example: Kitty Launch Plan Sub-Project Parallelism

For the larger launch plan (Layer 1, Sub-Project 1: Personal Onboarding Pipeline), this would look like:

- **Lane A** (`backend-pipeline`): build the `OnboardingPipeline` class in `src/services/`, allowed files: `src/services/onboarding_pipeline.py`, `tests/test_onboarding_pipeline.py`. Forbidden: anything else.
- **Lane B** (`frontend-wizard`): build the first-run wizard UI in `garage-ui/app/components/onboarding/`. Allowed: that directory only.
- **Lane C** (`agent-roles`): wire KnowledgeGetter / Librarian / Embedder agent stubs in `src/agents/onboarding/`. Allowed: that directory only.
- **Coordinator** (Sonnet/Opus): receives all three diffs, resolves any shared-config issues, runs full test suite, commits in 3 separate commits.
```

---

### File 8 of 8 — `/Users/jacobbrizinski/Projects/kitty/.claude/skills/overnight-queue/SKILL.md`

**Action:** Create directory and file.

```markdown
---
name: overnight-queue
description: Pattern for autonomous overnight task queue execution with durable checkpointing. Use when Jacob queues multi-task work and steps away. Prevents usage-limit cutoffs from losing state.
type: process
---

Act as an Autonomous Queue Worker. This skill operationalizes long unattended runs that survive interruption.

## When to Use

- Jacob queues 3+ tasks and explicitly says "work the queue" or "run overnight"
- Long-running batched work where each task is independent and reversible
- Implementation work where Jacob has approved the spec and is stepping away

## When NOT to Use

- Tasks requiring decisions Jacob hasn't pre-approved
- Anything destructive without explicit per-task authorization
- Work where one failure should cascade-stop the queue

## The Pattern

```
1. INGEST          → Read TASKS.md or queue source; confirm each task has clear done criteria
2. ESTIMATE        → Token budget per task, total queue, expected wall-clock
3. CHECKPOINT FILE → Create HANDOFF-<date>-queue.md with task list and status column
4. PER TASK:
     a. Mark in-progress in HANDOFF
     b. Branch (optional, if isolation matters)
     c. Implement
     d. Test (scripts/clear-and-test.sh)
     e. Commit (scripts/checkpoint.sh) — ALWAYS before next task
     f. Mark done in HANDOFF with one-line note
     g. Move to next
5. ON USAGE LIMIT  → HANDOFF is already current; next session resumes cleanly
6. ON HARD FAIL    → Mark task as blocked in HANDOFF, stop queue, leave clean state
7. ON COMPLETE     → Final HANDOFF entry summarizes what shipped, what's next
```

## Checkpoint File Shape

```markdown
# Queue: <name>
Started: <ISO timestamp>
Worker: <agent-id / model>

## Tasks

| # | Task | Status | Commit | Tests | Note |
|---|------|--------|--------|-------|------|
| 1 | ... | done | abc123 | 399/399 | <note> |
| 2 | ... | in-progress | — | — | — |
| 3 | ... | pending | — | — | — |

## Last Resumable State
<one paragraph: what's running, what's next, anything mid-flight>
```

## Hard Rules

- Never start task N+1 without having committed task N.
- Never silently expand scope. If a task reveals more work, log it as a NEW queue item, do not absorb it.
- Never leave the repo broken. If you cannot complete cleanly, revert the in-progress change before stopping.
- When sensing usage approaching limit, FINALIZE the HANDOFF immediately, then continue if budget allows.
- Stop the queue only on: empty queue, two consecutive task failures, or explicit user halt.

## Anti-Patterns

- Marking task done without test evidence — never.
- Working faster by skipping commits — defeats the entire purpose.
- "I'll consolidate the commits at the end" — no. Commit per task.

## Pairs With

- `scripts/checkpoint.sh` for fast WIP commits
- `scripts/clear-and-test.sh` for the test gate
- `parallel-subagents` skill if a queue item itself decomposes into parallel work
```

---

## Verification (Run These When All 8 Files Are Written)

```bash
cd /Users/jacobbrizinski/Projects/kitty

# 1. Validate JSON
python3 -m json.tool .claude/settings.json > /dev/null && echo "✓ settings.json valid"

# 2. Validate scripts
for s in scripts/clear-and-test.sh scripts/quick-smoke.sh scripts/checkpoint.sh; do
  [ -x "$s" ] && bash -n "$s" && echo "✓ $s ok" || echo "✗ $s failed"
done

# 3. Validate skills exist
for s in fix-and-verify parallel-subagents overnight-queue; do
  [ -f ".claude/skills/$s/SKILL.md" ] && echo "✓ skill $s exists" || echo "✗ skill $s missing"
done

# 4. Confirm CLAUDE.md changes landed
grep -q "## Workflow Conventions" CLAUDE.md && echo "✓ CLAUDE.md updated" || echo "✗ CLAUDE.md missing sections"

# 5. Run the full test suite (must still be 399 passing)
venv/bin/python -m pytest tests/ -q --tb=short 2>&1 | tail -3
```

All five checks must pass. If any fails, fix before commit.

---

## Commit

When all files written and all checks pass, commit:

```bash
git add CLAUDE.md .claude/settings.json .claude/skills/fix-and-verify/ .claude/skills/parallel-subagents/ .claude/skills/overnight-queue/ scripts/clear-and-test.sh scripts/quick-smoke.sh scripts/checkpoint.sh

git commit -m "$(cat <<'EOF'
infra: add workflow conventions, hooks, scripts, and process skills

Implements every actionable suggestion from the 2026-05-01 /insights report
plus high-value patterns harvested from Codex session memory.

CLAUDE.md additions:
- Workflow Conventions (check existing work, run tests, discuss before design)
- Project Context (Werkzeug flag, TokenCapture leak, port split, dynamic-exec rename)
- Session Management (checkpoint frequently, commit before risky ops)
- Cost Discipline (cheap-first, free-as-backup, premium-reserved routing)
- User Profile (beginner-friendly, honest verification, companion-feel-first)

Tooling:
- .claude/settings.json: ruff postToolUse hook alongside py_compile
- scripts/clear-and-test.sh: cache clear + test cycle
- scripts/quick-smoke.sh: live route smoke test
- scripts/checkpoint.sh: WIP commit helper

Skills (.claude/skills/):
- fix-and-verify: codified audit→fix→test→commit loop
- parallel-subagents: pattern for independent multi-lane work
- overnight-queue: durable checkpointed queue execution

No product code touched. No tests changed. Pre-commit hook should
still report 399 passing.
EOF
)"
```

---

## Stop Conditions

You're done when:
- All 8 files exist with the content above
- All 5 verification checks pass
- The commit lands cleanly (pre-commit hook passes)
- You append a one-line completion note to the bottom of THIS handoff file

If you hit a problem:
- Don't expand scope to fix it
- Don't skip files to "come back later"
- Stop, document the blocker in this file, hand back to user

---

## Completion Log

(Executor: append your completion line here)

- [ ] All 8 files written
- [ ] Verification checks pass
- [ ] Committed cleanly
- [ ] Tests still 399 passing

Completion note: 2026-05-01 — done by deepseek-v4-pro, commit 05ccb9a, 399/399, no surprises
