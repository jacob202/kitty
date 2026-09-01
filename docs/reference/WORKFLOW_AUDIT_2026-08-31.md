# Workflow Audit — 2026-08-31

Evidence-based look at how agent time is actually being spent across Claude
Code, Codex, and ChatGPT, and where the workflow is leaking. Raw data: 55
Claude Code sessions (~126.5h wall time, Aug 18–31), 65 Codex threads (121
turns), ChatGPT via the Codex read_thread connector.

## The one-sentence diagnosis

The tooling is already excellent — the repo has hooks, skills, handoffs,
builder lanes, and gates. The waste is in **waiting** (CI polling loops),
**collision** (parallel PR storms and checkpoint-file merge conflicts), and
**re-discovery** (parallel agents re-surveying the same codebase and cold
sessions re-running full test suites). None of it needs new tools; it needs
the right habits wired into the existing hooks.

## Evidence

### 1. Waiting on PR checks (biggest single leak)

Across kitty Claude sessions:

| Pattern | Count |
|---|---|
| `gh pr checks` | 52 |
| `sleep N` (polling) | 33 |
| `until ... sleep ... done` polling loops | 9 |
| `gh run view --job ... --log` CI-log grepping | 18 |
| `gh run rerun` | 5 |
| `gh pr update-branch` | 10 |

That's roughly 80+ blocking waits in two weeks, often looped 10–16 times at
20–60s intervals, each eating a full agent round-trip. Plus 18 sessions
digging through CI logs for failing jobs (policy-gate, review-gate,
browser-smoke, pytest-integration).

The replacement already exists in the tools we use:
- `gh pr checks <N> --watch` — one command, watches until done
- `gh pr merge <N> --auto` — GitHub auto-merge: merges when checks pass, no
  watching at all

### 2. PR storm / parallel collision

- 15 PRs open right now. On 08-31 alone ~12 parallel `feat/wow-*` branches
  were created within hours, plus kittybuilder branches (PRs 726–748).
- 5+ live worktrees: orca/workspaces/kitty/{packet-master, slate,
  toolchain, budget, handoff} + /private/tmp/kitty-* worktrees.
- 100+ PRs merged in the recent window.
- Codex ran parallel bursts: ~20 threads in one hour (08-30 20:39–21:49),
  ~12 the next morning, ~9 more at 13:39 — council/fan-out runs, many
  1-turn threads with failed/interrupted statuses.
- Claude spawned ~40 subagent/workflow sessions; three parallel survey
  workflows (wf_8a9c1e78, wf_e03528c9, wf_db9aecbf) each spawned ~7 agents
  re-surveying the same codebase.

Every parallel branch makes every other branch's merge harder (update-branch
x10, conflict fixes, re-review). The classic fix — a **GitHub merge queue** —
serializes merges, runs CI on the actual merged result, and removes
update-branch churn entirely. It's free and native.

### 3. Checkpoint files conflict on every merge

`.claude/STATE.md` and `.claude/HANDOFF.md` are **tracked in git**. They are
per-session state files that change every session, so every parallel merge
conflicts on them. A subagent literally called it "a tax on every future".
Fix: untrack them (gitignore + one `git rm --cached` commit).

### 4. Redundant full test runs

`.claude/settings.json` runs a **full pytest suite at every session start**
(`sessionStart` field). 55 sessions = ~55 full-suite runs before the agent
even knows the task. The pre-push rule in `.claude/rules.md` already
requires targeted tests before push — the session-start full run is pure
overhead. Fix: drop it; test on demand and before push.

### 5. Auth / infra friction

- Sessions full of `unset GITHUB_TOKEN` + `git -c credential.helper=...`
  dances and `gh auth setup-git` troubleshooting.
- Builder worker failures from Seatbelt write denials, uv python paths,
  brew git vs CommandLineTools git, time-budget, handoff bugs — two
  consecutive "Both attempts failed on Builder infrastructure" sessions.
- One session pip-installed pytest/ruff itself because the venv lacked them.

### 6. Context fragmentation across three surfaces

- Claude Code: 55 sessions, many /clear cycles, voice-dictated prompts.
- Codex: 8 contextCompactions in two days; threads titled "Lead Kitty
  recovery" (10 turns, 2 failed), "Read handoffs" (3 turns, 1 failed).
- ChatGPT: no local history exists (cloud-side); Codex accesses 4
  conversations via the read_thread connector — "Assess Two Character
  Rendering", "Harvest Kitty Upstream Findings", "Write Opus Execution
  Prompt", "Memory Automation Convergence". Codex already imports Claude
  sessions (external_agent_session_imports.json).

### 7. What already exists and works (use it harder)

- `.claude/hooks/`: session-start (context injection), recall-thread
  (SOUL_SCRATCHPAD readback), session-stop (memory nudge), warn-unpushed,
  scan-secrets, block-dangerous-commands, build-it evidence-lint +
  turn-end-gate, suggest-catchup, suggest-on-test-fail.
- Skills: `next`, `session-end`, `verified-delivery`, `catchup`, `remember`,
  `debug-fix` + the whole `.agents/skills/` suite.
- `config/PREFERENCES.md` durable prefs (already says: don't ping about PR
  status; decide and act; put detail in files).
- Builder lanes + packet system in AGENTS.md.
- Merge procedure memory file already written to
  `~/.claude/projects/-Users-jacobbrizinnski-Projects/memory/kitty-pr-merge-procedure.md`.

## The plan (ranked by leverage)

### Tier 1 — do now, wired into the repo (done in this audit)

1. **Never poll CI again.** New `.claude/hooks/block-polling.sh` blocks any
   `until/while/for + sleep + gh pr checks/view/run` loop and points at
   `gh pr checks --watch` and `gh pr merge --auto`. Wired into PreToolUse.
2. **Stop the session-start full pytest.** Removed from
   `.claude/settings.json`. Tests still run before push (rules.md) and on
   demand.
3. **Untrack checkpoint files.** `.claude/STATE.md` and `.claude/HANDOFF.md`
   added to `.gitignore`; they need one `git rm --cached` commit to stop
   conflicting (needs a commit — see below).
4. **New rule in `.claude/rules.md`**: never poll; use --watch / --auto;
   merge queue is the target.

### Tier 2 — one-time setup (needs Jacob's go)

5. **GitHub merge queue on main.** One-time ruleset change (ruleset
   20193076): enable a merge queue so PRs stack and merge automatically in
   order with CI on the merged result. Kills update-branch churn, most
   conflict fixes, and the "waiting for the merge" tail. After this, the
   standard flow becomes: open PR → `gh pr merge --auto` → done.
6. **Commit the checkpoint-file untracking** (one small commit: remove
   .claude/STATE.md + .claude/HANDOFF.md from git, keep them local).

### Tier 3 — habit changes (biggest weekly payoff)

7. **Sequential, not parallel, feature work.** The wow-blitz (12 parallel
   feature branches in a day) costs more in merge/review/conflict than it
   saves in wall clock. Rule: max 1–2 active feature branches; queue the
   rest in the existing Builder packet system. Use `next`/`session-end`
   skills on every /clear so nothing is re-discovered.
8. **One codebase survey, cached.** Parallel survey workflows re-survey the
   same tree repeatedly. Write one survey doc per week; agents read it
   instead of re-exploring.
9. **Fix the auth dance once.** `gh auth setup-git` in a healthy shell and
   stop unsetting GITHUB_TOKEN; keep the credential helper standard.
10. **ChatGPT bridge.** Can't read ChatGPT's cloud history locally. Keep
    using Codex's read_thread connector; when a ChatGPT session produces
    code decisions, paste the result into HANDOFF.md so every other tool
    sees it.

## What success looks like (end of week)

- Zero `sleep`/`until` polling loops in agent transcripts.
- PRs merged via `--auto`/merge queue without update-branch churn.
- No merge conflicts caused by checkpoint files.
- Fewer than 4 parallel feature branches at any time.
- Sessions resume via `next`/handoff instead of re-surveying.
