# KH-DEPS-PY-01 — Doctor detects Python dependency drift

**Initiative:** `kitty-hardening-python-env-truth-20260903-v1`  
**Owner:** Builder after explicit operator activation  
**Default route:** free; no `policy.routing` pin  
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`  
**Status:** authored only — not applied, queued, or dispatched

## What Jacob can do after this
Jacob can run Doctor and immediately know when Kitty's active Python environment violates the repository's declared dependency constraints, with a safe recovery command.

## Verified finding
During review, the active venv failed `pip check`: `mem0ai 0.1.118` requires `openai<1.110` and `protobuf<6`, while the venv had `openai 2.54.0` and `protobuf 7.36.1`. `requirements.txt` already carries the intended OpenAI ceiling, so this was environment drift rather than repository intent.

## Objective
This packet creates no new files. Add a bounded dependency-health projection used by `kitty doctor`. Run `sys.executable -m pip check` (or an equivalent package-metadata check with identical semantics) with a short timeout and classify: PASS when constraints are satisfied, WARN/FAIL with package names and a plain recovery instruction when conflicts exist, UNKNOWN when the check itself cannot run. Never auto-install, downgrade, or mutate the environment from Doctor. Keep secrets and full local paths out of user copy. Add a bootstrap/install verification hook only if an existing setup path already has a natural post-install check; do not create a new package manager or dependency authority. Preserve requirements.txt/uv.lock as repository truth.

## Intended files / fence
- `gateway/doctor.py`
- `requirements.txt`
- `tests/test_doctor.py`
- `tests/test_doctor_freshness.py`

This is a deliberate edit-only fence: the executable objective says `creates no new files` If a new module/test becomes necessary, stop and revise the manifest first.

## Acceptance criteria
1. Doctor reports a dependency conflict when a hermetic pip-check fixture returns incompatible packages.
2. Doctor reports PASS only when the dependency check itself succeeded and reported no conflicts.
3. Check timeout/tool failure is UNKNOWN/WARN, never a false PASS.
4. The message names conflicting packages and one safe remediation path without exposing secrets or irrelevant filesystem details.
5. Doctor performs no install/uninstall/upgrade/downgrade operation.
6. Repository dependency files remain the only declared version authority.

## Verification
**Tier 1 — Builder mechanical.** These are the only commands Builder runs:
- `python -m pytest -q tests/test_doctor.py tests/test_doctor_freshness.py`
- `python -m ruff check gateway/doctor.py tests/test_doctor.py tests/test_doctor_freshness.py`

**Tier 2 / Tier 3.** Tier 2: live Doctor against the current drifted venv, then after operator repair against a satisfying venv. Tier 3 not required; this is operator truth.

Current-green tests are baseline only. The implementation must add or strengthen at least one regression that fails on `70c15583a6afa4aac9a6f6eb11abf840afa377a4` for the verified finding before production edits.

## Failure modes that must be tested
- The original review reproduction is a required RED case, not prose-only evidence.
- Dependency/service unavailable paths stay truthful; UNKNOWN never becomes success.
- Cancellation/timeout/partial input cannot leave a false success receipt.
- The fix must preserve the existing security/authority boundary named in the objective.

## Stop condition
If resolving the current conflict requires changing mem0/openai product architecture rather than restoring declared constraints, stop after landing truthful detection; dependency upgrades are a separate decision.

## Recovery / restartability
Read-only environment inspection. Operator remediation happens outside the worker and is independently reversible via venv recreation.

## Dedupe / ownership guard
Before activation, re-read `workspace_global`, GitHub issue #490, current Git/PR state, and Builder task ownership. If current `main` already contains an equivalent fix or another live lane owns any implementation path, stop and reconcile rather than creating competing work. This packet never authorizes push, PR creation, merge, paid spend, credential mutation, or edits under `data/`.
