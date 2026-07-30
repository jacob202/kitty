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

### Session end protocol — triggered by: "session end", "end session", "wrap up", "i'm done", "save my work", "ship it"

When the user says any of these phrases, do NOT just say goodbye. Run the full
checklist. `.agents/skills/session-end/SKILL.md` is the authoritative version of
this checklist; this section is its summary and must not diverge from it.

1. **Survey the field** — run `bash scripts/session_end_survey.sh`. Read-only inventory of worktrees, unmerged branches and the paths they touch, open PRs **including drafts**, the Builder queue, `~/kb/NOW.md` claims, and recommendations carried from the previous `.claude/STATE.md`. A section printing `UNAVAILABLE` is unverified, not clean. Other agents' work is theirs — name it, don't claim it.

2. **Evaluate carried recommendations** — run the `release_check` of each **deferred** entry; a `ready` entry has none. Exit 0 promotes it to `ready`; exit 1 carries it with `deferred_count + 1`. A check that could not run at all (command missing, auth failure, network, signal) was never evaluated: carry the entry forward unchanged, do NOT increment, and report it `UNAVAILABLE`. At 3 deferrals, say out loud that the stated blocker is not the real one.

3. **Extract knowledge** — review the session for durable findings (patterns, gotchas, tool config changes, architecture decisions). Write `~/kb/wiki/YYYY-MM-DD-slug.md` with source, date, why it matters, verified-by. Append one line to `~/kb/INDEX.md`. Skip ephemera (task shuffles, typo fixes). If you got something wrong and Jacob corrected you, write `~/kb/corrections/YYYY-MM-DD-slug.md` instead. **The KB is `~/kb` (absolute), a separate repo — never write to a repo-relative `kb/` path.**

4. **Update `~/kb/NOW.md`** — refresh active project, accomplishments, blockers, and sync changes. Merge, don't clobber — parallel sessions exist.

5. **Build the recommendations** — at most three ranked next steps, life projects before code (ADR 0016), each one concrete action. Defer only for a real collision or dependency; "other work exists" is not a reason. Every deferred item needs a `release_check` command that exits 0 when the blocker clears.

6. **Write `.claude/HANDOFF.md`** — what was done, what's in-flight, other work in flight that isn't yours, blockers, next move, deferred items and what releases them, files changed. Make it directly actionable for the next session.

7. **Write `.claude/STATE.md`** — branch, SHA, status (complete/in-progress/blocked), completed items, next action. Must include the `<!-- kitty-state -->` JSON block with `schema_version` (write 2), `updated_at`, `head_sha`, `branch`, `status`, `completed_items`, `blockers`, `next_action`, plus `parallel_work` and `recommendations`. That block is the only carry-forward channel — do not open a separate notes file for future session-end runs (ADR 0022).

8. **Git status** — run `git status --short --branch`. Note uncommitted files. Do NOT commit or push unless explicitly asked.

9. **Confirm** — one line per file written, the next move, anything deferred with what releases it, and any survey section that came back `UNAVAILABLE`. Then stop. Do not start new work.

## Cloned Dependency Source

Read-only dependency source repositories are available under
`.slim/clonedeps/repos/` for inspection. Do not edit these clones.

- `.slim/clonedeps/repos/MeiGen-AI__GenEvolve/` — `MeiGen-AI/GenEvolve` at `23c847c`; image-planning and renderer-boundary reference only.
