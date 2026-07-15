# Skill Registry

Single source of truth for every skill bundled with this repo.
User-installed skills (`~/.config/opencode/skills/`, `~/.claude/skills/`)
are intentionally not listed here — this registry covers repo-owned only.

**Last verified:** 2026-07-15 by engineering leverage audit (phase 8/9)

## Canonical skill locations

| Path | Purpose | Loaded by |
|---|---|---|
| `.claude/skills/` | Repo-local Claude Code skills | Claude Code |
| `.agents/skills/` | Repo-local agent skills (OpenCode + others) | OpenCode / agents |

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

### `.agents/skills/` (20 skills after dedup)

| Skill | Verified | Verdict | Why |
|---|---|---|---|
| autonomy_tune | 2026-07-15 | KEEP | Core to Builder loop — fixes autonomy stalls |
| debug-issue | 2026-07-15 | **MERGE pending** → debug-fix | Overlapping purpose; needs content review |
| engineering/improve-codebase-architecture | 2026-07-15 | KEEP | Architecture improvement guided by domain docs |
| explore-codebase | 2026-07-15 | **DELETE pending** | Redundant with codegraph + codemap |
| extract-wisdom | 2026-07-15 | **H5 archive candidate** | Generic; awaits owner decision |
| first-principles | 2026-07-15 | **H5 archive candidate** | Generic; awaits owner decision |
| image-gen | 2026-07-15 | KEEP | Wired to ComfyUI endpoint |
| isa | 2026-07-15 | KEEP | Ideal State Artifact — core to Builder packets |
| iterative-depth | 2026-07-15 | **H5 archive candidate** | Generic; awaits owner decision |
| iterative-self-review-meta-optimization | 2026-07-15 | **H5 archive candidate** | Generic; awaits owner decision |
| journal-entry | 2026-07-15 | KEEP | Wired to Kitty journal subsystem |
| mcp-kitty-council | 2026-07-15 | KEEP | Council routing — active |
| provider-credit-debugging | 2026-07-15 | KEEP | Kitty-specific debugging |
| red-team | 2026-07-15 | **H5 archive candidate** | Generic; awaits owner decision |
| refactor-safely | 2026-07-15 | KEEP | Dependency-aware refactoring |
| review-changes | 2026-07-15 | **MERGE pending** → debug-fix / pr-review | Overlapping review purpose |
| root-cause-analysis | 2026-07-15 | **H5 archive candidate** | Generic; awaits owner decision |
| science-method | 2026-07-15 | **H5 archive candidate** | Generic; awaits owner decision |
| systems-thinking | 2026-07-15 | **H5 archive candidate** | Generic; awaits owner decision |
| tune | 2026-07-15 | **MERGE pending** → autonomy_tune | Overlapping autonomy tuning |

## Open human decisions (from audit)

- **H5**: Should the 8 generic agent skills (extract-wisdom, first-principles,
  iterative-depth, iterative-self-review-meta-optimization, red-team,
  root-cause-analysis, science-method, systems-thinking) be archived or kept?
  Audit recommendation: archive (not Kitty-specific, available as generic LLM
  capability). Blocked on Jacob's call — see
  `docs/AUDIT_ENGINEERING_LEVERAGE_2026-07-14.md` §10 ARCHIVE A2.

## Freshness check

This file must be re-verified when:
- a skill is added, removed, merged, or archived
- a skill's wiring (scripts, config, endpoints) changes
- the lev
   
Last verified date: `2026-07-15`. If that date is older than 90 days at
audit time, the registry should be re-walked.