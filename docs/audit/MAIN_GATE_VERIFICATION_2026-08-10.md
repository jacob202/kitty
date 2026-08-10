# Main Gate Verification — 2026-08-10

**Verified commit:** `d54fd8966edd1f8a14802ed19e26a07917498caf` (`origin/main`)
**Run date:** 2026-08-10 (UTC)
**Runner:** ephemeral Linux container, clean clone, no local Kitty services
**Reason this exists:** GitHub Actions still has not executed a workflow step for
this repository, so no automated verdict exists for current `main`.

`main` at `d54fd896` **fails two of the gates the `Tests` workflow defines**:
`lint` and `typecheck`. Both failures are in one file added by the merge that
created that commit. The repair is on `claude/next-4gj621`; with it applied,
every reproducible gate passes.

This supersedes the `574899d` results in
[`MAIN_GATE_VERIFICATION_2026-08-09.md`](MAIN_GATE_VERIFICATION_2026-08-09.md),
which described a commit that is no longer `main`.

## The Actions outage has not lifted

Read from the Actions API on 2026-08-10 at 23:12Z, most recent 30 runs
(2026-08-10 22:16:31Z through 2026-08-10 23:04:04Z):

| Fact | Value |
|---|---|
| Runs concluding `failure` | 28 |
| Runs concluding `skipped` | 2 |
| Runs concluding `success` | 0 |
| Run wall-clock duration | 3–13 seconds |

The 3–13 second durations and the absence of any success match the
instant-failure pattern documented on 2026-08-09: jobs are assigned no runner
and end before a workflow line executes. The cause remains account-level and is
visible only on the billing page. No branch change clears it.

## Gate results at bare `d54fd896`

Every job in `.github/workflows/tests.yml` reproduced with the workflow's own
commands.

| Workflow job | Command | Result |
|---|---|---|
| `lint` | `ruff check gateway/ tests/ mcp/ workers/ scripts/runpod_worker_smoke_test.py` | **FAIL** — 1 error |
| `typecheck` | `mypy gateway/ mcp/ workers/ scripts/runpod_worker_smoke_test.py` | **FAIL** — 1 error |
| `pytest` | `pytest tests/ -q --tb=short --cov=gateway --cov-report=term-missing --cov-fail-under=73` | 3987 passed, 2 deselected, 29 subtests passed, 42 warnings, 213.61s |
| `pytest` (coverage gate) | same run | 78.40% total, floor 73% — reached |
| `kitty-chat` (unit) | `vitest run` | 341 passed, 45 files, 16.65s |
| `kitty-chat` (build) | `next build` | Compiled successfully, TypeScript clean, 6/6 static pages |
| `browser-smoke` | `next build --webpack` + gateway stub + `next start -p 4000` + `playwright test` | 29 passed, 15 skipped, 47.7s |
| `hygiene` (dead code) | `vulture gateway/ --min-confidence 80 --exclude gateway/kitty-chat/` | exit 0, no findings |

### The two failures

Both are in `mcp/builder/context.py`, added by `d54fd896`
("feat: add KittyBuilder MCP bridge v1").

**`lint`** — `I001 Import block is un-sorted or un-formatted` at
`mcp/builder/context.py:3`. `[tool.ruff.lint.isort]` in `pyproject.toml` leaves
`combine-as-imports` at its default `false`, so
`get_initiative_readonly as get_initiative` cannot share a `from` statement with
an unaliased name. Reproduced on ruff 0.15.8 and 0.16.2, so it is not a
lint-version artifact.

**`typecheck`** — `Incompatible types in assignment (expression has type "None",
variable has type "str")` at `mcp/builder/context.py:252`. `initiative_error`
was first bound in the `except` branch as an f-string, fixing its inferred type
to `str`, and the `else` branch then assigned `None`.

Neither failure changes runtime behaviour: the module's own tests
(`tests/test_mcp_builder_context.py` and the five sibling MCP test modules) pass
at `d54fd896`. These are gate failures, not defects in the bridge.

### How they reached `main`

`d54fd896` is a direct-to-`main` squash with no merge commit and no green check,
landed while Actions cannot run and while the default-branch ruleset that would
require checks is still disabled (issue #399). Nothing in the current setup
could have stopped it. This is the second consecutive checkpoint where `main`
was left red by a merge no gate examined.

## Gate results with the repair applied

Branch `claude/next-4gj621`, `mcp/builder/context.py` only — the aliased import
split onto its own statement, and `initiative_error` pre-declared as
`str | None`.

| Workflow job | Result |
|---|---|
| `lint` | All checks passed |
| `typecheck` | Success: no issues found in 293 source files |
| `pytest` | **3987 passed**, 2 deselected, 29 subtests passed, 42 warnings, 224.71s |
| `pytest` (coverage gate) | **78.38%** total, floor 73% — reached |
| `kitty-chat` (unit) | 341 passed, 45 files |
| `kitty-chat` (build) | Compiled successfully, TypeScript clean, 6/6 static pages |
| `browser-smoke` | 29 passed, 15 skipped |
| `hygiene` (dead code) | exit 0, no findings |

The 15 skipped smoke tests are project-scoped by design: `navigation`, `chat`,
and part of `settings` are desktop-only; `mobile-layout`, `dogfood-mobile`, and
the rest of `settings` are phone-only. Each runs in exactly one of the two
Playwright projects. CI skips the same 15.

### One observed flake, recorded

An intermediate full-suite run — taken while a webpack build and the Playwright
suite were running on the same container — reported
`tests/test_builder_loop.py::TestRecoveryExercise::test_killed_run_packet_recovers_end_to_end`
as failed:

```
gateway.builder_loop.LoopError: task kb_msnuryhv_c60d for loop-test/LP-1 is
running; the loop only starts on a queued task or a blocked task with a stale
attempt
```

The same test passed in isolation (2.58s) and in both uncontended full-suite
runs. The recovery path decides staleness from an attempt's heartbeat age, so
CPU starvation can keep a killed run's attempt looking fresh past the test's
window. Recorded as a load-sensitivity risk in the recovery test, not as a
verdict on the code. It has not been reproduced without concurrent load.

## Environment

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
- **Three advisory steps were not run.** `lychee` needs outbound requests to
  every external URL in `docs/`; `deptry`, `pip-audit`, and `bandit` are all
  `continue-on-error` in the workflow and cannot fail it.
- **Only these two trees.** `d54fd896` and `d54fd896` plus the repair above. Any
  later commit is unverified until this is repeated.
- **A green local gate is not a merge gate.** It cannot block a merge, and the
  default-branch ruleset that would (issue #399) is still disabled.
