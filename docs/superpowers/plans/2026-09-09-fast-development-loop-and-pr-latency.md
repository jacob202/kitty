# Fast Development Loop and PR Latency Implementation Plan

**Goal:** Restore a genuinely fast inner development loop while keeping GitHub's ready-candidate validation strong and reproducible.

**Architecture:** Keep `.github/workflows/tests.yml` as authoritative final evidence. Change the local publication path so ordinary feature pushes perform deterministic admission plus bounded changed-scope checks, while an explicit full-local mode preserves offline CI parity. Reprofile and repair the Python fast tier instead of hiding slow tests.

**Tech stack:** Bash Git hooks, Python 3.12/pytest, Ruff, mypy, Vitest/Next.js, GitHub Actions.

**Baseline:** 2026-09-09 `make test` equivalent: 5,649 passed, 1 failed, 1 skipped, 386 deselected in 403.10s. Current pre-push then repeats much of GitHub CI.

## Task 1: Lock the new local-vs-authoritative gate contract in tests

**Files:**
- Modify: `tests/test_pre_push_gate.py`
- Modify: `scripts/hooks/pre-push`
- Modify: `Makefile`

**Step 1:** Replace `test_python_gates_never_skip` with tests asserting two modes: normal non-main feature push runs publication preflight + bounded local checks; `scripts/hooks/pre-push --full` runs current CI-parity Ruff/mypy/coverage/frontend behavior.

**Step 2:** Add a test proving direct-main/non-fast-forward protections run in both modes and cannot be bypassed by scope selection.

**Step 3:** Run `python3.12 -m pytest tests/test_pre_push_gate.py -q`. Expect the new mode tests to fail before the hook changes.

**Step 4:** Implement argument parsing and make `make ci` / explicit `--full` the local full-parity path. Do not remove any GitHub required job.

**Step 5:** Re-run the same test file and commit `test(delivery): define cheap push and full candidate gates`.

## Task 2: Repair the current fast-tier correctness failure

**Files:**
- Modify: `tests/test_builder_attempt.py`
- Inspect only unless behavior is wrong: `gateway/builder_attempt.py`

**Step 1:** Add/adjust the validation-environment assertion so it proves the child command used the Builder Python environment by resolved interpreter/venv identity, not by the textual spelling of a symlink (`venv/bin/python` versus `venv/bin/python3.12`).

**Step 2:** Run only `python3.12 -m pytest tests/test_builder_attempt.py::TestRunValidation::test_validation_uses_builder_python_environment -q`; record the pre-fix failure and post-fix pass.

**Step 3:** If the resolved environments differ, stop and fix production behavior instead of weakening the test. Commit `test(builder): compare validation interpreter identity truthfully`.

## Task 3: Remove accidental 15-second waits from the fast tier

**Files:**
- Modify: `tests/test_brief.py`
- Modify: `tests/test_life_awareness.py`
- Modify: `tests/test_library_chat_001.py`
- Modify production seams only if tests cannot isolate current dependencies cleanly: `gateway/brief.py`, `gateway/life_awareness.py`, `gateway/routes/completions.py`

**Step 1:** Run the known slow tests individually with `--durations=20` and identify the exact unmocked enrichment/fallback boundary responsible for each wait.

**Step 2:** Add assertions that the unit tests inject/mock calendar, weather, todo, memory, model-routing, or attachment dependencies rather than exercising timeout behavior incidentally.

**Step 3:** Preserve one separate test for each timeout/fallback contract where the timeout itself is the behavior under test; move genuine process/network-bound contracts to the appropriate integration tier rather than merely marking slow tests away.

**Step 4:** Run the three affected test files with `--durations=30`; no ordinary unit-path test should retain a multi-second external/fallback wait. Commit `test: remove accidental waits from fast unit paths`.

## Task 4: Turn nightly profiling into a latency ratchet

**Files:**
- Modify: `.github/workflows/nightly-health.yml`
- Modify: `scripts/ci_metrics.py`
- Modify: `tests/test_ci_metrics.py`
- Modify: `TESTING.md`

**Step 1:** Extend the existing nightly `--durations=50` evidence so the artifact records total selected tests, elapsed suite time, top slow tests, and FAST versus INTEGRATION counts in machine-readable JSON.

**Step 2:** Add report fields for the prior measured baseline and current observation without pretending a single machine measurement is an SLO.

**Step 3:** Add a first ratchet: warn when FAST exceeds 180 seconds or an unexplained ordinary FAST test exceeds 5 seconds. Do not fail PR CI on timing variance in this first change.

**Step 4:** Unit-test the metrics parser/rendering with synthetic duration data, then update `TESTING.md` with the 2026-09-09 measured reality. Commit `feat(testing): make fast-suite latency observable`.

## Task 5: Formalize draft iteration and frozen-candidate delivery

**Files:**
- Modify: `AGENTS.md`
- Modify: `.agents/skills/verified-delivery/SKILL.md`
- Modify: `TESTING.md`
- Modify tests enforcing documentation authority if required: `tests/test_documentation_authority.py`

**Step 1:** Specify that iterative remote pushes should remain draft when full PR evidence is not yet requested. The workflow already skips expensive jobs while draft and runs them on `ready_for_review`.

**Step 2:** Define `frozen candidate` as the SHA after bounded implementation/self-check and before independent completion review. Adjacent non-blocking findings become follow-up evidence, not silent scope expansion.

**Step 3:** Require one explicit full-local parity run only when GitHub cannot provide authoritative evidence or the task specifically requires local parity; otherwise ready-PR GitHub CI is the full gate.

**Step 4:** Run `python3.12 -m pytest tests/test_pre_push_gate.py tests/test_documentation_authority.py -q` and `git diff --check`. Commit `docs(delivery): separate inner loop from candidate gate`.

## Acceptance evidence

- `tests/test_pre_push_gate.py` proves cheap ordinary-push behavior and explicit full-candidate behavior without weakening history/main protections.
- The Builder interpreter regression test passes for equivalent symlinked interpreter identities and still fails for a genuinely foreign environment.
- Reprofiled FAST suite is below 180 seconds on the same local machine as the 403.10-second baseline, or the PR documents the remaining measured blockers rather than claiming success.
- No unexplained ordinary FAST test exceeds 5 seconds in the recorded profile.
- Ready code/frontend PRs still receive every scope-required GitHub job from `.github/workflows/tests.yml`.
- `TESTING.md` reports current measured test counts/timing instead of the stale 4,714/108.8-second snapshot as if it were current.

## Non-goals

Do not delete broad regression coverage merely to hit a timing number. Do not turn timing assertions into flaky wall-clock PR gates. Do not make `--no-verify` the normal delivery workflow. Do not weaken merge-gate, sensitive-review, browser acceptance, or controlled-live safety boundaries.
