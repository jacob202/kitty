# KH-IMPORT-01 — ChatGPT import is bounded and failures stay failures

**Initiative:** `kitty-hardening-chatgpt-import-20260903-v1`
**Owner:** Builder after explicit operator activation
**Default route:** free; no `policy.routing` pin
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`
**Status:** authored only — not applied, queued, or dispatched

## What Jacob can do after this
Jacob can import a large ChatGPT export without loading it all into RAM and get a truthful, actionable failure when extraction fails.

## Verified finding
`gateway/routes/import_chatgpt.py` does `content = await file.read()` with no route-specific streaming cap, writes the full bytes afterward, and returns HTTP 200 with `items: 0` for extractor absence, timeout, nonzero exit, and arbitrary exceptions. Arbitrary exception text can be embedded directly in the user message.

## Objective
Depend on KH-BODY-01. Stream the uploaded export directly to a private temporary file while enforcing the dedicated ChatGPT-import cap defined by the request-limit policy; do not accumulate the export in a Python bytes object. Validate filename/type and ensure temp cleanup on every branch. Treat extractor missing, timeout, nonzero exit, malformed output, and internal exceptions as typed failures with appropriate 4xx/5xx status rather than successful zero-item imports. Log technical stderr/exception detail internally; return only safe action-oriented copy. Preserve a legitimate successful result with zero extracted items as a distinct success state. Bound captured subprocess stdout/stderr or switch to an output file/stream so a malicious extractor result cannot create a second memory spike. Keep the extractor command argv-based and no shell.

## Intended files / fence
- `gateway/routes/`
- `gateway/constants.py`
- `gateway/request_limits.py`
- `tests/`

Directory entries are deliberate because this packet may create the specifically named helper/migration/test described in the objective. The worker must still stay inside the narrow objective; a directory fence is not permission for opportunistic refactoring.

## Acceptance criteria
1. Upload bytes are streamed to disk under a documented cap rather than read into one in-memory bytes object.
2. Extractor missing, timeout, nonzero exit, malformed output, and unexpected exception are distinct failure responses and never HTTP-200 zero-item success.
3. A real successful import with zero findings remains a successful zero-item result.
4. Raw exception text, stack traces, subprocess stderr, file paths, and executable names are not primary user copy.
5. Temporary files are removed on success, rejection, timeout, cancellation, and exception.

## Verification
**Tier 1 — Builder mechanical.** These are the only commands Builder runs:
- `python -m pytest -q tests/test_import_chatgpt.py`
- `python -m ruff check gateway/routes/import_chatgpt.py gateway/constants.py gateway/request_limits.py tests/test_import_chatgpt.py`

**Tier 2 / Tier 3.** The Builder packet is backend-only. After it lands, an interactive companion must exercise the existing Onboarding UI against a successful small export, a zero-findings export, an oversized export, and a forced extractor failure. If the current UI cannot surface the new safe failure contract, stop and author a separate frontend packet rather than widening this Builder task. Tier 3: independent desktop/mobile reviewer confirms failure remains retryable and the selected file is not silently cleared after a rejected import.

Current-green tests are baseline only. The implementation must add or strengthen at least one regression that fails on `70c15583a6afa4aac9a6f6eb11abf840afa377a4` for the verified finding before production edits.

## Failure modes that must be tested
- The original review reproduction is a required RED case, not prose-only evidence.
- Dependency/service unavailable paths stay truthful; UNKNOWN never becomes success.
- Cancellation/timeout/partial input cannot leave a false success receipt.
- The fix must preserve the existing security/authority boundary named in the objective.

## Stop condition
If supporting realistic exports requires lifting the dedicated import cap beyond the packet's streaming design or changing the extractor format, stop and report measured file-size evidence; do not silently increase the global body cap.

## Recovery / restartability
Temporary-file only before extraction; no idea-mine/import state may be committed on a failed extractor run.

## Dedupe / ownership guard
Before activation, re-read `workspace_global`, GitHub issue #490, current Git/PR state, and Builder task ownership. If current `main` already contains an equivalent fix or another live lane owns any implementation path, stop and reconcile rather than creating competing work. This packet never authorizes push, PR creation, merge, paid spend, credential mutation, or edits under `data/`.
