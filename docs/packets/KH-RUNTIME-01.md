# KH-RUNTIME-01 — Runtime truth and build provenance are authoritative

**Initiative:** `kitty-hardening-runtime-truth-20260903-v1`
**Owner:** Builder after explicit operator activation
**Default route:** free; no `policy.routing` pin
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`
**Status:** authored only — not applied, queued, or dispatched

## What Jacob can do after this
Jacob can run `./kitty status` or `./kitty doctor` and trust whether the UI and Gateway are actually current, stale, dirty-built, unavailable, or unknown.

## Verified finding
At base `70c15583a6afa4aac9a6f6eb11abf840afa377a4`, `kitty` checks only the top-level `gateway/kitty-chat/src` directory mtime against `.next/BUILD_ID`; nested source edits can therefore be newer while status says `checkout-current`. The live build stamp observed during review was from divergent SHA `d440561…`. `gateway/doctor.py` searched for `gateway.main` and Linux `/proc`, while the real macOS process was `uvicorn gateway.app:app`, causing a false PASS that said the Gateway was not running.

## Objective
This packet creates no new files. Create one authoritative runtime/provenance probe inside the existing `gateway/doctor.py`/launcher surfaces for Kitty-owned processes and UI build state. The probe must work on macOS without `/proc`, identify the actual Uvicorn Gateway command/cwd/start time, distinguish running/current from running/stale and running/unverifiable, and never convert unknown process identity into PASS. Replace recursive-source freshness inference based on directory mtimes with recorded build provenance: clean source SHA plus an explicit dirty/unverifiable marker or content fingerprint written only after a successful build. Make `kitty status` and `gateway.doctor` consume the same classification rather than reimplementing it. Preserve existing loopback/service-health semantics and do not restart services automatically. First add regressions that reproduce the current false-current and false-not-running cases; if current main already contains equivalent authoritative logic, stop and report that evidence instead of creating a second probe.

## Intended files / fence
- `kitty`
- `gateway/doctor.py`
- `scripts/desktop/start_ui.sh`
- `tests/test_doctor_freshness.py`
- `tests/test_kitty_launcher_runtime.py`
- `tests/test_start_ui_script.py`

This is a deliberate edit-only fence: the executable objective says `creates no new files`. If a new module/test becomes necessary, stop and revise the manifest first.

## Acceptance criteria
1. Nested UI source edits newer than the last build cannot be reported as checkout-current.
2. A clean UI build records an exact source SHA; a dirty-source build is explicitly classified dirty/unverifiable and never stamped as a clean current build.
3. The macOS Gateway process launched as uvicorn gateway.app:app is detected with truthful cwd/start evidence.
4. When runtime identity cannot be established, status is WARN/UNKNOWN rather than PASS/not-running.
5. `kitty status` and `kitty doctor` agree on Gateway/UI freshness for the same fixture state.
6. No runtime probe restarts, kills, rebuilds, or mutates services while answering status.

## Verification
**Tier 1 — Builder mechanical.** These are the only commands Builder runs:
- `python -m pytest -q tests/test_doctor_freshness.py tests/test_kitty_launcher_runtime.py tests/test_start_ui_script.py`
- `python -m ruff check gateway/doctor.py tests/test_doctor_freshness.py tests/test_kitty_launcher_runtime.py tests/test_start_ui_script.py`

**Tier 2 / Tier 3.** Tier 2: live CLI acceptance on a deliberately stale UI build and then on a fresh clean build. Tier 3: independent reviewer confirms the exact same SHA classification from `status`, `doctor`, and the running UI build stamp.

Current-green tests are baseline only. The implementation must add or strengthen at least one regression that fails on `70c15583a6afa4aac9a6f6eb11abf840afa377a4` for the verified finding before production edits.

## Failure modes that must be tested
- The original review reproduction is a required RED case, not prose-only evidence.
- Dependency/service unavailable paths stay truthful; UNKNOWN never becomes success.
- Cancellation/timeout/partial input cannot leave a false success receipt.
- The fix must preserve the existing security/authority boundary named in the objective.

## Stop condition
If truthful provenance requires rebuilding or restarting the user's current runtime as part of the worker run, stop. The packet changes detection/recording code only; live mutation belongs to acceptance after review.

## Recovery / restartability
Read-only probes and build-stamp generation only. A failed probe must leave existing services and `.next` content untouched.

## Dedupe / ownership guard
Before activation, re-read `workspace_global`, GitHub issue #490, current Git/PR state, and Builder task ownership. If current `main` already contains an equivalent fix or another live lane owns any implementation path, stop and reconcile rather than creating competing work. This packet never authorizes push, PR creation, merge, paid spend, credential mutation, or edits under `data/`.
