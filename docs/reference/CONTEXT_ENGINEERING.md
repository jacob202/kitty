# Context Engineering Playbook

This playbook optimizes cold start and long-running work without weakening authority or verification.

## Goal

Keep the smallest high-signal context that can produce the desired outcome. Expand only when evidence requires it, and move durable state outside the active conversation before context becomes noisy or is compacted.

## Diagnose the context problem

Use the mechanism that matches the actual source of growth:

- **Tool-result clearing:** discard old, bulky, re-fetchable file reads and API responses while retaining that the call occurred.
- **Compaction:** replace an overgrown conversation with a concise continuation record. This is necessarily lossy.
- **Memory:** persist structured facts, decisions, progress, and corrections outside the conversation so they survive sessions and compaction.
- **Subagents/fresh contexts:** isolate investigation or verification so one task does not contaminate another with irrelevant history.

Do not use memory as a transcript dump, compaction as an excuse to lose requirements, or a huge context window as a substitute for retrieval discipline.

## Baseline sequence

1. Run `./kitty context --agent`.
2. Classify the request: informational, planning, or code change.
3. Load only canonical sources needed for that class:
   - informational: `docs/AUTHORITY_MAP.md` plus directly relevant authority files;
   - planning: add `docs/ROADMAP.md`, `docs/ACTIVE_MISSION.md`, and `.claude/STATE.md`;
   - code change: use the full `START_HERE.md` reading order.
4. Gather local evidence for the specific scope before changing files.
5. For implementation or repair work, load `.agents/skills/verified-delivery/SKILL.md` and create an outcome contract before editing.
6. Re-check authorization and live state immediately before mutation.

## What active context should contain

Keep:

- the current user-visible outcome and acceptance criteria;
- canonical constraints and explicit decisions;
- the smallest relevant code/test surface;
- current branch, worktree, SHA, changed paths, and live failures;
- unresolved questions, blockers, and the next verification action.

Clear, summarize, or re-fetch:

- large tool outputs and whole-file reads no longer under examination;
- repeated discussion and speculative explanations;
- stale plans and superseded decisions;
- evidence already represented by a concise receipt or reproducible command.

## Compaction and handoff contract

Before compaction, a context reset, or a cross-tool handoff, preserve explicitly:

1. outcome contract and non-goals;
2. accepted decisions and their authority;
3. current implementation state, branch/worktree, and SHA;
4. exact verification commands and results;
5. unresolved failures and blockers;
6. one concrete next action.

After resuming, validate this record against live Git/runtime state before trusting it.

## Task-scoped expansion rules

- Do not read broad historical plans by default.
- Prefer authority docs and live runtime projections over handoff prose.
- Treat unknowns from the context receipt as unresolved, not as permission to guess.
- Expand context in small steps, each tied to an explicit open question.
- Keep implementation and independent verification in separate contexts when acceptance matters.

## Mutation gate

Before any edit, confirm:

- requested outcome is concrete and in scope;
- observable acceptance criteria exist;
- the relevant authority path is identified;
- live Git/runtime evidence does not contradict inherited prose;
- the exact files to change are known;
- required verification can be performed or will be reported as unavailable.

## Completion gate

A plausible artifact is not a verified outcome. Use the states defined by `verified-delivery`:

- `verified`;
- `implemented, awaiting verification`;
- `blocked`;
- `failed`.

Never claim “done,” “fixed,” or “working” without reproducible evidence bound to the reviewed SHA or runtime artifact.

## Source pattern

This playbook adapts Anthropic’s distinction between memory, compaction, and tool-result clearing, and its grade-and-revise Outcomes pattern, into Kitty’s provider-independent workflow. Claude API implementations may later use the corresponding first-party context-management and Managed Agents features, but the behavioral contract above applies regardless of provider.