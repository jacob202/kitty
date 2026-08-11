# Main Gate Verification — 2026-08-10, and the end of the Actions outage

**Commits examined:** `d54fd8966edd1f8a14802ed19e26a07917498caf` and
`6de35bde4da298ca7e1c51401397eda201bf6dcc` (both `origin/main`)
**Run date:** 2026-08-10 into 2026-08-11 (UTC)
**Runner:** ephemeral Linux container, clean clone, no local Kitty services

Two findings, in the order they happened.

1. `main` at `d54fd896` **failed two of the gates the `Tests` workflow defines**,
   `lint` and `typecheck`, and no automated verdict existed to say so.
2. The GitHub Actions outage **ended during this session**, between 23:03Z and
   23:20Z on 2026-08-10. `Tests` now executes for real, and `main` at `6de35bde`
   passes it.

Out-of-band verification is therefore retired. CI is the gate again. This
supersedes [`MAIN_GATE_VERIFICATION_2026-08-09.md`](MAIN_GATE_VERIFICATION_2026-08-09.md).

## The outage, and exactly when it ended

`Tests` run history read from the Actions API:

| Window | Runs | Wall-clock duration | Outcome |
|---|---|---|---|
| 2026-08-09 08:27Z – 2026-08-10 23:03Z | 20 | 3–13 seconds | every one `failure` |
| 2026-08-10 23:20Z onward | 6 | 200–314 seconds | mixed, on their merits |

The 3–13 second runs never started: no runner, empty check output, no logs. The
200–314 second runs are real executions. The last no-runner `Tests` run was
`a736ee52` on `docs/architecture-ratification-governance` at 23:03:51Z; the first
genuine one was `59900f20` on `jacob202/kproof-001-status-probe` at 23:20:19Z.

Nothing in the repository changed to cause this. The block was account-level, and
it cleared at the account level.

### Current CI verdicts

| Branch | Head | `Tests` result |
|---|---|---|
| `main` | `6de35bde` | **success**, 275s |
| `main` | `d13cd186` | **success**, 314s |
| `docs/architecture-ratification-governance` (#450) | `a7e33384` | failure, 245s — a real result, not the outage |

## What `main` at `d54fd896` actually failed

Verified before the outage lifted, by reproducing every job in
`.github/workflows/tests.yml` with the workflow's own commands.

| Workflow job | Result at `d54fd896` |
|---|---|
| `lint` | **FAIL** — 1 error |
| `typecheck` | **FAIL** — 1 error |
| `pytest` + coverage | 3987 passed, 2 deselected, 29 subtests, 78.40% vs 73% floor |
| `kitty-chat` (unit) | 341 passed, 45 files |
| `kitty-chat` (build) | compiled, TypeScript clean, 6/6 static pages |
| `browser-smoke` | 29 passed, 15 skipped |
| `hygiene` (dead code) | exit 0, no findings |

Both failures were in `mcp/builder/context.py`, added by the KittyBuilder MCP
bridge merge:

- **`lint`** — `I001 Import block is un-sorted or un-formatted` at line 3.
  `[tool.ruff.lint.isort]` leaves `combine-as-imports` at its default `false`, so
  `get_initiative_readonly as get_initiative` cannot share a `from` statement
  with an unaliased name. Reproduced on ruff 0.15.8 and 0.16.2, so it was not a
  lint-version artifact.
- **`typecheck`** — `Incompatible types in assignment (expression has type
  "None", variable has type "str")` at line 252. `initiative_error` was first
  bound in the `except` branch as an f-string, fixing its inferred type to `str`,
  and the `else` branch then assigned `None`.

Neither changed runtime behaviour, and the bridge's own tests passed at
`d54fd896`. They were gate failures, not defects in the bridge.

### How they reached `main`, and what closed the hole

`d54fd896` was a direct-to-`main` squash with no green check, landed while
Actions could not run and while the default-branch ruleset that would require
checks is still disabled (issue #399). Nothing in the setup at that moment could
have stopped it.

Both failures were fixed independently in #453
(`b2a0dd2 feat(ci): gate pushes locally, and fix the three failures that found`),
which also added `scripts/hooks/pre-push` — a local gate that catches exactly
this class of failure before it can reach `main`. The `typecheck` repair landed
there character-for-character identical to the one derived here; the `lint`
repair differs only in import layout. That convergence is corroboration, not
duplication, but the fix belongs to #453 and this branch carries no code change.

#453 also found a third failure this verification did not:
`gateway/image_quality.py`. That gap is unexplained and is the one open thread
from this exercise.

## One observed flake, recorded

An intermediate full-suite run — taken while a webpack build and the Playwright
suite were running on the same container — reported
`tests/test_builder_loop.py::TestRecoveryExercise::test_killed_run_packet_recovers_end_to_end`
as failed:

```
gateway.builder_loop.LoopError: task kb_msnuryhv_c60d for loop-test/LP-1 is
running; the loop only starts on a queued task or a blocked task with a stale
attempt
```

The same test passed in isolation (2.58s) and in all three uncontended
full-suite runs. The recovery path decides staleness from an attempt's heartbeat
age, so CPU starvation can keep a killed run's attempt looking fresh past the
test's window. Recorded as a load-sensitivity risk in the recovery test, not as
a verdict on the code. It has not been reproduced without concurrent load.

## Environment used for the out-of-band runs

| Component | Version |
|---|---|
| Python | 3.12.3 (workflow pins 3.12) |
| Dependencies | `requirements.txt` installed as pinned, into a container-local venv |
| mypy | 2.3.0 (workflow installs unpinned; this is current) |
| ruff | 0.16.2 (and 0.15.8, same result) |
| Node | 22.22.2 (workflow pins 22) |
| npm install | `npm ci` from `package-lock.json` |
| Playwright | 1.62.1, run against the container's own Chromium via the config's supported `PLAYWRIGHT_CHROMIUM_PATH` |

`KITTY_EXPECTED_CANONICAL_CHECKOUT` was set to the container checkout path, the
same override the workflow applies for runners.

## What this does not prove

- **Nothing about Jacob's Mac.** No local service, launchd, credential, provider,
  Builder database, or Open WebUI state was reachable or inspected. Builder's
  queue database does not exist in this container, so every Builder projection
  read `unavailable` rather than empty.
- **Three advisory steps were never run.** `lychee` needs outbound requests to
  every external URL in `docs/`; `deptry`, `pip-audit`, and `bandit` are all
  `continue-on-error` in the workflow and cannot fail it. CI now runs them again
  on its own terms.
- **The out-of-band results describe `d54fd896` only.** `main` has since moved to
  `6de35bde`, whose verdict comes from CI, not from this container.
- **A green local gate was never a merge gate.** The default-branch ruleset that
  would require checks (issue #399) is still disabled, so a green `Tests` run on
  `main` still cannot block the next unchecked merge. #453's pre-push hook is a
  local guard, not a server-side one.
