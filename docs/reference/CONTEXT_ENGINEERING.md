# Context Engineering Playbook

This playbook optimizes cold start without weakening authority or verification.

## Goal

Load the minimum context needed for the current task, then widen only when evidence requires it.

## Baseline sequence

1. Run `./kitty context --agent`.
2. Classify the request: informational, planning, or code change.
3. Load only canonical sources needed for that class:
   - informational: `docs/AUTHORITY_MAP.md` + directly relevant authority file(s);
   - planning: add `docs/ROADMAP.md`, `docs/ACTIVE_MISSION.md`, `.claude/STATE.md`;
   - code change: full `START_HERE.md` reading order.
4. Gather local evidence for the specific scope before changing files.
5. Re-check authorization and live state immediately before mutation.

## Task-scoped expansion rules

- Do not read broad historical plans by default.
- Prefer authority docs and live runtime projections over handoff prose.
- Treat unknowns from the receipt as unresolved, not as permission to guess.
- Expand context in small steps, each tied to an explicit open question.

## Mutation gate

Before any edit, confirm:

- requested outcome is concrete and in scope;
- the relevant authority path is identified;
- live Git/runtime evidence does not contradict inherited prose;
- the exact files to change are known.
