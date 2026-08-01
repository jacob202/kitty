# Repository Guidelines

## Prime Directive

Fail loud, never mask. Raise errors with clear causes; do not swallow exceptions, return fake defaults, or add silent fallbacks. External calls may retry with a visible warning, then must raise the real error with useful context.

## Cold-start bootloader

Before acting, execute the bootloader in `START_HERE.md`. At minimum:

1. verify this worktree belongs to the canonical `~/Projects/kitty` checkout;
2. inspect live Git state;
3. run `./kitty context --agent` and reject any stale or contradictory receipt;
4. follow the receipt's canonical reading order and authority map;
5. read `docs/ACTIVE_MISSION.md` and the current session checkpoint;
6. inspect Builder through supported interfaces when execution state matters;
7. treat handoffs and prose as invalid when live evidence disagrees; and
8. verify relevant facts and authorization before mutation.

## Context engineering default

Use staged context loading per `docs/reference/CONTEXT_ENGINEERING.md`: start
from `./kitty context --agent`, load only the authority needed for the current
task class, and expand incrementally. For code changes, complete the full
canonical reading order before edits.

## Project Structure

Kitty is a local-first personal AI companion. KittyBuilder is its execution control plane — Kitty owns product intent, Builder owns execution state (ADR 0017). Backend code lives in `gateway/`, with FastAPI routes under `gateway/routes/` and path constants in `gateway/paths.py`. The main UI is `gateway/kitty-chat/` (Next.js). Tests live in `tests/`. Product, architecture, and planning docs live in `docs/`. Runtime data and logs live in `data/` and `logs/` and must not be committed.

For a detailed repository map with entry points, data flows, state ownership, and common change locations, see `docs/reference/CODEBASE_MAP.md`.

## Commands

- `./kitty up`: start Gateway and LiteLLM locally.
- `./kitty down`: stop local services.
- `./kitty status`: show process and health status.
- `./kitty doctor --json`: run preflight checks.
- `python3.12 -m pytest tests/ -q --tb=short`: run the default Python suite.
- `cd gateway/kitty-chat && npm run build`: verify the production UI build.
- `cd gateway/kitty-chat && npm test`: run frontend tests.
- `make agent-wrap`: write a session wrap-up template to `.agent/session_logs/`.

## Style

Match the existing file before introducing new patterns. Python uses 4-space indentation, explicit errors, and small readable functions. TypeScript/React uses functional components and clear prop names. Comment the why, not the obvious what. Keep diffs focused; do not reformat unrelated code.

## Testing

After any non-trivial code change, run the narrowest tests that actually cover it — the specific test files, not `tests/` — and report exact pass/fail counts. Verifying your own change is not a quality gate; it is how you know the change works.

Do NOT run the full suite, lint, typecheck, or build mid-session unless explicitly asked with `/qg` or `/qg all`. CI runs those on every PR and push to main. When the user does ask for quality gates, run only what's relevant: UI changes → `npm test` + `npm run build` in `gateway/kitty-chat/`; backend changes → `python3.12 -m pytest tests/ -q --tb=short`; launch/auth/port/env changes → also `./kitty status` and `./kitty doctor --json`.

`CLAUDE.md` states this same rule — change both or neither.

## Git and PRs

Use small Conventional Commit messages such as `fix(auth): fail closed`. Never push, force-push, rewrite history, delete files, touch secrets/auth/payments/env, or add heavy dependencies without explicit confirmation. PRs should state user-facing impact, verification, skipped checks, and screenshots for visible UI changes.

Before any `gh` command or `git push`, check whether `GITHUB_TOKEN` is set. If `env -u GITHUB_TOKEN gh auth status` succeeds, run GitHub commands with `env -u GITHUB_TOKEN` so a stale ambient token cannot override keyring authentication. Never print token values.

Before merging a PR, read the Actions **check runs** and confirm each required job is `success` — not just the combined commit `status`. They are different GitHub surfaces; a green `status` (e.g. a review bot) can hide failing lint/typecheck/pytest check runs. A broken file reached `main` this way once (see `docs/LEARNINGS.md` L-CAND-6). After any non-trivial merge, compile/import the touched files before declaring done.

### PR agent review

A GitHub Action (`pr-agent-review.yml`) auto-reviews every opened or updated PR using an LLM via OpenRouter. It posts a review comment on the PR. Requires `OPENROUTER_API_KEY` set as a GitHub repo secret at Settings → Secrets and variables → Actions → Repository secrets.

## KittyBuilder execution control plane

KittyBuilder has durable initiatives, packets, queue state, leases, attempts,
isolated worker runs, validation/review, recovery, budgets, publication rails,
and a bounded read-only status projection. Use `./kitty builder --help` and
`docs/KITTYBUILDER_QUICKSTART.md` for the supported surface; use
`./kitty builder initiative doctor --json` before execution-sensitive work.

Builder owns execution state, not product intent. The accepted boundary is the
versioned, authorized Mission in ADR 0017. This repository does not yet permit
Kitty to submit that Mission autonomously. Never infer Builder state from
handoff prose, worker output, or UI emptiness, and never join its SQLite tables
into another state machine.

### Orca/OpenCode Build Train

Use Orca worktrees for isolated KittyBuilder work. Run
`scripts/orca_worktree_setup.sh` as the Orca setup hook for this repo, and keep
`docs/KITTYBUILDER_ORCA_SETUP.md` as the operating guide.

Default to OpenCode for planning, implementation, packaging, and normal scoped
review. Reserve Codex for high-risk safety reviews involving queue state,
concurrency, auth/secrets/env, destructive operations, or blocked escalation.

Before dispatching a planning pass or an independent review, check it against
the compute governor: `./kitty governor explain <dispatch.json>`. One plan and
one review per unchanged `(task_type, subject_ref, head_sha)`; a changed SHA,
changed requirements, or a named human override reauthorizes. See the compute
governor section of `docs/FREE_WORKERS.md`.

Do not let the same worker approve its own work. T0 work may proceed
automatically, T1 work needs a separate model approval, and T2 work still needs
Jacob: push, merge, deletes, auth/secrets/env, paid or heavy dependencies, and
broad scope changes.

## Agent Rules

Before multi-file work, give a short plan. Prefer editing existing files over creating new structure.

### Session start

Read `.claude/HANDOFF.md` and `.claude/STATE.md` at the start of every session.

### Exact `next` protocol

When the user's instruction is a bare continuation such as `next`, `do the next
thing`, `continue the queue`, `resume work`, or `take the next packet`, execute
`.agents/skills/next/SKILL.md` instead of asking the user to restate the work or
selecting from memory.

The skill must:

1. run the cold-start receipt and live field survey;
2. continue valid owned in-flight work before starting anything;
3. validate/apply the approved leverage initiative idempotently when absent;
4. inspect all initiatives and live collision scopes;
5. select one eligible authorized non-colliding packet;
6. execute it through governed Builder rails with evidence and independent review;
7. run the full session-end skill; and
8. stop after one bounded cycle.

A named request outranks the bare trigger. Never hijack another worker's lease,
start a duplicate of active Chat/Builder work, promote an unowned learning signal
over approved queued work, or begin a second packet after session-end.

### Session end protocol — triggered by: "session end", "end session", "wrap up", "i'm done", "save my work", "ship it"

When the user says any of these phrases, do NOT just say goodbye. Run the full
checklist. `.agents/skills/session-end/SKILL.md` is authoritative; this summary
must not diverge from it.

1. **Survey the field** — run `bash scripts/session_end_survey.sh`. Inventory worktrees, unmerged branches and touched paths, open PRs **including drafts**, Builder's read-only projection, `~/kb/NOW.md`, and carried recommendations. `UNAVAILABLE` is unverified, not clean. Other agents' work is theirs—name it, do not claim it.

2. **Evaluate carried recommendations** — execute only the exact safe read-only `release_check` forms allowed by the skill. Exit 0 promotes to `ready`; exit 1 re-defers and increments; an unavailable command/auth/network/signal carries unchanged and is reported. At 3 deferrals say the stated blocker is probably not the real one.

3. **Reconcile completion evidence** — establish packet/task/attempt, branch/worktree/base/HEAD, changed files, exact tests, runtime proof, SHA-bound independent review, PR/check/publication state, provider/spend/cleanup, and honest failure/recovery. Attach Builder reports through supported fenced commands; never edit SQLite or infer done from prose.

4. **Extract durable knowledge and corrections** — write verified reusable facts to `~/kb/wiki/`, Jacob corrections to `~/kb/corrections/`, and index them. The KB is absolute `~/kb`, never repo-relative. Stage a transfer payload under `docs/session-notes/` only when the KB is unavailable.

5. **Record workflow learning** — use `scripts/session_learning.py` to record zero to three evidence-based stable signals and summarize the rolling window. First ordinary occurrence stays observed; repeated signals promote; integrity/security/data-loss/fabricated-success/queue-integrity/paid-waste incidents may promote immediately. Check existing roadmap, Mission, initiative, queue, branch, PR, and issue owners before carrying at most one unowned promoted code improvement. Session-end does not automatically create issues or tasks (ADR 0025).

6. **Update `~/kb/NOW.md`** — merge current accomplishments, blockers, tool ownership, and promoted-signal ownership without clobbering parallel sessions.

7. **Build recommendations** — at most three ranked concrete actions, life before code (ADR 0016). Defer only for a real collision/dependency and provide one safe release check. At most one promoted unowned workflow improvement may appear.

8. **Write `.claude/HANDOFF.md` and `.claude/STATE.md`** — current evidence, parallel work, blockers, one next action, deferred release conditions, and workflow learning. STATE uses schema version 2 with `parallel_work` and `recommendations`; recommendations remain the only carry-forward next-step channel (ADR 0023).

9. **Validate and inspect** — run `python3 scripts/check_continuity_state.py`, `./kitty context --agent`, and `git status --short --branch`. Do not commit/push/delete/clean/merge unless explicitly authorized or an approved Builder publication policy permits the bounded action.

10. **Confirm and stop** — report files written, exact execution state, next move, deferrals, signal status/ownership, and every unavailable source. Do not start new work.

## Cloned Dependency Source

Read-only dependency source repositories are available under `.slim/clonedeps/repos/` for inspection. Do not edit these clones.

- `.slim/clonedeps/repos/MeiGen-AI__GenEvolve/` — `MeiGen-AI/GenEvolve` at `23c847c`; image-planning and renderer-boundary reference only.
