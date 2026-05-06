# Startup + Standup Audit — 2026-05-06

## Scope
- `docs/STANDUP.md`
- `scripts/kitty_builder.py`
- `scripts/start-session.sh`
- `scripts/golden_demo.sh`
- `.agents/skills/*`

## Findings (highest severity first)

1. `HIGH` `docs/STANDUP.md` was accumulating repeated auto-appended KittyBuilder session dumps.
- Impact: startup context bloat, stale dirty-tree snapshots, noisy hook payload drift.
- Fix applied:
  - Trimmed stale appended blocks from standup.
  - Moved session append target to `docs/handoffs/kittybuilder-session-log.md`.
  - `scripts/kitty_builder.py` now appends to standup only when `KITTY_BUILDER_APPEND_STANDUP=1`.

2. `MED` Quick startup mode could hide baseline failures.
- Impact: false confidence in readiness (`|| true` swallowed failures).
- Fix applied:
  - `scripts/start-session.sh` quick mode now reports pass/fail explicitly.
  - Failure remains non-fatal in quick mode, but is visible and actionable.

3. `MED` Golden demo assumed `venv/bin/python` existed.
- Impact: brittle startup checks on environments without venv path.
- Fix applied:
  - `scripts/golden_demo.sh` now resolves python interpreter (`venv/bin/python` fallback to `python3`).

4. `LOW` Skill workflow consolidation check.
- Impact: potential chain break if optimize skill points to old path.
- Status:
  - `optimize` skill is now aligned to `scripts/kitty_optimizer.py`.
  - No additional broken references found in `.agents/skills/{handoff,optimize,orient}`.

## Verification
- `bash -n scripts/start-session.sh scripts/golden_demo.sh scripts/kitty-standup scripts/verify_setup.sh`
- `scripts/kitty-standup --hook` (compact HOOK block OK)
- `venv/bin/python -m py_compile scripts/kitty_builder.py scripts/builder_intake.py`
- `venv/bin/python -m pytest tests/builder tests/test_builder_intake.py tests/test_builder_intake_compiler.py tests/test_kitty_builder.py::test_delegate_calls_popen_streams_and_logs_banner tests/test_kitty_builder.py::test_delegate_nonzero_exit_reports_failure tests/test_kitty_builder.py::test_delegate_includes_next_agent_packet_context tests/test_kitty_builder.py::test_compile_builder_request_returns_brief tests/test_kitty_builder.py::test_record_builder_recommendation_writes_ledger -q --tb=short --noconftest`
  - Result: `29 passed`
- `bash scripts/start-session.sh --quick`
  - Result: setup checks pass, quick baseline pass, server-not-running warning expected.

## Remaining risks
- `scripts/kitty_builder.py --brief` progress metrics are sourced from `project.json` and may drift from `TASKS.md` if not synchronized.
- Full golden demo was not run in this pass because no local server process was running.
