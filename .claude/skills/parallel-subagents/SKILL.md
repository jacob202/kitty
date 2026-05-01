---
name: parallel-subagents
description: Pattern for spawning multiple specialized subagents that work independently and report to a coordinator. Use when facing 2+ truly independent tasks (different subsystems, no shared files), especially for multi-component refactors or audits.
type: process
---

Act as a Coordinator Agent. This skill operationalizes parallel subagent execution to collapse serial work into one coordinated burst.

## When to Use

- 2+ independent tasks in different subsystems (backend, frontend, evals, infra)
- A broad audit that needs multiple lenses (security, performance, test coverage, dependencies)
- A refactor touching 3+ unrelated areas
- The launch plan's parallel work streams (one agent on knowledge pipeline, one on UX, one on architecture)

## When NOT to Use

- Tasks share files or interfaces (serial is safer)
- Single-subsystem work
- Anything where a misstep is hard to roll back
- Quick fixes (<15 min) — overhead exceeds benefit

## The Pattern

```
1. DECOMPOSE     → Break work into N independent lanes; each lane has one clear deliverable
2. SCOPE EACH    → For each lane, define: directory boundary, allowed files, forbidden files, deliverable shape
3. SPAWN         → Launch all subagents in ONE message with full instructions per lane
4. STEP BACK     → Stop. Do not check status. Trust them to return.
5. RECEIVE       → When all results land, review ALL outputs before any commit
6. RECONCILE     → Resolve conflicts (rare, since lanes were independent)
7. UNIFIED TEST  → Run scripts/clear-and-test.sh; all green or revert
8. COMMIT BATCH  → One commit per lane (clean separation) OR one batched commit (if tightly related)
```

## Lane Brief Template

Use this exact shape when spawning each subagent:

```
LANE: <name>
DELIVERABLE: <single sentence>
ALLOWED FILES: <explicit list or directory>
FORBIDDEN FILES: <explicit no-touch list — at minimum: other lanes' files>
SUCCESS LOOKS LIKE: <what proof of completion you expect>
TIME BUDGET: <token / wall-clock cap>
REPORT: <required final report format>
STOP CONDITION: <when to abort>
```

## Hard Rules

- All subagent calls go in ONE message (parallel, not sequential).
- After spawning, do NOT poll status. Wait for results.
- Never let a subagent commit. Coordinator owns the merge.
- If any lane fails, the whole batch holds — do not partial-merge.
- Cut parallel agents the moment they stop producing evidence (Jacob's rule).

## Anti-Patterns

- Spawning 5+ parallel agents on overlapping work — guaranteed merge pain.
- "Quick parallel agent for this small thing" — overhead kills it.
- Letting agents run unbounded — always set a deliverable + stop condition.

## Example: Kitty Launch Plan Sub-Project Parallelism

For the larger launch plan (Layer 1, Sub-Project 1: Personal Onboarding Pipeline), this would look like:

- **Lane A** (`backend-pipeline`): build the `OnboardingPipeline` class in `src/services/`, allowed files: `src/services/onboarding_pipeline.py`, `tests/test_onboarding_pipeline.py`. Forbidden: anything else.
- **Lane B** (`frontend-wizard`): build the first-run wizard UI in `garage-ui/app/components/onboarding/`. Allowed: that directory only.
- **Lane C** (`agent-roles`): wire KnowledgeGetter / Librarian / Embedder agent stubs in `src/agents/onboarding/`. Allowed: that directory only.
- **Coordinator** (Sonnet/Opus): receives all three diffs, resolves any shared-config issues, runs full test suite, commits in 3 separate commits.
