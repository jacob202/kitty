# Market-Ready Execution Plan

Date: 2026-04-30
Status: planning approved for transition to execution
Source docs read:
- `CURRENT_FOCUS.md`
- `TASKS.md`
- `SESSION_SUMMARY.md`
- `docs/DELEGATION_BOARD.md`
- `docs/MCP_AGENT_BUNDLE_REVIEW_2026-04-29.md`
- `docs/OPEN_LOOPS.md`
- `docs/PARKED_FEATURES.md`
- `docs/FILE_MANIFEST.md`
- `docs/WORKSPACE_SEPARATION_EXECUTION_REPORT_2026-04-29.md`
- `docs/WORKSPACE_SEPARATION_MOVE_MAP.md`
- `specs/copy-first-workspace-separation.spec.md`

## Objective

Ship a market-ready Kitty baseline from a controlled, verifiable scope:
- stable runtime
- reliable launcher and route behavior
- guarded build pipeline
- clean canonical docs
- release checkpoint that can be demoed and handed to early users

## What Is Already Strong

- Full test suite was recently green (`333 passed` in session summary).
- Core routes and utilities are wired and smoke-tested (`/api/brief`, `/api/command`, `/api/chat`).
- Copy-first workspace exists and has launch smoke on port 5002.
- Chat-log candidate review process is established and has canonical disposition docs.

## Transition Decision

Authoritative migration runtime:

`/Users/jacobbrizinski/Projects/kitty-system/kitty-app`

Legacy rollback remains available at `/Users/jacobbrizinski/Projects/kitty` until retirement criteria are met.

## Execution Phases

### Phase A: Release Baseline Checkpoint (done)

Scope:
- verify launcher state accuracy
- verify live route smoke
- verify canon reflects latest Gemini candidate review decisions
- checkpoint repository

Required commands:

```bash
./kitty status
curl -sS http://localhost:5001/api/brief
curl -sS -X POST http://localhost:5001/api/command -H "Content-Type: application/json" -d '{"command":"/stuck"}'
curl -sS -X POST http://localhost:5001/api/chat -H "Content-Type: application/json" -d '{"message":"release smoke","domain":"chat"}'
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
```

Definition of done:
- launcher status reflects real listener state (completed)
- route smoke all 200 with non-empty useful responses (completed)
- tests green (completed)
- checkpoint commit created (completed)

### Phase B: Launch Reliability and UX Safety (done)

Scope:
- resolve any launcher/PID mismatches
- keep route behavior deterministic under failures
- add/keep regression tests for previously fixed regressions (eval dashboard object failures, chat fallback)

Validation:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_web_chat_phase1.py tests/test_brief_route.py tests/test_commands_route.py tests/test_evals_dashboard.py -q --tb=short
```

Definition of done:
- no known launcher ambiguity (completed)
- prior regressions covered by tests (completed)
- no blank response path in `/api/chat` (completed)

### Phase C: Canonical Governance Freeze (done)

Scope:
- promote only high-confidence chat-log candidates into canonical docs
- keep uncertain items in `docs/OPEN_LOOPS.md`
- reject noisy extraction explicitly

Source of truth:
- `docs/CHAT_LOG_CANDIDATE_REVIEW_2026-04-29.md`

Definition of done:
- canonical docs and open loops are consistent with source-of-truth review (completed)
- no assistant-authored speculation promoted as fact (completed)

### Phase D: Security and Builder Hardening (done)

Scope:
- keep builder security enforcement active
- keep command scanning and write-path controls active
- verify no regression in protected-file rules and gating

Validation:

```bash
bash scripts/run_gates.sh
/opt/homebrew/bin/python3.12 -m pytest tests/test_kitty_builder.py tests/test_security_scanner.py -q --tb=short
```

Definition of done:
- security gates pass (completed)
- blocked patterns still blocked (completed)
- no protected file policy regressions (completed)

### Phase E: Release Candidate Package

Scope:
- produce clean operator handoff and launch instructions
- freeze deferred scope list
- create RC checklist and signoff notes

Deliverables:
- `docs/RELEASE_CANDIDATE_CHECKLIST.md`
- `docs/KNOWN_LIMITATIONS.md`
- `docs/OPERATIONS_RUNBOOK.md`

Definition of done:
- one-command start path documented
- smoke and test commands documented
- known risks explicitly listed

Status:
- completed and checkpointed
- signoff hash: `d08cd3b`

## Explicit Do-Not-Build Boundaries (unchanged)

- MCP bundle adoption (currently parked/unverified)
- memory migration outside approved focused modules
- QLoRA/fine-tuning
- proactive nudging
- broad UI polish initiatives
- deletion of raw chat logs
- destructive path moves/renames of old checkout

## Delegation Lanes (ready now)

Lane 1: live smoke verifier (read-only)
- ownership: runtime checks only
- output: status codes + snippets + log anomalies

Lane 2: canonical doc reconciler (docs-only)
- ownership: `docs/DECISIONS.md`, `docs/OPEN_LOOPS.md`, `docs/PROJECT_FACTS.md`, `docs/USER_PREFS.md`
- source: `docs/CHAT_LOG_CANDIDATE_REVIEW_2026-04-29.md`

Lane 3: launcher reliability worker (script/test only)
- ownership: launcher scripts and launcher tests
- output: fixed status/PID mismatch plus regression test

Lane 4: checkpoint worker (git hygiene)
- ownership: checkpoint commit and evidence block
- output: commit hash + command transcript summary

## Immediate Next Smallest Action

Post-checkpoint (user-approved): run spec-first triage for parked MCP agent bundle before any migration or adoption work.
