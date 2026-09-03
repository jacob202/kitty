# KH-BODY-01 — Actual request bytes are bounded before route parsing

**Initiative:** `kitty-hardening-request-limits-20260903-v1`
**Owner:** Builder after explicit operator activation
**Default route:** free; no `policy.routing` pin
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`
**Status:** authored only — not applied, queued, or dispatched

## What Jacob can do after this
Jacob can send uploads and API requests knowing Kitty enforces the declared limit even for chunked bodies, false Content-Length headers, and route-specific larger upload caps.

## Verified finding
`gateway/app.py` rejects oversized requests only when `Content-Length` is present and greater than `MAX_BODY_BYTES`. A client can omit the header or declare a smaller value while streaming more bytes. Separate upload routes already have larger/smaller caps, so a single 10 MB header-only guard is both bypassable and inconsistent.

## Objective
Replace the header-only global guard with streaming actual-byte enforcement at the ASGI receive boundary. Keep Content-Length as an early rejection optimization, but count `http.request` chunks and terminate with 413 once the applicable limit is exceeded without eagerly buffering the body. Centralize route-specific request limits using existing constants: default JSON/body limit 10 MB, voice 25 MB, inventory 10 MB, character/source image limits matching their existing contracts, and a bounded ChatGPT-import allowance used by KH-IMPORT-01. Do not widen a route merely because another route needs a larger cap. Downstream multipart/request parsing must still receive the original stream when under limit. Add regressions for missing, malformed, dishonest-short, exact-limit, and over-limit Content-Length cases plus a streamed multipart case.

## Intended files / fence
- `gateway/`
- `tests/`

Directory entries are deliberate because this packet may create the specifically named helper/migration/test described in the objective. The worker must still stay inside the narrow objective; a directory fence is not permission for opportunistic refactoring.

## Acceptance criteria
1. A body larger than its route limit is rejected even when Content-Length is absent.
2. A client that declares a smaller Content-Length than it actually sends cannot exceed the real byte cap.
3. Valid chunked and multipart bodies under their route-specific limits reach the route unchanged.
4. Malformed or negative Content-Length remains a 400 and an honestly oversized header is rejected before body consumption.
5. Route-specific larger caps do not widen unrelated API routes.
6. The limiter streams/counts bytes and does not buffer an entire request merely to measure it.

## Verification
**Tier 1 — Builder mechanical.** These are the only commands Builder runs:
- `python -m pytest -q tests/test_app_input_validation.py`
- `python -m ruff check gateway/app.py gateway/constants.py gateway/request_limits.py tests/test_app_input_validation.py`

**Tier 2 / Tier 3.** Tier 2: live ASGI/HTTP probes using chunked/no-length and dishonest-length bodies. Tier 3 not required because this is a transport security boundary with unchanged success UX.

Current-green tests are baseline only. The implementation must add or strengthen at least one regression that fails on `70c15583a6afa4aac9a6f6eb11abf840afa377a4` for the verified finding before production edits.

## Failure modes that must be tested
- The original review reproduction is a required RED case, not prose-only evidence.
- Dependency/service unavailable paths stay truthful; UNKNOWN never becomes success.
- Cancellation/timeout/partial input cannot leave a false success receipt.
- The fix must preserve the existing security/authority boundary named in the objective.

## Stop condition
If Starlette/FastAPI middleware cannot enforce the limit without consuming/replacing the request stream incorrectly, stop and implement a small raw ASGI middleware in `gateway/request_limits.py`; do not fall back to full-body buffering.

## Recovery / restartability
No persistent state. Rejected partial uploads must not leave destination/temp files behind.

## Dedupe / ownership guard
Before activation, re-read `workspace_global`, GitHub issue #490, current Git/PR state, and Builder task ownership. If current `main` already contains an equivalent fix or another live lane owns any implementation path, stop and reconcile rather than creating competing work. This packet never authorizes push, PR creation, merge, paid spend, credential mutation, or edits under `data/`.
