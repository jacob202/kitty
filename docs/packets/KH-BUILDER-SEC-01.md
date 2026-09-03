# KH-BUILDER-SEC-01 — Builder validation runs with credential isolation parity

**Initiative:** `kitty-hardening-builder-validation-env-20260903-v1`  
**Owner:** Builder after explicit operator activation  
**Default route:** free; no `policy.routing` pin  
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`  
**Status:** authored only — not applied, queued, or dispatched

## What Jacob can do after this
Jacob can let Builder validate worker changes without validation commands inheriting GitHub, SSH, or other credentials stripped from the worker itself.

## Verified finding
`gateway/builder_runner.py` deliberately strips credential variables from worker environments, but `gateway/builder_attempt.py::run_validation` starts from `dict(os.environ)`. Validation commands therefore execute after the worker under a more privileged environment than the code-generation process.

## Objective
Do not activate until the current ONE KITTY OK-ACTION-01/02 execution lane has released Builder validation paths. Extract or reuse one canonical credential/environment sanitizer shared by worker launch and validation so the blocked credential set cannot drift. Validation receives only the minimal toolchain/runtime variables needed to run repository gates plus explicitly safe inherited values; `extra_commands` do not gain additional environment authority. Preserve venv/PATH behavior required by packet tests. Add a regression that injects fake GitHub/SSH credentials into the parent environment and proves both worker-env construction and run_validation cannot observe them. Also verify error/log output cannot print stripped secret values.

## Intended files / fence
- `gateway/`
- `tests/`

Directory entries are deliberate because this packet may create the specifically named helper/migration/test described in the objective. The worker must still stay inside the narrow objective; a directory fence is not permission for opportunistic refactoring.

## Acceptance criteria
1. Worker launch and validation derive credential blocking from one canonical definition/helper.
2. GITHUB_TOKEN, GH_TOKEN, SSH agent variables, git credential helpers/askpass variables, and any existing blocked credential vars are absent from validation subprocesses.
3. Validation still receives the repository Python venv/PATH required for `python -m pytest`.
4. Adding a blocked credential through an override/extra environment is rejected rather than silently restored.
5. Validation results and logs do not echo stripped credential values.
6. No active Builder task, lease, attempt, queue state, or worker worktree is mutated by this hardening packet itself.

## Verification
**Tier 1 — Builder mechanical.** These are the only commands Builder runs:
- `python -m pytest -q tests/test_builder_runner.py tests/test_builder_attempt.py`
- `python -m ruff check gateway/builder_runner.py gateway/builder_attempt.py gateway/builder_env.py tests/test_builder_runner.py tests/test_builder_attempt.py`

**Tier 2 / Tier 3.** Tier 2: hermetic subprocess probe under fake credentials. No product UI PA. Independent review must inspect the final environment allow/deny semantics because this is a privilege boundary.

Current-green tests are baseline only. The implementation must add or strengthen at least one regression that fails on `70c15583a6afa4aac9a6f6eb11abf840afa377a4` for the verified finding before production edits.

## Failure modes that must be tested
- The original review reproduction is a required RED case, not prose-only evidence.
- Dependency/service unavailable paths stay truthful; UNKNOWN never becomes success.
- Cancellation/timeout/partial input cannot leave a false success receipt.
- The fix must preserve the existing security/authority boundary named in the objective.

## Stop condition
If making validation functional requires passing through a real GitHub/SSH credential, stop. Publication/review is a different authority and must not be smuggled into validation.

## Recovery / restartability
Environment-only change; no DB migration. A failed validation remains a normal failed validation receipt.

## Dedupe / ownership guard
Before activation, re-read `workspace_global`, GitHub issue #490, current Git/PR state, and Builder task ownership. If current `main` already contains an equivalent fix or another live lane owns any implementation path, stop and reconcile rather than creating competing work. This packet never authorizes push, PR creation, merge, paid spend, credential mutation, or edits under `data/`.
