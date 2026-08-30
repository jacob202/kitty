# Main Gate Verification — 2026-08-09

**Verified commit:** `574899d64dbc5f27af4140d7c2d33222b1e3f248` (`origin/main`)
**Run date:** 2026-08-09 (UTC)
**Runner:** ephemeral Linux container, clean clone, no local Kitty services
**Reason this exists:** GitHub Actions has not executed a workflow step for this
repository since 2026-08-06, so no automated verdict exists for current `main`.

`main` passes every deterministic gate the `Tests` workflow defines. The red
checks on GitHub are an Actions execution outage, not a code result.

## Why an out-of-band verification was needed

`Tests` (`.github/workflows/tests.yml`) run history, read from the Actions API on
2026-08-09:

| Fact | Value |
|---|---|
| Last passing `Tests` run on `main` | run `30965868674`, 2026-08-05 01:15:39Z, head `6a6d6256` |
| Last passing `Tests` run on any branch | run `31075781705`, 2026-08-06 05:59:13Z, head `a6fa3c3c`, branch `closeout/2026-08-05-architecture-reconciliation` |
| Commits landed on `main` since `6a6d6256` | 36 |
| `Tests` runs created after 2026-08-06 05:59:13Z | every one concluded `failure` |

The 60 most recent `Tests` runs were enumerated (2026-08-05 00:38Z through
2026-08-09 04:15Z). Within that window there is no success after
`31075781705`.

### The failing runs never started

Sampled failing jobs — `pytest` (`92989887851`) from run `31216104282` on `main`,
and `publish-evidence` (`93196464744`) from run `31294192675`:

| Field | Observed |
|---|---|
| `runner_id` | `0` |
| `runner_name` | empty |
| `started_at` vs `completed_at` | 1–2 seconds apart |
| Job log download | HTTP 404 |
| Check-run `output.title` / `summary` / `text` | all empty |

In run `31216104282` all five independent `Tests` jobs failed within the same
second (the sixth, `browser-smoke`, was skipped because it `needs: kitty-chat`).
The same instant-failure pattern appears on every event type and every branch. No
workflow line executed, so these results carry no information about the code. The cause is account-level — either a failed payment
method or an exhausted Actions allowance/spending limit on a private repository —
and it is visible only on the account billing page, not through the API. No
branch change can clear it.

## Gate results at `574899d`

Every job in `.github/workflows/tests.yml` was reproduced locally with the same
commands the workflow runs.

| Workflow job | Command | Result |
|---|---|---|
| `lint` | `ruff check gateway/ tests/ mcp/ workers/ scripts/runpod_worker_smoke_test.py` | All checks passed |
| `typecheck` | `mypy gateway/ mcp/ workers/ scripts/runpod_worker_smoke_test.py` | Success: no issues found in 286 source files |
| `pytest` | `pytest tests/ -q --tb=short --cov=gateway --cov-report=term-missing --cov-fail-under=73` | **3932 passed**, 2 deselected, 29 subtests passed, 42 warnings, 227.18s |
| `pytest` (coverage gate) | same run | **78.31%** total, floor 73% — reached |
| `kitty-chat` (unit) | `vitest run` | **339 passed**, 45 files, 18.11s |
| `kitty-chat` (build) | `next build` | Compiled successfully, TypeScript clean, 6/6 static pages |
| `browser-smoke` | `next build --webpack` + `next start -p 4000` + `playwright test` | **29 passed**, 15 skipped, 46.3s |
| `hygiene` (dead code) | `vulture gateway/ --min-confidence 80 --exclude gateway/kitty-chat/` | exit 0, no findings |

The 15 skipped smoke tests are project-scoped by design: `navigation`, `chat`,
and part of `settings` are desktop-only; `mobile-layout`, `dogfood-mobile`, and
the rest of `settings` are phone-only. Each runs in exactly one of the two
Playwright projects. CI skips the same 15.

### Environment

| Component | Version |
|---|---|
| Python | 3.12.3 (workflow pins 3.12) |
| Dependencies | `requirements.txt` installed as pinned |
| mypy | 2.3.0 (workflow installs unpinned; this is current) |
| ruff | 0.16.2 |
| Node | 22.22.2 (workflow pins 22) |
| npm install | `npm ci` from `package-lock.json` |
| Playwright | 1.62.0, repository-pinned binary |
| Chromium | container build, selected through the config's supported `PLAYWRIGHT_CHROMIUM_PATH` |

`KITTY_EXPECTED_CANONICAL_CHECKOUT` was set to the container checkout path, the
same override the workflow applies for runners.

## What this does not prove

- **Nothing about Jacob's Mac.** No local service, launchd, credential, provider,
  Builder database, or Open WebUI state was reachable or inspected.
- **`hygiene` is not fully covered.** The `lychee` broken-link step needs outbound
  requests to every external URL in `docs/` and was not run. `deptry` is
  `continue-on-error` in the workflow and was not run.
- **Only `574899d`.** Any later commit is unverified until this is repeated.
- **A green local gate is not a merge gate.** It cannot block a merge, and the
  default-branch ruleset that would (issue #399) is still disabled.

## Related open work

- **#442** cuts the Actions minute burn and makes `make ci` match these commands
  exactly. Draft, blocked on Jacob's CI-scope approval.
- **#441** records the same Actions outage in `docs/PROJECT_STATUS.md` and states
  that red Actions results cannot serve as code-quality evidence. This file
  supplies the missing half: what the gates actually say.
- **#399** owns branch protection and the workflow ledger; both need account-level
  changes.
