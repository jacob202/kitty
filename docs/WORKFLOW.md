# PR Review Workflow

How agents and reviewers coordinate on Kitty pull requests. This is the
coordination contract — read it before opening a PR.

## Workflow automation baseline (2026-07-30)

This repository now automates low-risk GitHub workflow steps while preserving
manual control for risky actions.

### Automated now

1. **PR intake formatting**
   - `.github/pull_request_template.md` pre-fills required sections.
   - `pr-description-check.yml` still enforces `## Summary` and `## Test plan`.
2. **Issue intake structure**
   - `.github/ISSUE_TEMPLATE/bug_report.yml` standardizes bug triage evidence.
   - `.github/ISSUE_TEMPLATE/workflow_automation.yml` captures automation
     requests with scope, guardrails, and success metrics.
3. **PR scope triage**
   - `.github/workflows/pr-auto-label.yml` applies path-based area labels from
     `.github/labeler.yml`.
   - The workflow creates missing `area/*` labels and emits a summary of changed
     file count + final labels for observable triage logs.
4. **Risk guardrails**
   - `.github/workflows/pr-risk-guardrails.yml` detects sensitive scope (auth,
     secrets/env-like files, dependency roots, CI workflows).
   - Risky PRs receive `risk/high` + `risk/manual-approval` labels and require
     explicit manual approval in the PR body (`Manual approval: YES` or checked
     manual-approval checkbox).
5. **Selective test hints**
   - `.github/workflows/pr-test-hints.yml` posts scoped validation command
     suggestions based on changed paths.
6. **Release evidence comment**
   - `.github/workflows/pr-release-evidence.yml` posts a PR comment summary from
     completed `Tests` workflow runs (run URL, conclusion, per-job outcomes).
7. **Current-head agent review**
   - `.github/workflows/pr-agent-review.yml` replaces stale review evidence on
     every PR head change and re-runs the advisory reviewer for that exact SHA.

### Guardrails (intentionally manual)

- Approvals, merge decisions, and risky scope expansion remain manual.
- Auth/secrets/env/destructive operations still require explicit human approval.
- Automation must fail loud; unknown labels or script errors fail the workflow.

### Phased rollout

- **Phase 1 (shipped):** intake templates + PR area auto-labeling + logs.
- **Phase 2 (shipped):** risk guardrails + selective test hints.
- **Phase 3 (shipped baseline):** PR CI evidence comments; age-based stale
  auto-closure was retired because age is not evidence of completion.
- **Phase 4 (current):** Builder-owned delivery/supervision with GitHub as
  review, CI, and audit projection rather than a second task queue.

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

Do not merge a PR unless Jacob or ChatGPT explicitly approves the merge.
A green CI check is not approval. A "looks good" in a different channel
is not approval. The approval must appear as a PR comment or a direct
instruction to merge.

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
