# PR Review Workflow

How agents and reviewers coordinate on Kitty pull requests. This is the
coordination contract — read it before opening a PR.

## Task inbox — KittyBuilder Queue (issue #127)

GitHub issue **#127 — "KittyBuilder Queue"** is the single task inbox for
KittyBuilder work. A task only counts once it appears as a comment on
that issue. Ideas, chat prompts, and stale handoffs in other channels
are not tasks — they are noise until they land on #127.

The handoff chain:

1. **Intake.** ChatGPT or Jacob posts a new task comment on #127. Each
   comment must include `TASK:`, `BRANCH:`, `SCOPE:`, `DO NOT:`,
   `VALIDATION:`, and `STOP:` (see the issue body for the exact format).
2. **One captain, not self-selected workers.** Exactly one captain reads
   the queue and dispatches the next task. Workers do not self-select
   broad work from the issue, the registry, or the packet README —
   they take the specific task the captain assigns. If a task comment
   does not clearly include scope, validation, and a stop point, the
   worker asks for clarification on #127 instead of guessing.
3. **Claim.** The worker replies `CLAIMED` with the branch name and
   timestamp on the task comment before starting. If another worker
   already claimed the same task, do not start. A stale claim (no update
   for a long time) may be taken over with a `TAKING OVER` reply after
   inspecting existing branches/PRs.
4. **Implement.** Start from clean, up-to-date `main`. Create the
   requested branch. Do only the stated scope.
5. **Open PR.** The worker opens a PR for the implementation branch.
   **PRs are for implementation branches; issue #127 is for task intake
   and coordination — never the other way around.** Do not treat
   issue #127 as a PR, and do not use an implementation branch as a
   task queue.
6. **Report on the PR.** Post the required final report comment on the
   PR (see "Every PR gets a final report comment" below).
7. **Close the loop on #127.** Comment back on issue #127 with the PR
   number, then stop and wait.
8. **Review/merge on the PR.** ChatGPT and Jacob review through PR
   comments and merge there. The worker does not merge.

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
- It does not make the packet README, planning docs, or chat prompts
  into a task queue. Only comments on issue #127 are tasks.
