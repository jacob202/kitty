# Handoff — PR triage: #365 reviewed, #361 reviewed, #360 recovered

## Goal
Review #365 (image-agent A3) and #361 (delta reconcile), then recover #360 (session audit + writing rule) onto a clean branch.

## State

- **Done:** #365 and #361 confirmed clean — all checks green, MERGEABLE, no issues found. Can't self-approve from an agent shell (GitHub rejects).
- **Done:** #360 recovered to `recovery/open-session-audit-2026-08-01` (88cf8735), off main at 037052b6. Three files: `docs/research/open-session-audit-2026-08-01.md` (the full session audit), `CLAUDE.md` (+"How to write to Jacob" section), `config/PREFERENCES.md` (+one-line writing rule mirror).
- **Dropped:** stale `.claude/HANDOFF.md` and `.claude/STATE.md` changes from original #360 (session state from a different session).
- **Not pushed:** fence denies `git push*`, `gh pr create*`, `gh pr merge*`.

## Gotchas

- GitHub rejection: `gh pr review --approve` returns "Can not approve your own pull request" for own PRs. Three agent sessions (Claude Code, OpenCode, Codex) are listed as co-authored — GitHub treats them as self-reviews.
- Both fences (`git push*` → deny, `gh pr create*` → deny) prevent pushing the recovery branch or opening a draft PR from the agent shell.

## Next step

Jacob: merge #361 first, then open a draft PR from `recovery/open-session-audit-2026-08-01` to main (recovered #360). Then merge #365 (image-agent A3) after convenient.

## Files changed this session

- `docs/research/open-session-audit-2026-08-01.md` (new, from #360)
- `CLAUDE.md` (+"How to write to Jacob" section)
- `config/PREFERENCES.md` (+one-line writing rule mirror)
