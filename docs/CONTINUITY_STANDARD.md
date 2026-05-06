# Continuity Standard

Last updated: 2026-05-06
Status: active

Purpose: make takeover safe when an agent/session crashes, compacts, or is replaced.

## Required updates after meaningful work

A run is "meaningful" when it changes code, plans, risk posture, rollout order, or verification evidence.

Update all of these before ending the run:

1. `TASKS.md`
2. `docs/TASKS.md`
3. `SESSION_SUMMARY.md`
4. `docs/OPEN_LOOPS.md`
5. `docs/handoffs/HANDOFF-YYYY-MM-DD.md` (dated handoff for the current run)

If a durable policy changed, also update:

6. `docs/DECISIONS.md`

## Mandatory content fields

Each checkpoint must include:

- What was done (files, commands, validations)
- What is planned next (ordered)
- Why that order/decision was chosen
- Blockers and risks
- Exact evidence pointers (tests, reports, docs)

For delegated runs, include:

- lane ownership
- strict gate result and fallback result (if used)
- token telemetry summary

## Token telemetry requirement

When delegation is used, capture actual telemetry from session logs:

- source: `~/.codex/sessions/<yyyy>/<mm>/<dd>/*.jsonl`
- report:
  - per-lane `delta total_tokens`
  - estimated uncached prompt (`input_tokens - cached_input_tokens`)
  - parent-orchestrator delta over the same time window

## Handoff format

Use a dated handoff file per run:

- `YYYY-MM-DD checkpoint`
- chronology
- files touched
- commands/tests run + outcomes
- open blockers
- resume-first files

If the same-day handoff already exists, append to it instead of creating duplicates.

## Enforcement intent

This is process discipline, not product scope expansion. It exists to reduce restart cost, prevent ghost status claims, and keep another model productive within one turn.
