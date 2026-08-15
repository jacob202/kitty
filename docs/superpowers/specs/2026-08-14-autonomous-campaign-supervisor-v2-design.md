# Design: Autonomous Campaign Supervisor v2

## Goal

Make the unattended Builder walking skeleton executable from clean worktrees by adding an explicit runtime preflight, then build the stateless supervisor and strict Claude adapter on top of it.

## Evidence and decision

The approved v1 Mission reached Builder but could not execute safely. The free worker tried to create a 646 MB worktree-local virtual environment because clean worktrees do not inherit the root `venv`; a symlink workaround was correctly rejected by Builder's clean-worktree guard. The verified root environment runs the declared baseline (`192 passed, 1 skipped`). The fix is to propagate the existing root runtime through process `PATH` and use portable `python -m ...` validation commands. No worktree files, symlink, package installation, queue, or second authority is needed.

## Boundaries

- KittyBuilder remains the only durable authority.
- Runtime preflight is limited to the existing worker adapter and validation executor; it must fail clearly when the configured runtime is unavailable and must never install dependencies.
- The supervisor remains stateless, lock-protected, capped at two canonical Builder runs, and unable to mutate task state or publish.
- Claude adapter remains strict: Sonnet worker, Opus reviewer, no fallback, fake-CLI-only tests.
- Discord remains a typed projection/control surface, never a shell, approval, publication, or merge authority.

## Acceptance evidence

A clean Builder worktree can run worker and declared validation commands using the root runtime without creating untracked setup files. The supervisor Mission can advance through normal Builder review/manual-publication gates, repeated ticks duplicate nothing, and provider failures remain durable Builder truth.
