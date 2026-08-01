# Skill Registry

Single source of truth for every skill bundled with this repo. User-installed
skills under home-directory tool configs are intentionally excluded.

**Last verified:** 2026-08-01 — corrected the interactive/Builder execution
boundary and added measured KB-effectiveness wiring to session-end.

## Canonical skill locations

| Path | Purpose | Loaded by |
|---|---|---|
| `.claude/skills/` | Repo-local Claude Code skills | Claude Code |
| `.agents/skills/` | Repo-local cross-tool agent skills | OpenCode / agents; Claude and Codex route through `START_HERE.md`, `CLAUDE.md`, and `AGENTS.md` |

Duplicate skills across both locations are not allowed. `second-opinion` is
canonical under `.claude/skills/`.

## Skills by location

### `.claude/skills/` (4 skills)

| Skill | Verified | Verdict | Why |
|---|---|---|---|
| catchup | 2026-07-15 | KEEP | Rebuilds session context |
| debug-fix | 2026-07-15 | KEEP | Active bug-fixing workflow |
| remember | 2026-07-15 | KEEP | Persists durable preferences |
| second-opinion | 2026-07-15 | KEEP | Independent model review before asking Jacob |

### `.agents/skills/` (10 active + 8 archived)

| Skill | Verified | Verdict | Why |
|---|---|---|---|
| engineering/improve-codebase-architecture | 2026-07-15 | KEEP | Architecture improvement guided by domain docs |
| image-gen | 2026-07-15 | KEEP | Wired to ComfyUI endpoint |
| isa | 2026-07-21 | KEEP | Load-bearing specification/verification workflow |
| journal-entry | 2026-07-15 | KEEP | Wired to Kitty journal subsystem |
| mcp-kitty-council | 2026-07-15 | KEEP | Council routing |
| next | 2026-08-01 | KEEP | Continues one valid interactive assignment; inspects Builder for collisions but never consumes its queue without explicit Builder intent |
| provider-credit-debugging | 2026-07-15 | KEEP | Kitty-specific provider/credit debugging |
| orca-orchestration | 2026-07-26 | KEEP | Parallel/phased Builder execution layer |
| session-end | 2026-08-01 | KEEP | Surveys live work, preserves evidence/continuity, records execution ownership, writes a strict KB-effectiveness receipt, extracts durable knowledge/corrections, and records workflow signals |
| expert-swarm | 2026-07-26 | UNVERIFIED | Low historical usage; requires Jacob confirmation before archive |

Deleted 2026-07-21 after verification/confirmation: `debug-issue`,
`explore-codebase`, `refactor-safely`, `review-changes`, `autonomy_tune`, and
`tune`.

Archived 2026-07-21 under `.agents/skills/_archive/`: `extract-wisdom`,
`first-principles`, `iterative-depth`,
`iterative-self-review-meta-optimization`, `red-team`,
`root-cause-analysis`, `science-method`, and `systems-thinking`.

## Recorded human decisions

- **H5**: archive the eight unused generic reasoning skills while preserving
  their content.
- **Interactive continuation boundary** (corrected 2026-08-01): bare `next`
  continues the current interactive Claude Code/OpenCode/Codex assignment. It
  does not apply initiatives, select packets, or drain Builder. Explicit
  `builder next` or a valid Builder bundle enters Builder's lane.
- **Single execution owner** (2026-08-01): every implementation is owned by
  exactly one of `interactive` or `builder`. Review does not transfer ownership.
- **Learning without a second backlog** (ADR 0025): session-end records evidence
  signals in `~/kb`; execution promotion remains governed and deduplicated.
- **Measured KB effectiveness** (2026-08-01): session-end writes a hash-chained,
  tamper-evident receipt through `scripts/kb_effectiveness.py`. Unknown token,
  time, cost, and quality measurements stay null. Cohort comparisons are
  observational and do not prove causation.

## Supporting scripts

| Script | Purpose | Authority boundary |
|---|---|---|
| `scripts/session_learning.py` | Record repeated workflow failures/corrections | Evidence only; no automatic issue or Builder task |
| `scripts/kb_effectiveness.py` | Record KB retrieval/outcome receipts and produce rolling reports | Measurement only; no roadmap, queue, issue, or priority mutation |
| `scripts/session_end_survey.sh` | Read-only field inventory | Must report unavailable sources honestly |

## Freshness check

Re-verify this file whenever:

- a skill is added, removed, merged, archived, or rewired;
- a supported coding tool changes its `next` semantics;
- session-end changes its KB, continuity, or measurement contract;
- the leverage audit runs; or
- this verification date is older than 90 days.

The 2026-08-01 re-walk verified that bare `next` is interactive-only,
Builder remains autonomous, session-end records exactly one execution owner, and
KB effectiveness is measured without creating another execution authority.
