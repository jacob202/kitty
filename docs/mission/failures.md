# Failures — approaches that did not work, and why

Read this before repeating any of them.

## F1 — `pip install pytest` into the system interpreter

Blocked by PEP 668 (`externally-managed-environment`). Do not reach for
`--break-system-packages`. Use `python3.12 -m venv .venv-ci` — that worked and
matches CI's Python 3.12.

## F2 — Assuming the roadmap's status was current

`docs/ROADMAP.md` Gate 0.1 read "Restore green main … Status: COMPLETE",
verified at `59f598c5`. Believing it would have hidden the actual blocker.
Main had been red for 8 commits.

The claim was *true when written* and falsified by later merges into the same
branch it described. **A status line is a measurement with a timestamp, not a
property of the repo.** Re-measure; do not re-read.

## F3 — Treating all 7 test failures as environmental

The first four failures were plainly container artefacts (`gh` missing,
launchd, checkout path), which made "the rest are environmental too" an easy
and wrong inference. Three were genuine committed-state defects that would
have failed CI identically.

What separated them: running the underlying check with the CI environment
override applied, so environmental noise dropped out and only real failures
remained. Do that before classifying a failure as "just the sandbox".

## F4 — Bumping mem0ai to clear the openai conflict

Considered and rejected, not attempted. mem0ai 2.0.14 drops the openai upper
bound and looks like the clean fix, but 0.1.118 → 2.0.x is a major-version API
break against `gateway/memory.py` and `gateway/doctor.py`, unverifiable without
a live memory backend. Bundling it into a CI repair would have made a one-line
green-main fix unmergeable.

Recorded as its own slice. If a future session attempts it: the blast radius is
`memory.py`, `doctor.py`, `memory_graph.py`, `routes/completions.py`,
`routes/repairs.py`, and two scripts.

## F5 — Reaching for issue #336's acceptance test in a container

Not attempted, deliberately. The hard acceptance test needs a browser, a
running Kitty, RunPod credentials and real GPU spend. None exist here.

The failure mode this avoids is the one issue #336 names explicitly:
"Generated substitutes, mock contact sheets, and prompt-only 'edits' fail the
slice." A mocked RunPod call producing a fixture image would have looked like
progress and been worth less than nothing — it would have to be un-believed
later. `IMPLEMENTED-NOT-VERIFIED` with the inaccessible check named is the
honest state.

## F6 — Editing `.claude/` checkpoints without checking whose they were

`CLAUDE.md` forbids clobbering another active workstream's checkpoint, and
STATE.md was written by the `recovery/roadmap-2026-07-31` session.

What made the edit safe was not urgency but verification: that session's PR
(#331) was merged, and its own declared `invalidation_conditions` — "HEAD
advances past 9c446874" — had already fired, because main was at `b68268b`.
A checkpoint that has invalidated itself is not a live workstream.

Check the invalidation conditions before deciding a checkpoint is stale. Do
not decide it from the timestamp.
