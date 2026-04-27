# Implementation Review - 2026-04-27

## Request

Review prior chat code dumps and implementations, compare them to the current codebase, grade the result, identify actionable improvements, and implement the useful fixes.

## Grade Before Feedback

B+

The previous pass implemented useful fixes and verified them, but it did not leave a durable comparison record. That made it harder for a future assistant to see which dumped ideas were accepted, rejected, or deferred.

## Comparison

| Requested area | Implementation status | Decision |
| --- | --- | --- |
| Review prior code dumps | Partially satisfied through current thread context and local archive artifacts | Keep this ledger so the review is durable |
| Manifest review | Implemented | Restored `src/eval/rlhf_collection.py` because live routes imported it |
| Gemini UI harvest review | Implemented | Fixed `garage-ui` voice MIME detection and documented current SSE/SocketIO drift |
| Useful code now | Implemented | Landed only fixes that matched current live app paths |
| Useful code later | Partially satisfied | Deferred LLM-client consolidation and full SocketIO chat migration because they are larger architecture decisions |
| Verification | Implemented | Full Python suite and frontend production build passed |

## Implemented Feedback

1. Added Safari/iOS `audio/mp4` route coverage so the browser MIME fix is not just a frontend assumption.
2. Added route tests for `/api/rlhf/options` and `/api/rlhf/preference` so the restored collector remains protected.
3. Added the current `garage-ui` transport note to `docs/phase3b_ui_rebuild_guide.md` so `/stream` is not removed while the active UI still uses it.
4. Added a launcher regression test to prevent future scaffolding scripts from creating a root-level `kitty/` package over the existing executable launcher.

## Deferred

- Full `garage-ui` chat migration from SSE to SocketIO. This should be a dedicated patch because it touches live chat transport, backend events, and room/request scoping.
- LLM-client consolidation across `src/api/web_llm.py`, `src/space_kitty/llm_client.py`, and `src/utils/resilient_llm_client.py`. The harvest correctly identifies this as future architecture work, not a safe drive-by cleanup.
- Real Safari/iOS device verification for MediaRecorder. Backend and build tests pass, but device recording should still be checked on the actual target browser.

## Grade After Feedback

A-

The implementation now has code, tests, verification, and a durable review trail. It stops short of A because the highest-risk browser behavior still needs real device validation.
