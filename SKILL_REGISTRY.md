# Skill Registry

Single source of truth for every skill bundled with this repo.
User-installed skills (`~/.config/opencode/skills/`, `~/.claude/skills/`)
are intentionally not listed here — this registry covers repo-owned only.

**Last verified:** 2026-08-01 — added the canonical cross-tool `next` workflow
and re-verified the learning-aware `session-end` wiring.

## Canonical skill locations

| Path | Purpose | Loaded by |
|---|---|---|
| `.claude/skills/` | Repo-local Claude Code skills | Claude Code |
| `.agents/skills/` | Repo-local agent skills | OpenCode / agents; Claude and Codex are routed to canonical skills through `START_HERE.md`, `CLAUDE.md`, and `AGENTS.md` |

Duplicate skills across both locations are not allowed — pick one.
The audit found `second-opinion` in both; `.claude/skills/` is canonical,
the `.agents/skills/second-opinion/` copy was removed 2026-07-15.

## Skills by location

### `.claude/skills/` (4 skills)

| Skill | Verified | Verdict | Why |
|---|---|---|---|
| catchup | 2026-07-15 | KEEP | Uniquely valuable; rebuilds session context |
| debug-fix | 2026-07-15 | KEEP | Active bug-fixing workflow |
| remember | 2026-07-15 | KEEP | Wired to `scripts/remember.py` + `config/PREFERENCES.md` |
| second-opinion | 2026-07-15 | KEEP (canonical) | Independent model review before asking Jacob |

### `.agents/skills/` (10 active + 8 archived)

| Skill | Verified | Verdict | Why |
|---|---|---|---|
| engineering/improve-codebase-architecture | 2026-07-15 | KEEP | Architecture improvement guided by domain docs |
| image-gen | 2026-07-15 | KEEP | Wired to ComfyUI endpoint |
| isa | 2026-07-21 | KEEP | 27 commits reference it — genuinely load-bearing, not ceremony |
| journal-entry | 2026-07-15 | KEEP | Wired to Kitty journal subsystem |
| mcp-kitty-council | 2026-07-15 | KEEP | Council routing — active |
| next | 2026-08-01 | KEEP | Canonical bare-`next` resolver: cold start, live collision survey, idempotent initiative apply, one eligible packet, governed execution, full session-end, then stop |
| provider-credit-debugging | 2026-07-15 | KEEP | Kitty-specific debugging |
| orca-orchestration | 2026-07-26 | KEEP | Referenced from `docs/FREE_WORKERS.md` as the parallel/phased execution layer |
| session-end | 2026-08-01 | KEEP | Surveys live work, preserves evidence and continuity, extracts `~/kb` knowledge/corrections, records deduplicated workflow signals through `scripts/session_learning.py`, and leaves one honest next action |
| expert-swarm | 2026-07-26 | UNVERIFIED | 2 lifetime commits; only reference is an archived doc. Same profile as the H5 archive set — needs Jacob's confirm before archiving |

**Deleted 2026-07-21** (Jacob confirmed unused; `code-review-graph` MCP confirmed not connected in this environment, superseded by `.codegraph`): `debug-issue`, `explore-codebase`, `refactor-safely`, `review-changes`.

**Deleted 2026-07-21** — `autonomy_tune`, `tune`. The registry's prior "KEEP — core to Builder loop" verdict for `autonomy_tune` was never verified against actual code: zero references in `gateway/`, `scripts/`, or the `kitty` CLI. Jacob confirmed directly he never used either. The 2026-06-20 consolidation plan's proposed merge is moot now that both are gone.

**Archived 2026-07-21** to `.agents/skills/_archive/` (H5 executed — Jacob confirmed unused, content preserved not deleted, 1-3 lifetime commits each): `extract-wisdom`, `first-principles`, `iterative-depth`, `iterative-self-review-meta-optimization`, `red-team`, `root-cause-analysis`, `science-method`, `systems-thinking`.

## Recorded human decisions

- **H5** (recorded 2026-07-15, executed 2026-07-21): Archive the 8 generic agent skills — see list above. Original record: `docs/AUDIT_ENGINEERING_LEVERAGE_2026-07-14.md` §10 ARCHIVE A2.
- **Cross-tool next protocol** (approved 2026-08-01): a bare continuation instruction routes to `.agents/skills/next/SKILL.md`; one instruction resolves and completes one bounded work cycle, invokes session-end, and stops.
- **Learning without a second backlog** (approved 2026-08-01): session-end records evidence signals in `~/kb`, ordinary signals require repetition, integrity incidents may promote immediately, and execution promotion remains deduplicated through Builder rather than a new task store.

## Freshness check

Re-verify this file whenever:

- a skill is added, removed, merged, or archived;
- a skill's wiring, scripts, configuration, entrypoint, or authority changes;
- the leverage audit runs;
- a supported coding tool no longer follows the `START_HERE.md` routing contract.

Last verified date: `2026-08-01`. If that date is older than 90 days at audit
time, re-walk every listed directory and live reference.

The 2026-08-01 re-walk verified that `next` has a canonical skill file,
`START_HERE.md` routes all supported tools to it, `session-end` invokes the
validated learning helper, and neither skill creates another execution or
continuity authority.
