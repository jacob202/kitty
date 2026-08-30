# Kitty Quickstart — 3 commands

| What | Command |
|------|---------|
| Continue where you left off | `catch me up` |
| Ship current work | `ship it` |
| Run quality gates | `/qg` (or `/qg all`) |

## How it works

- Tests only run in CI (on PRs). I won't run them mid-session unless you say `/qg`.
- Say `catch me up` at the start of every session to rebuild context.
- Say `ship it` when you're done — it commits, pushes, creates the PR with a description.
- Every PR gets auto-reviewed by an agent (posts a review comment).
- Session-end protocol runs automatically on `ship it` or `i'm done`.
