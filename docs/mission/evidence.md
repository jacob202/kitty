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

## E7 — issue #336 claims checked against code

Method: read the named files, not the issue's summary of them. Results in
`grounding.md` § "Image subsystem". All six claims TRUE. Key line numbers:
`image_plan.py:61` (plan built, never stored), `extended.py:406` vs `:415`
(`plan_id` absent from generate, `guidance_tags` absent from generate),
`workers/comfy_worker/app.py:704` (workflow hardcoded), migrations stop at
`028` (no session table).

## Not evidence — what this session could not produce

No browser screenshot, no generated image, no artifact hash, no RunPod job,
no GPU billing record, no `./kitty up` run, no Builder mission execution.
The container has no `.env`, no RunPod credentials, no display, no GPU, and
is not Jacob's Mac. Issue #336's acceptance test and Outcome B items 8–10
were not attempted, because attempting them would have produced only
fabricated results.
