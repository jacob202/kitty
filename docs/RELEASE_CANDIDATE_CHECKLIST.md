# Release Candidate Checklist

Date: 2026-04-30
Target: Market-Ready Baseline Checkpoint

This checklist validates the completion of the `MARKET_READY_EXECUTION_PLAN_2026-04-30.md` execution phases prior to the formal release candidate tag.

## Core Stability

- [x] Full Python test suite passes (`pytest tests/`).
- [x] Preflight control gates pass (`bash scripts/run_gates.sh`).
- [x] Frontend test suite passes (`npm run test` in `garage-ui`).
- [x] Frontend production build compiles without errors (`npm run build`).

## Routing & Communication

- [x] `./kitty status` correctly identifies listener state on port 5001.
- [x] `GET /api/brief` route serves deterministic content reliably.
- [x] `POST /api/command` correctly parses and maps stuck/focus commands.
- [x] `POST /api/chat` correctly handles provider/API key failures by explicitly returning error messages instead of blank payloads.

## Security & Governance

- [x] `security_scanner.py` successfully blocks forbidden sub-processes or unauthorized writes via `kittybuilder`.
- [x] Protected directories (e.g., `src/`, `data/`) are clear of unwanted generated `Icon\r` artifacts or dirty database commits.
- [x] `docs/FILE_GOVERNANCE.md` rules remain unbroken.

## Documentation & Operator Clarity

- [x] Chat-log candidates have been rigorously reviewed against `CHAT_LOG_CANDIDATE_REVIEW_2026-04-29.md` and only explicitly verified statements were added to `PROJECT_FACTS.md` or `USER_PREFS.md`.
- [x] Speculative/Assistant-authored statements remain in `OPEN_LOOPS.md` or `PARKED_FEATURES.md`.
- [x] `OPERATIONS_RUNBOOK.md` exists and details the standard startup/shutdown/test paths.
- [x] `KNOWN_LIMITATIONS.md` exists and lists the current boundaries regarding the MCP agent bundle, repo splits, and privacy integrations.

## Signoff

- **Checkpoint Hash:** *(Automatically generated upon final commit)*
- **Status:** APPROVED for handoff.
