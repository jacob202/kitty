# Delegation Board

Last updated: 2026-04-29

This is the queue for parallel agents. Delegated work must stay inside the lane listed here and report exact files read, findings, commands run, and remaining risks.

## Delegation Rules

- Read-only scouts may inspect protected files but must not edit them.
- Code workers need an approved spec with allowed files, forbidden files, smoke tests, and rollback.
- No worker may delete raw chat logs, eval artifacts, histories, data files, or protected source files.
- Each worker must finish with a completion report.
- Close agents when their result has been captured.

## Ready To Delegate Now

### Live Route Smoke

Type: verification

Status: completed 2026-04-29 — all routes verified and documented below

Task:

- start or inspect the live Kitty server
- verify `/api/brief`
- verify `/api/command` with `/stuck`
- verify `/api/chat` still answers or fails clearly

Validation:

```bash
./kitty status
curl http://localhost:5001/api/brief
curl -X POST http://localhost:5001/api/command -H "Content-Type: application/json" -d '{"command":"/stuck"}'
```

Completion report:

- server status
- response status codes
- response snippets
- any log errors

Result:

- `./kitty status`: running on `http://localhost:5001`
- `GET /api/brief`: HTTP 200, deterministic control-doc brief returned
- `POST /api/command {"command":"/stuck"}`: HTTP 200, next action returned
- `POST /api/chat`: initially HTTP 200 with empty `response`; fixed and re-smoked with non-empty response
- `GET /api/eval/dashboard`: HTTP 200, read-only eval artifact summary returned

### Gemini: Canonical Chat Log Intake

Type: external review / extraction

Input:

- raw chat exports
- `docs/GEMINI_CHAT_LOG_INTAKE.md`
- `CURRENT_FOCUS.md`
- `docs/README.md` (orientation; **`KITTY_CONTEXT.md`** retired)
- `docs/DECISIONS.md`
- `docs/PARKED_FEATURES.md`

Output:

- draft report saved under `docs/imports/`
- accepted candidates for decisions, parked features, user preferences, project facts, cleanup candidates, skill candidates, and open loops

Validation:

```bash
test -f docs/imports/[gemini-output].md
grep -q "## Decisions" docs/imports/[gemini-output].md
grep -q "## Parked Features" docs/imports/[gemini-output].md
```

### Tree Cleanup Scout

Type: read-only audit

Status: tiny generated-cache cleanup completed 2026-04-28

Task:

- classify generated artifacts, caches, logs, unknown top-level dirs, and metadata files
- do not delete anything
- flag protected-tree metadata separately

Output:

- updates to `docs/CLEANUP_CANDIDATES.md`
- completed spec: `specs/tiny-generated-cache-cleanup.spec.md`

Validation:

```bash
bash scripts/run_gates.sh
```

Latest result:

- removed only root `.DS_Store`, root `__pycache__/`, `scripts/__pycache__/`, `tests/__pycache__/`, `.pytest_cache/`, and `.aider.tags.cache.v4/`
- gates after cleanup: `78 passed`
- protected-tree `Icon\r`, `src/`, `data/`, `skills/`, eval artifacts, frontend caches, and tracked deletions were not cleaned

### Runtime Surface Scouts

Type: read-only code map

Status: completed / reconciled 2026-04-28

- `/stuck` scout completed.
- deterministic brief scout completed.
- task/done tracking scout completed.

Verified implementation hooks:

- `/stuck`: `src/api/commands.py`, `src/core/stuck.py`, `tests/test_commands_route.py`, `tests/test_stuck_command.py`
- deterministic brief: `src/api/brief.py`, `src/core/morning_brief.py`, `tests/test_brief_route.py`, `tests/test_morning_brief.py`
- task/done tracking: `src/memory/task_tracker.py`, `src/memory/task_repo.py`, `tests/test_task_tracker.py`

Current follow-up:

- do not delegate more hook-mapping scouts for these features unless behavior regresses
- delegate only product/UI polish or durable-storage changes after a new spec

Validation:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_brief_route.py tests/test_commands_route.py tests/test_morning_brief.py tests/test_stuck_command.py tests/test_task_tracker.py -q --tb=short
```

## Ready After Spec Approval

### Worker: `/api/chat` Real Provider Response

Status: completed 2026-04-28

Task:

- decide whether `/api/chat` should call `WebLLMClient` when the compatibility LLM shim is blank, or keep the deterministic `Kitty heard:` fallback while runtime is stabilized
- add provider-error behavior that fails clearly instead of returning blank

Validation:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_web_chat_phase1.py -q --tb=short
curl -sS -X POST http://localhost:5001/api/chat -H "Content-Type: application/json" -d '{"message":"status smoke test","domain":"chat"}'
```

Result:

- `tests/test_web_chat_phase1.py`: 13 passed
- Removed deterministic 'Kitty heard' fallback, allowing empty strings to trigger dispatcher's web fallback correctly.
- Added explicit error accumulation in `WebLLMClient` so provider-error behavior fails clearly instead of returning a generic error.

### Worker: Chat Log Consolidation

Status: completed 2026-04-28

Task:

- run extraction in dry-run mode first
- write reviewed report only when explicitly approved
- never delete raw logs

Validation:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_consolidate_chat_logs.py -q --tb=short
python3 scripts/consolidate_chat_logs.py --project . --input data/sessions --write-reviewed --output docs/CHAT_LOG_CONSOLIDATION_REPORT.md
```

Latest result:

- `tests/test_consolidate_chat_logs.py`: 20 passed
- CLI write-reviewed: 449 logs found, 449 processed, 0 errors, wrote report
- category counts: decisions 3, parked features 16, active tasks 33, corrections 3853, user preferences 405, project facts 232, file references 304, cleanup candidates 51, skill candidates 54, specialist KB candidates 0, bugs/failures 981, rejected ideas 155
- **real sessions**: 8245 user + 8232 assistant messages extracted from JSON

Next:

- Do not treat the keyword report as canonical-quality extraction.
- Review `docs/imports/gemini_intake_20260428.md` candidates before promoting `accepted_candidate` or `parked_candidate` entries to accepted canon.
- Preserve raw logs.

### Worker: Transparent Evals Dashboard

Status: completed 2026-04-28 (backend & UI)

Required first step:

- spec written: `specs/evals-dashboard.spec.md` (backend) and `specs/evals-dashboard-ui.spec.md` (UI)
- backend service added: `src/observability/evals_dashboard.py`
- route added: `GET /api/eval/dashboard`
- tests added: `tests/test_evals_dashboard.py`
- UI panel built: `kitty-chat/app/components/EvalDashboard.tsx`

Validation target:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_eval_loop_logging.py tests/test_browser_smoke.py -q --tb=short
cd kitty-chat && npm run build
```

Latest result:

- `tests/test_evals_dashboard.py tests/test_reliability_platform.py tests/test_eval_loop_logging.py`: 29 passed
- app-factory smoke: `GET /api/eval/dashboard` returned HTTP 200 and summarized 156 artifacts
- Garage UI typecheck passed: `npx tsc --noEmit --incremental false`
- Garage UI production build passed: `npm run build`
- failed-check object rendering fixed in `kitty-chat/app/components/EvalDashboard.tsx`
- `cd kitty-chat && npm run build`: Next.js UI compiled successfully

### Worker: Builder Output Security Scanning

Status: scanner and builder enforcement implemented 2026-04-28

Required first step:

- spec written: `specs/security-scanner.spec.md`
- scanner added: `src/utils/security_scanner.py`
- tests added: `tests/test_security_scanner.py`
- integrated into `scripts/run_gates.sh`
- enforcement spec written: `specs/builder-security-enforcement.spec.md`
- `scripts/kitty_builder.py` blocks scanner findings before file writes and subprocess launch

Validation target:

```bash
bash scripts/run_gates.sh
```

Latest result:

- `tests/test_security_scanner.py`: 8 passed
- `tests/test_kitty_builder.py tests/test_security_scanner.py`: 53 passed
- `bash scripts/run_gates.sh`: 83 passed

### Worker: Runtime Utility Productization

Status: blocked until a narrow product spec exists

Already built:

- `/api/brief`
- `/api/command` with `/stuck`
- task/done tracking modules

Possible next work:

- connect `done [task]` through the main chat path if not already wired
- add UI affordance for brief/stuck only after UI spec
- add durable task repository behavior only after storage spec

Validation:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_brief_route.py tests/test_commands_route.py tests/test_task_tracker.py -q --tb=short
curl http://localhost:5001/api/brief
curl -X POST http://localhost:5001/api/command -H "Content-Type: application/json" -d '{"command":"/stuck"}'
```

### Worker: Safe Cache Cleanup

Allowed only after a cleanup spec.

Allowed candidates:

- `.DS_Store`
- `scripts/__pycache__/`
- `tests/__pycache__/`
- `.pytest_cache/`
- `.aider.tags.cache.v4`

Validation:

```bash
bash scripts/run_gates.sh
git status --short
```

## Do Not Delegate Yet

- physical `kitty-system/kitty-app` repo migration
- memory migration
- source-grounded specialist engine
- Kelly bodywork update
- QLoRA or model training
- MCP expansion
- proactive idle nudging
- UI polish
- deletion of raw chat logs
- deletion of eval artifacts
- deletion inside `src/` for `Icon\r` files without a narrow waiver spec

## Completed 2026-04-29

- MCP agent bundle review: KnowledgeGetter, Librarian, VisionGuide, CodeReviewer, and Overnighter are present in the dirty tree but parked/unverified; do not treat as complete.
- /stuck command: 8 tests pass
- Deterministic brief: 10+ tests pass  
- Task/done tracking: 10+ tests pass
- Chat log consolidation (449 sessions)
- Tree cleanup scout: 78 gates pass
