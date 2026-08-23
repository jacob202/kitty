# Delivery pipeline baseline — 2026-08-23

Measured from live GitHub Actions history before any change in this lane, so the
next 20–30 PRs can be compared against something real rather than a memory.

- Base: `origin/main` @ `9d466214197cdd11a5e2ed08da7e8eb3c8c15308`
- Reproduce the aggregate numbers with `python scripts/ci_metrics.py --window-days 14`
  (it needs GitHub API access; the numbers below were read from the Actions API
  directly).

## Full job breakdown — docs-only merge to `main`

Run [32626738131](https://github.com/jacob202/kitty/actions/runs/32626738131),
the push that merged PR #603. PR #603 changed one Markdown file. Its own PR run
correctly skipped every code and browser job in 38 seconds. The merge then ran
everything:

| job | runner seconds | notes |
| --- | --- | --- |
| changes | 4 | |
| merge-gate | 3 | |
| lint | 10 | |
| hygiene | 39 | advisory; gates nothing |
| kitty-chat | 69 | |
| typecheck | 99 | mypy 91 s |
| browser-smoke | 201 | playwright install 21 s, next build 43 s, tests 52 s |
| pytest | 305 | dependency install 42 s, suite 252 s |
| **total** | **730 (12.2 runner-minutes)** | |

Wall clock 9 m 29 s (07:52:33 → 08:02:02 UTC), of which roughly 4 minutes was
runner queueing.

Nothing in those 12.2 runner-minutes could have detected a failure the PR gate
missed. The default-branch ruleset requires strict up-to-date checks with zero
bypass actors, so the merge commit carries the exact tree the PR head validated.

## Wall-clock spread, 20 most recent completed `Tests` runs

| event | n | range | median |
| --- | --- | --- | --- |
| pull_request | 12 | 0 m 38 s – 7 m 40 s | ~5 m 05 s |
| push to main | 8 | 4 m 46 s – 9 m 29 s | ~5 m 04 s |

Cancelled superseded runs: 5 of the 40 most recent `Tests` runs (12.5%), all
from pushes onto a branch whose previous run was still in flight.

## Draft PR behaviour

`.github/workflows/tests.yml` triggered on a bare `pull_request` with no draft
condition, so a PR opened as a draft ran the full applicable suite on open and
on every subsequent push. `ready_for_review` was not a trigger type at all.

## Model review breadth

`PR Agent Review` ran 30 workflow runs in the two hours before this baseline. The
`agent-review` job called the external model on every non-draft
`opened`/`synchronize`/`reopened`/`ready_for_review` event regardless of scope,
including docs-only PR #603
([run 32626680763](https://github.com/jacob202/kitty/actions/runs/32626680763)).
`policy-gate` consumes review evidence only for sensitive scope, so every one of
those calls on an ordinary PR was evidence nothing read.

Up to three workflow runs existed per head SHA, because metadata events
(`edited`, `labeled`, `unlabeled`) each get their own concurrency group. Those
runs evaluate `policy-gate` only, which is correct and cheap.

## `pytest` cost structure

From the same run: 42 s dependency install, 252 s suite, on 320 test files with
a `--cov-fail-under=73` floor. Per-test timings did not exist anywhere in CI
history, which is why nothing could name the slow tests. The nightly
`suite-profile` job now records `--durations=50` on every run, so the next pass at
suite speed starts from data instead of a guess. No parallelism was introduced:
this repository has SQLite and runtime-isolation-heavy tests and unsafe
parallelisation manufactures flakes.

## What this baseline cannot answer

- Draft pushes avoided — Actions does not record runs that were never triggered.
- Actionable vs. noise review findings — needs comment bodies, not run metadata.
- Repeated false positives — needs cross-night finding identity, which no source
  in this window provides.

`scripts/ci_metrics.py` reports these as `null` with the reason attached rather
than estimating them.
