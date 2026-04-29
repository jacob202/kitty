# Gemini Chat Log Intake

Last updated: 2026-04-28

Use this when Gemini reviews raw Kitty chat exports.

## Goal

Turn raw chat history into reviewed canonical project inputs without deleting or rewriting raw logs.

## Input

- Raw chat export files from `kitty-archives/chat_exports/raw/`, or the current equivalent folder.
- The current control docs:
  - `CURRENT_FOCUS.md`
  - `KITTY_CONTEXT.md`
  - `docs/DECISIONS.md`
  - `docs/PARKED_FEATURES.md`
  - `docs/FILE_GOVERNANCE.md`
  - `docs/CHAT_LOG_CONSOLIDATION_REPORT.md`

## Gemini Prompt

```text
You are reviewing raw chat logs for Kitty, Jacob's local-first assistant project.

Do not write code.
Do not collapse everything into a vague summary.
Do not recommend deleting raw logs.

Extract only durable project information into the categories below.
Preserve enough context that a future builder can revive parked ideas without rereading the raw logs.
Mark uncertain items as needs_review.

Authority order:
1. CURRENT_FOCUS.md
2. active spec in specs/
3. KITTY_CONTEXT.md
4. docs/DECISIONS.md
5. docs/FILE_GOVERNANCE.md
6. docs/PARKED_FEATURES.md
7. SESSION_SUMMARY.md
8. raw chat logs

Output exactly these sections:

# Chat Log Consolidation Draft

## Source Files
- file:
- date range if known:
- confidence:

## Decisions
For each:
- title:
- decision:
- why:
- rejected alternatives:
- consequences:
- source evidence:
- status: accepted_candidate / needs_review

## Parked Features
For each:
- title:
- source/context:
- problem it solves:
- proposed behavior:
- why not now:
- dependencies:
- implementation sketch:
- risks:
- revival trigger:
- minimum safe version:
- status: parked_candidate / needs_review

## Active Tasks
For each:
- title:
- source:
- next concrete action:
- affected files:
- validation command:
- status:

## Rejected Ideas
For each:
- idea:
- why rejected:
- revisit trigger if any:

## Corrections
For each:
- correction:
- wrong behavior it prevents:
- affected files or surfaces:
- validation:

## User Preferences
For each:
- preference:
- evidence:
- confidence:
- scope:

## Project Facts
For each:
- fact:
- evidence:
- confidence:

## File References
For each:
- path:
- why it matters:
- status: active / parked / unknown / stale

## Cleanup Candidates
For each:
- path:
- type:
- safe or unsafe:
- validation before cleanup:

## Specialist KB Candidates
For each:
- specialist:
- source material:
- reason:
- safety/source notes:

## Skill Candidates
For each:
- skill:
- trigger:
- behavior:
- why not now if parked:

## Bugs / Failures
For each:
- symptom:
- likely cause:
- affected files:
- reproduction:
- validation after fix:

## Open Loops
For each:
- question:
- why it matters:
- next step:

## Do Not Write Yet
List anything that should remain out of code for now.
```

## Acceptance Criteria

Gemini output is usable only if it:

- keeps decisions separate from preferences
- keeps parked features information-rich
- marks uncertainty clearly
- includes exact file paths where available
- includes validation commands for proposed fixes
- avoids claiming raw logs are safe to delete

## Landing Process

1. Save Gemini output as a draft under `docs/imports/`.
2. Review it manually.
3. Copy accepted decisions into `docs/DECISIONS.md`.
4. Copy accepted parked items into `docs/PARKED_FEATURES.md`.
5. Copy accepted facts/preferences/open loops into their canonical docs.
6. Update `docs/CHAT_LOG_CONSOLIDATION_REPORT.md`.
7. Zip/back up raw logs only after accepted extraction exists.
