# Repository Guidelines

This file is the compact root contract. `START_HERE.md`,
`docs/reference/CONTEXT_ENGINEERING.md`, and the named skills own the detailed
procedures; do not duplicate them here.

## Prime directive

Fail loud. Raise errors with clear causes. Do not swallow exceptions, invent
defaults, hide unavailable evidence, or add silent recovery. External calls may
retry with a visible warning, then must raise the real error with status,
parameters, and response context.

## Judgment and clarification

Do not agree reflexively with Jacob or treat a factual premise as true merely
because he stated it. Challenge unsupported premises with the best available
evidence and say when the evidence disagrees. Never invent facts, certainty, or
understanding. Never claim understanding when material ambiguity remains. Ask
one consolidated clarifying question when its answer can materially change the
outcome; otherwise resolve what you can from the repository, tools, and existing
context, state any bounded assumption that matters, and avoid ceremonial or
low-value questions.

## Before work

For repository-changing work or stale inherited context, run `START_HERE.md`.
It is the single source for checkout verification, live Git state, the context
receipt, authority reading order, mission/checkpoint freshness, and the final
mutation gate. Read `config/PREFERENCES.md` once per session for Jacob-specific
interaction and taste defaults; preferences are personal context, not
architecture/runtime evidence, and never override verified repository truth. Use staged loading from
`docs/reference/CONTEXT_ENGINEERING.md`; read only the authority required by
the task. Builder and GAR are suspended as defaults; inspect them only when
explicit historical, rollback, or Builder-specific work requires it.

## Suspended default operating model

Builder is not the default executor and GAR is not mandatory recall, lifecycle,
or handoff infrastructure. Normal work begins from live Git/GitHub/runtime state
and the current assignment.

Before mutating a shared Kitty worktree, acquire the smallest local ownership
claim that covers the paths you intend to change:

`python3 scripts/work_claim.py claim --owner <id> --task <task> --path <scope>`

Claims live only in the repository's shared Git metadata. They have explicit
expiry, block overlapping active scopes, allow non-overlapping work, and require
no daemon or database. Use `status`, `renew`, `release`, and `reap` as
needed. Do not kill, clean, move, or delete another session's worktree or files.
Do not use `/tmp` for durable worktrees. Commit recoverable WIP before stopping
long-running work.

Git/GitHub remain publication authority. GAR and Builder history stay preserved
for archaeology and rollback, but ordinary completion must not create GAR
traffic, lifecycle receipts, or Builder work merely to satisfy bookkeeping.

## Scope and code quality

Kitty is a local-first companion. Backend code is in `gateway/`, FastAPI routes
in `gateway/routes/`, the web UI in `gateway/kitty-chat/`, tests in `tests/`,
and product/architecture docs in `docs/`. Runtime data and logs in `data/` and
`logs/` are not source artifacts. Use the existing patterns, keep diffs focused,
prefer editing existing files, and comment the why rather than the obvious.
Durable architecture decisions belong in ADRs; proven workflow lessons belong
in canonical docs/tests/skills, and workflow signals follow ADR 0025 as
evidence rather than a second execution backlog. `docs/ROADMAP.md` is the sole
active roadmap.

## Verification

After a meaningful change, run the narrowest relevant checks and report exact
results. Do not run the full suite, lint, typecheck, or build unless the task
asks for it or `/qg`/CI requires it. Runtime, UI, launch, and environment
claims need their corresponding live proof. Never call work complete from
inspection alone; use the final states in `verified-delivery`. Implementation,
packet completion, tests, a green PR, or a subagent reporting `DONE` are
implementation evidence only. A user outcome closes only when its applicable
outcome contract is verified against the exact running candidate or, for a
non-runtime documentation/process task, the exact repository state and the
reader/operator behavior the task was meant to change. Material course
corrections to how agents work must be persisted into load-bearing doctrine,
preferences, tests, or enforcement before closeout; a transient chat message
alone is not enough.

## Reviewer routing

Independent review is reliability-sensitive. Outside an explicitly requested
`--free` Builder lane, use the governed paid OpenRouter reviewer directly instead
of spending time on flaky free-model roulette. Routine reviewer requests force
OpenRouter price-first provider routing and may fall back once to a different
reviewer model if the primary fails cleanly. Keep review read-only and preserve
model-family independence: DeepSeek implementations use MiniMax M3 first and
Qwen 3.7 Plus as the bounded fallback. Explicit `--free` still means zero paid
fallback. Do not depend on Freebuff, 9Router, or any other optional service.
OpenRouter is the preferred router for reviewer routing. AgentRouter is dead; do not recommend it. Freebuff and 9Router are optional only and must never be dependencies. Do not prefer `openrouter/deepseek/deepseek-v4-flash-0731` merely because it is newer; repeated runs observed it stalling.


## Git, credentials, and irreversible actions

The canonical checkout is an observation/integration point, not the default
implementation workspace. Before creating any task branch intended for a PR,
resolve the fresh GitHub `main` SHA and base the task worktree/branch on that
SHA. Do not base new PR work on local `main` unless you have just proven it
equals GitHub `main`; local-only integration commits can silently contaminate
the PR.

Preserve unrelated uncommitted work. Do not stash or clean merely to simplify
the checkout; if isolation genuinely requires a stash, name it descriptively.

Keep small Conventional Commits. Never force-push, rewrite history, delete data,
touch secrets/auth/env, spend money, add a heavy dependency, merge, or push
directly to `main` without explicit authorization. An explicit instruction from
Jacob to implement, fix, continue, or finish a named technical task authorizes
creating an isolated task worktree/branch, committing verified task work, pushing
that non-main branch, and opening or updating its PR. It does not authorize the
higher-impact actions listed above or material scope expansion. Before `gh` or
push, check for an ambient `GITHUB_TOKEN`; prefer `env -u GITHUB_TOKEN gh ...`
when stored auth is valid, and never print credential values. Never poll CI: use
one `gh pr checks <N> --watch` command when waiting on a PR, and never wrap `gh`
status checks in sleep/loop polling. Before merge,
inspect every required Actions check run. A green aggregate status is not enough.
Do not enable or rely on auto-merge for dependency/lockfile, CI, auth/security,
destructive/schema, human-judgment, collision, unverifiable-gate, or scope-
expansion changes.

## Builder compatibility

Builder code, data, task history, leases, attempts, and publication records are
preserved. Builder runs only when Jacob explicitly requests Builder work or a
rollback experiment requires it. A normal interactive session must not select,
schedule, supervise, drain, repair, or depend on Builder.

If explicitly reviewing historical Builder output, use its supported projections
and preserve its recorded evidence. Do not translate dormant Builder state into
new work automatically.

## Special commands

When the user says bare `next`, `continue`, `resume`, or `do the next thing`,
execute `.agents/skills/next/SKILL.md`: continue only the current assignment
from the conversation and verified live repository state. Do not inspect Builder
or GAR merely to manufacture a continuation.

Normal completion is simply: verify the requested outcome, report the evidence,
and stop. `.agents/skills/session-end/SKILL.md` is suspended compatibility
documentation and must not run automatically or create GAR/STATE/HANDOFF/KB
bookkeeping.

For implementation, repair, review, or completion claims, use
`.agents/skills/verified-delivery/SKILL.md`. For modernization or maintenance
cost reduction, use `.agents/skills/aim42-software-improvement/SKILL.md`. For
codebase improvement or hardening triage, use
`.agents/skills/engineering/improve-codebase/SKILL.md` (internal shape, runtime
failure behaviour, user surface, test trustworthiness). For repository upkeep —
stale docs, CI/gate drift, architecture conformance, dependency checks — use
`.agents/skills/engineering/maintain-repo/SKILL.md`.

Read-only dependency sources under `.slim/clonedeps/repos/` may be inspected
but not edited.
