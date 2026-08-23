# PR Review Workflow

How agents and reviewers coordinate on Kitty pull requests. This is the
coordination contract — read it before opening a PR.

## Workflow automation baseline (2026-08-23)

GitHub automation is deliberately split into high-signal deterministic checks and
risk-scoped governance. Routine PRs should not be blocked by duplicate prose, bot
comments, or an external model verdict.

### Automated now

1. **PR intake and triage**
   - `.github/pull_request_template.md` provides review context without making
     `## Summary` / `## Test plan` formatting a merge condition.
   - `.github/workflows/pr-auto-label.yml` applies path-based `area/*` labels.
2. **Trusted policy**
   - `.github/workflows/pr-policy-trusted.yml` runs `policy-gate` from the
     repository default branch under `pull_request_target`; PR-authored policy
     code is never executed with the policy token.
   - Native UI source/public changes require completed product acceptance.
   - Sensitive scope (auth/security, CI policy, approval/action boundaries,
     publication/destructive paths, secrets/env, dependency roots) requires
     `risk/approved`, an exact-head Risk approval receipt, and trusted
     independent review for the exact current head.
   - Large PR size is advisory rather than a second approval ceremony.
3. **Deterministic merge evidence**
   - `.github/workflows/tests.yml` keeps Python `pytest`, Ruff, and mypy as hard
     signals. `merge-gate` aggregates them into one stable required result.
   - Kitty Chat and browser smoke remain hard evidence when the frontend changes;
     unrelated PRs skip those expensive jobs.
   - `hygiene` still runs, but is advisory because link/dead-code heuristics should
     not veto an otherwise valid repair.
4. **Independent model review**
   - `.github/workflows/pr-agent-review.yml` reviews each new code head using
     trusted default-branch reviewer code. Editing prose or labels does not call
     the model again.
   - Review is advisory for ordinary PRs. `policy-gate` requires trusted exact-head
     review evidence only for sensitive scope. An independently justified
     `review/override-approved` exact-head receipt remains the explicit outage /
     false-positive escape hatch.

The old standalone description, risk-guardrail, test-hint, and release-evidence
comment workflows were removed because they duplicated policy/CI state without
adding an independent safety signal.

### Ruleset migration

The intended default-branch ruleset requires only `policy-gate` and `merge-gate`.
During the one-PR migration that introduces those check names, legacy `pr-policy`
and `review-gate` jobs remain compatibility checks so the existing ruleset cannot
deadlock its own replacement. Remove those compatibility jobs immediately after
the ruleset is switched.

### Guardrails (intentionally manual)

- Merge decisions and risky scope expansion remain explicit human decisions.
- Sensitive scope still requires final-head approval plus independent review.
- A new commit invalidates exact-head approval/review evidence.
- Automation fails loud when required evidence is unavailable; ordinary PRs do
  not depend on the availability of an external review model.

## Builder authority and historical issue #127

The local KittyBuilder SQLite queue/database is the authoritative execution
state. Missions, packet eligibility, claims, attempts, recovery, review
bindings, publication evidence, and merge reconciliation live there. GitHub
remains the PR/CI/review/audit surface; it is not a task scheduler.

GitHub issue **#127 — "KittyBuilder Queue"** is historical bridge metadata only.
Comments there do not create, claim, resume, cancel, or complete Builder work.
A task is executable only after Builder records it durably. Do not double-track
new work in both #127 and the Builder queue.

The current handoff chain is:

1. **Intake.** Convert approved intent into a Builder Mission/initiative and
   durable packets.
2. **Dispatch.** Builder selects eligible work, owns claims/leases/worktrees,
   and launches the bounded packet loop. Workers do not self-select broad work.
3. **Implement/validate/review.** Evidence is bound to the durable attempt and
   exact implementation SHA; a new HEAD invalidates stale review evidence.
4. **Publish.** Builder records the PR link/head and GitHub supplies CI/review
   projection. PR comments remain the human-visible review channel.
5. **Merge/reconcile.** Merge remains approval-gated. Builder reconciles merged
   PR truth back into task state, which unlocks dependent packets.
6. **Continue.** The supervisor may dispatch newly eligible work; there is no
   issue-comment captain queue.

### Read-only / stale agents

Codex, Antigravity, and any older worker sessions are read-only unless
current git/GitHub confirms an active claim. A captain or worker that
finds a stale session should either close its branch or mark it
read-only in `.claude/STATE.md` — do not silently build on top of it.
Before taking over a stale task, inspect local branches, open PRs, and
`.claude/STATE.md` to avoid duplicate branches and conflicting work.

## PR comments are the coordination channel

GitHub PR comments are the single source of truth for review and merge
decisions. Do not rely on Jacob copy-pasting feedback between tools
(ChatGPT, Claude Code, the terminal, etc.).

- The agent opens the PR and posts its own final report there.
- Reviewers (Jacob or ChatGPT) leave feedback as PR comments.
- The agent responds on the PR, pushes fixes, and posts a new final
  report comment — not back in the originating chat.

## Every PR gets a final report comment

After every push (initial open or follow-up fix), post a final report
comment on the PR before stopping. The report must include:

- **Head SHA** — the commit the branch is now at.
- **Changed files** — exact list, scope-relevant.
- **Tests** — the exact command run and the exact pass/fail result
  (e.g. `104/104 passed`, not just "tests pass").
- **Build** — the exact command run and result.
- **Live verification** — if the change is UI, runtime, or ops-facing,
  show evidence from the running app: a screenshot, a `curl` of a new
  route, `./kitty status` / `./kitty doctor --json` output, etc.
  "Code inspection says it works" is not sufficient for UI or
  behavior changes (see `AGENTS.md` Definition of Done).
- **Scope confirmation** — state explicitly: backend touched? routes /
  data / schema changed? fake data added?
- **Stop point** — end with "Stopping here, not merging. Awaiting
  approval." Do not merge without explicit approval.

## UI PRs — visual verification

For any change that affects what Kitty looks like:

1. **Prefer attaching screenshots to PR comments** when the GitHub CLI
   or tooling can upload them.
2. **If attaching binaries is not possible** (GitHub has no
   CLI-accessible issue-asset upload, and `gh gist` rejects binaries),
   provide:
   - computed-style verification — the actual rendered CSS values read
     from the live dev app via `agent-browser eval` or equivalent, and
   - local screenshot paths (e.g. `/tmp/kitty-*.png`) so Jacob can
     eyeball them on his own machine if he wants.
3. Capture **desktop width** and, if the change is responsive,
   **mobile/narrow width**.
4. Screenshots must come from the **live dev app** (`npm run dev` +
   `./kitty up`), not a guess from a static build. State which one was
   used in the report.

Computed-style verification is a stronger signal than a screenshot
eyeball for things like glass blur, grid layout, or theme-token
resolution — include it even when a screenshot is also attached.

## Handling review feedback

When a reviewer leaves a comment asking for a fix:

1. Respond on the PR (not in another chat) acknowledging the feedback.
2. Make the smallest fix that addresses the issue; do not broaden
   scope.
3. Push to the same branch.
4. Post a new final report comment (head SHA, changed files, tests,
   build, what was fixed, whether anything else changed).
5. Stop. Do not merge.

## Merge gate

The stable merge contract is two required outcomes:

- `merge-gate` — deterministic code evidence. It requires `pytest`, `lint`, and
  `typecheck`; when frontend paths change it additionally requires `kitty-chat`
  and `browser-smoke`. Hygiene remains visible but advisory.
- `policy-gate` — trusted governance. Routine changes pass without model review.
  Sensitive scope requires explicit exact-head approval and trusted independent
  review; native UI source/public changes require product-acceptance evidence.

The default branch remains strict/up-to-date: passing evidence must describe the
current integration base rather than a stale branch. Green checks are necessary
evidence, not merge authorization.

Do not merge a PR unless Jacob or ChatGPT explicitly approves the merge. A
"looks good" in another channel is not approval unless it is a direct instruction
for that PR/head.

Before any `gh` command or `git push`, run GitHub operations with the
keyring-authenticated client:

```bash
env -u GITHUB_TOKEN gh ...
env -u GITHUB_TOKEN git push ...
```

This prevents a stale ambient `GITHUB_TOKEN` from overriding keyring
auth (see `AGENTS.md` — this has bitten the repo before).

## What this workflow is not

- It is not a substitute for `AGENTS.md` (agent rules, prime directive,
  testing policy, git/PR conventions). Read both.
- It is not a packet. It does not change execution order or the
  registry.
- It does not authorize autonomous merges or autonomous scope
  expansion.
- It does not make issue #127, the packet README, planning docs, chat prompts,
  Discord, or PR comments into a task queue. Only durable KittyBuilder state
  authorizes execution.
