# Session Discipline

Derived from 73 analyzed sessions (2026-05-11 → 2026-08-15). Each rule below
maps to a repeated, recorded failure — not a hypothetical.

## Scope containment

- Do exactly what was asked. Never spawn review fleets, parallel agent
  workflows, or broad re-reads of the tree unless Jacob asked for them by name.
- Before touching a file outside the stated scope, stop and ask.
- Smallest diff that solves the problem wins.

## Deliverables

- "Export", "share", or "send" means a real shareable artifact or URL. A path
  under `/tmp` is not an export.
- When asked for a document, prompt, or plan, output the actual content.
  Never a placeholder, never "see above", never a stub to fill in later.

## Verification before claiming

- Never write "fixed", "solved", "working", "complete", or "delivered" unless
  the same message contains the command you ran and its output.
- For a bug: write the failing test first, show it red, fix, show it green on
  that one test. Full suite once at the end — see `## Execution defaults` in
  CLAUDE.md.
- Three failed fix attempts means stop and report the hypotheses eliminated.
  Do not try a fourth.

## Git and branch hygiene

- Before reviewing or reporting on any file, run `git status -sb` and confirm
  the branch. Never review stale working-tree files when the work lives on a
  branch.
- Commit the fix before pushing or opening a PR.
- PR descriptions state the true commit count and any conflict or rebase
  situation. Do not undersell a mess.

## Concurrency

This repo is worked by several agents and sessions at once.

- Before editing, check `git status` and `git log -1`. If the branch moved or
  your edits were reverted, STOP and report. Do not blindly re-apply.
- Never write a "complete" entry to a ledger, HANDOFF, or STATE file without a
  verified artifact backing it.

## Long campaigns

Roughly a third of past sessions died on usage limits mid-merge.

- Break multi-phase work into ~15-minute phases up front and show the list
  before starting.
- Commit at every phase boundary and add one line to `.claude/HANDOFF.md`
  saying what is done and what is next.
- The test is: a cold session must be able to resume from HANDOFF.md alone.
