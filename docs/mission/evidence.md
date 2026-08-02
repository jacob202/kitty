# Evidence

Commands run this session and what they returned. Nothing here is
reconstructed from memory; each entry was produced during this run.

## E1 — main is red, and why

`mcp__github__actions_list` on `tests.yml`, branch `main`, most recent runs:

```
1139 b68268b0 completed failure 2026-08-01T02:39:23Z
1134 fb4e3002 completed failure 2026-07-31T22:45:06Z
1133 415580fb completed failure 2026-07-31T22:44:42Z
1132 e6b74846 completed failure 2026-07-31T22:43:40Z
1127 8da5e079 completed failure 2026-07-31T22:41:41Z
1126 19865ce4 completed failure 2026-07-31T22:41:16Z
1125 4618e29b completed failure 2026-07-31T22:40:44Z
1124 092372b1 completed failure 2026-07-31T22:40:12Z
```

Failed-job log for run 1139 (`pytest`, job 91316234344), verbatim:

```
ERROR: Cannot install -r requirements.txt (line 29) and openai<2.50.0 and
>=2.49.0 because these package versions have conflicting dependencies.

The conflict is caused by:
    The user requested openai<2.50.0 and >=2.49.0
    mem0ai 0.1.118 depends on openai<1.110.0 and >=1.90.0

ERROR: ResolutionImpossible
##[error]Process completed with exit code 1.
```

Only 1 of 6 jobs failed — `pytest` — and it never reached a test.

## E2 — reproduced locally before changing anything

`python3.12 -m venv .venv-ci && .venv-ci/bin/pip install -r requirements.txt`
returned the identical `ResolutionImpossible` and the identical conflict
lines. The defect is in the file, not in the runner.

## E3 — blame

```
git log -p --follow -- requirements.txt
commit 600c0faec2815325911bd46888fe4ecdc447de9d
-openai>=1.90.0,<1.110.0
+openai>=2.49.0,<2.50.0
```

Subject: `chore(deps): bump openai from 2.48.0 to 2.49.0`. The removed range
is character-for-character mem0ai 0.1.x's requirement — it existed because of
the coupling, and Dependabot overwrote it without seeing it. Seven earlier
commits in the same file's history show `+openai>=1.90.0,<1.110.0`, so the
constraint had held since the pin was introduced.

## E4 — repair verified by clean install

After the fix, a **freshly recreated** venv (`rm -rf .venv-ci`, rebuild):

```
REQS_INSTALL_EXIT=0
mem0ai   0.1.118
openai   1.109.1
```

Resolution succeeds. The comment added above the pin records the coupling so
the next bump does not silently reintroduce it.

## E5 — full suite, one run

Exact CI command
(`pytest tests/ -q --tb=short --cov=gateway --cov-report=term-missing --cov-fail-under=73`):

```
Required test coverage of 73% reached. Total coverage: 77.50%
7 failed, 3452 passed, 2 deselected, 16 warnings, 29 subtests passed in 298.26s
```

Failures, each classified by reading its traceback rather than by assumption:

| Test | Cause | Real? |
| --- | --- | --- |
| `test_resume_script::test_exits_zero` | `FileNotFoundError: 'gh'` | container-only |
| `test_kitty_launcher_runtime::test_down_handles_launchd_ui_and_owned_listeners` | launchd is macOS-only | container-only |
| `test_check_continuity_state` ×2 (`test_passes_with_generous_limit`, `test_zero_days_warns_but_does_not_block`) | `repo:canonical_checkout` expects `~/Projects/kitty`; CI sets `KITTY_EXPECTED_CANONICAL_CHECKOUT` (`tests.yml:15`) | container-only |
| `test_check_continuity_state` ×2 (`test_current_checkpoint_within_seven_days`, `test_json_output_is_structured`) | checkpoint metadata defects below | **real** |
| `test_cold_start_acceptance::test_clean_reader_can_resolve_all_cold_start_questions` | checkpoint metadata defects below | **real** |

## E6 — the real failures, isolated

Re-run with the CI override applied
(`KITTY_EXPECTED_CANONICAL_CHECKOUT=/home/user/kitty scripts/check_continuity_state.py`)
to strip the environmental noise. What survived:

```
FAIL handoff:metadata      .claude/HANDOFF.md checkpoint metadata is missing keys: ['pull_request']
FAIL state:head            head_sha is not a full lowercase SHA: '9c446874'
FAIL state:pull_request    an active pull request must declare state OPEN and a head_sha
WARN state:branch          recorded branch 'recovery/roadmap-2026-07-31' does not match current branch
PASS repo:canonical_checkout   /home/user/kitty
```

Confirmed these files are byte-identical to `main` (`git diff main -- .claude/`
returned empty), so the defects are main's, not this branch's.

Validator rules, read from source rather than inferred:
- `gateway/context_receipt.py:693` — `head_sha` must match the full-SHA pattern
- `gateway/context_receipt.py:840` — `pull_request: null` returns PASS,
  `"no active PR claimed"`; `:854` fails any block not `OPEN` with a `head_sha`
- `gateway/context_receipt.py:448` — `pull_request` is a required key

STATE.md recorded `9c446874` while main sat at `b68268b`, and declared merged
PR #331 active. Its own `invalidation_conditions` ("HEAD advances past
9c446874") had already fired, so it was safe to rewrite. Repaired to a full
SHA and `pull_request: null`; HANDOFF.md gained the missing key.

## E6b — main is green again (closes Gate 0.1)

After PR #339 merged as `8c58f52`:

```
1145 8c58f52d completed success 2026-08-01T05:46:08Z
1139 b68268b0 completed failure 2026-08-01T02:39:23Z
1134 fb4e3002 completed failure 2026-07-31T22:45:06Z
```

Run 1145 ends the red streak that ran from `092372b1` through `b68268b0`.
Gate 0.1 and Gate 0.8 are VERIFIED on this run, not on the PR-head checks.

## E7 — red PRs are mergeable on `main`

Checked after slice 0 merged, to find out why a broken bump reached main at
all. The answer was not the one the plan assumed.

PR #322 (`dependabot/pip/openai-2.49.0`, the PR carrying `600c0fa`) check runs:

```
pytest            failure   completed 2026-07-31T05:25:32Z  (job 91080470314)
lint              failure   completed 2026-07-31T05:25:28Z
hygiene           failure   completed 2026-07-31T05:25:32Z
check-description failure   completed 2026-07-31T05:25:18Z
auto-label        failure   completed 2026-07-31T05:25:26Z
suggest-tests     failure   completed 2026-07-31T05:25:16Z
risk-guardrails   failure   completed 2026-07-31T05:25:13Z
```

Merge commit `19865ce`, authored **2026-07-31 16:41:13 -0600** — about eleven
hours after `pytest` went red, with the red check still standing.

It was one of six Dependabot merges inside 4.5 minutes:

```
4618e29  16:40:42  #323
19865ce  16:41:13  #322   <- carries the breaking openai pin
8da5e07  16:41:38  #321
e6b7484  16:43:38  #311
415580f  16:44:39  #312
fb4e300  16:45:03  #313
```

`mem0ai>=0.1.118` had been pinned since `a45f161` (2026-07-26), five days
earlier, so #322 was intrinsically broken on its own — not a semantic conflict
between concurrently-merged PRs. Its own CI said so and was overridden.

**Conclusion:** the tests gate works. Nothing bypassed it. `main` simply has no
enforced required status checks, so red is mergeable. Adding another CI check
would add another ignorable red mark. The fix is branch protection, which needs
repo admin.

## E8 — issue #336 claims checked against code

Method: read the named files, not the issue's summary of them. Results in
`grounding.md` § "Image subsystem". All six claims TRUE. Key line numbers:
`image_plan.py:61` (plan built, never stored), `extended.py:406` vs `:415`
(`plan_id` absent from generate, `guidance_tags` absent from generate),
`workers/comfy_worker/app.py:704` (workflow hardcoded), migrations stop at
`028` (no session table).

## E9 — slice A1, durable image sessions

`gateway/image_sessions.py` + `gateway/migrations/029_image_sessions.sql`.

```
.venv-ci/bin/python -m pytest tests/test_image_sessions.py tests/test_image_jobs.py -q
76 passed in 5.64s
```

33 new tests, 43 existing `image_jobs` tests still green — the new migration
and the deferred `session_id` column did not disturb the job store.

One test was wrong on the first run and the code was right:
`test_succeeded_job_without_artifact_is_rejected` tried to build a
succeeded-but-artifactless job to feed `set_anchor`, and
`image_jobs.transition` refused to create that state
(`gateway/image_jobs.py:423`). The branch is unreachable through the normal
path. Rewritten as `test_job_store_prevents_artifactless_success`, which pins
the upstream invariant instead of testing an impossible state.
`set_anchor`'s own artifact check stays as defence in depth for rows that
predate the guard.

This verifies A1's stated acceptance. It does **not** verify any user-visible
behaviour — no image was generated, no browser was involved. That is A6.

## E10 — slice A3, bounded image-specialist controller

`gateway/image_agent.py` + `tests/test_image_agent.py`.

```
.venv/bin/python -m pytest tests/test_image_agent.py -q
32 passed in 5.39s

.venv/bin/python -m pytest tests/test_image_plans.py tests/test_image_sessions.py \
  tests/test_image_jobs.py tests/test_image_recipes.py tests/test_image_router.py \
  tests/test_image_cancel.py tests/test_image_backends.py tests/test_db.py -q
161 passed in 16.90s

.venv/bin/python -m ruff check gateway/image_agent.py tests/test_image_agent.py
All checks passed!

.venv/bin/python -m mypy gateway/image_agent.py
Success: no issues found in 1 source file

.venv/bin/python -m vulture gateway/image_agent.py --min-confidence 80
(no output)
```

Two test-harness defects were found and fixed here, both in the new tests
rather than in shipped code. `image_recipes` binds `KITTY_DB_FILE` at import
(`gateway/image_recipes.py:13`), so redirecting `gateway.paths.KITTY_DB_FILE`
alone would have written the recipe table into the real database — the
fixture now monkeypatches the module-level name, matching
`tests/test_image_recipes.py:23`. And `image_jobs` has no `created → running`
transition (`gateway/image_jobs.py:56`), so the anchor helper goes through
`submitted` like the real dispatch path does.

`test_edit_is_refused_when_no_recipe_supports_img2img` forces the routing
decision rather than disabling recipes: all four default recipes declare
`supports_img2img`, so disabling them leaves zero available recipes and the
test would have passed on the wrong error.

This verifies A3's stated acceptance. Every LLM call is a scripted stub — no
real model output was parsed, no image was generated, no browser was
involved. That is A6.

## Not evidence — what this session could not produce

No browser screenshot, no generated image, no artifact hash, no RunPod job,
no GPU billing record, no `./kitty up` run, no Builder mission execution.
The container has no `.env`, no RunPod credentials, no display, no GPU, and
is not Jacob's Mac. Issue #336's acceptance test and Outcome B items 8–10
were not attempted, because attempting them would have produced only
fabricated results.

---

# KTL2-003 — parallel-lanes proof

This packet is a zero-cost, non-destructive proof that the Builder execution
lane and the interactive continuation lane stay separate. Two modules now
cover it:

- `tests/test_resolve_next_work.py` — the pure resolver (KTL2-001)
- `tests/workflow/test_parallel_lanes.py` — exercises the real resolver
  for bare `next` vs. explicit `builder next`, plus secondary receipt-layer
  invariants on `scripts/kb_effectiveness.record_receipt`

## P1 — the resolver exercises the real continuation boundary

`tests/workflow/test_parallel_lanes.py` exercises `scripts.resolve_next_work`
directly:

- Bare `next` (no explicit builder intent, no valid bundle) always returns
  `ExecutionOwner.INTERACTIVE` with zero `BUILDER_SIDE_EFFECTS`.
- Explicit `builder next` and a valid Builder-launched bundle both enter the
  governed `ExecutionOwner.BUILDER` lane with all five `BUILDER_SIDE_EFFECTS`.
- Contradictory intent (bundle + review, explicit builder + review) raises
  `ValueError` — fail loud, never mask.
- The resolver is deterministic: same input → same output; `to_dict()` is
  roundtrip-safe.

The receipt-layer regression invariants (idempotent continuation, single
execution owner per result, separate-but-cross-referenced builders/interactive
evidence, unknown-stays-null) are kept in the same module as secondary
evidence.

`python3.12 -m pytest tests/test_kb_effectiveness.py tests/test_resolve_next_work.py tests/workflow/ -q`:

All tests pass.

## P2 — continuity metadata reflects main identity

STATE.md and HANDOFF.md now carry `origin/main`'s HEAD, branch, and
execution ownership rather than a stale Builder worktree identity.
`python3.12 scripts/check_continuity_state.py` and `./kitty context --agent`
both pass.

## Unavailable measurements (names not estimates)

- No live second interactive tool/process was run; the resolver is proven
  as a pure function, not by spawning a second process.
- Total tokens, elapsed time, and cost were not measured and remain `null`;
  no causal token/quality claim is made.
- No durable JSONL receipt artifact was committed; all receipt assertions
  use a `tmp_path` store and are reproducible.
