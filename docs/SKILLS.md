# Kitty Skills Roster

Project root: `/Users/jacobbrizinski/Projects/kitty`
Crush config: `crush.json` → `skills_paths: ["./src/tools/superpowers/skills", "./skills"]`

---

## Overview

Kitty manages **35 skills** across three skill directories:

| Directory | Source | Count | Status |
|-----------|--------|-------|--------|
| `./src/tools/superpowers/skills/` | Superpowers (third-party) | 21 | Active |
| `./consolidated-skills/` | Consolidated skills | 3 | Active |
| `./skills/legacy-skills/` (via `archive/skills/legacy-skills/`) | Project-original | 11 | ✅ Archived (loadable) |

---

## Consolidated Skills

Located at `./consolidated-skills/`. These were generated from conversation history and packaged as standalone skills.

| Skill | Purpose |
|-------|---------|
| **execution** | Implement features, fix bugs, execute plans |
| **planning** | Break down multi-step features into tasks |
| **reasoning** | Non-trivial analysis, debugging, and decision-making |

---

## Superpowers Skills

Located at `./src/tools/superpowers/skills/`. These are the actively-maintained skills, each with a `SKILL.md` file and optional scripts/references/tests/agents.

### Development Workflow Pipeline

| # | Skill | Type | Purpose | Dependencies | Status |
|---|-------|------|---------|--------------|--------|
| 1 | **using-superpowers** | Meta | Entry point — instructs agents to scan & load skills before responding | None | Active |
| 2 | **brainstorming** | Process | Explore user intent, requirements, and design before implementation. Hard-gate against coding without spec | `docs/superpowers/specs/` directory | Active |
| 3 | **writing-plans** | Process | Break specs into bite-sized implementation tasks (2-5 min each) | brainstorming | Active |
| 4 | **writing-skills** | Meta | TDD for skill creation — write pressure tests first, then SKILL.md | test-driven-development | Active |
| 5 | **executing-plans** | Process | Execute a written plan in a **separate** session with checkpoints | writing-plans, finishing-a-development-branch | Active |
| 6 | **subagent-driven-development** | Process | Execute plans in **same** session — dispatch fresh subagents per task | writing-plans, implementer-prompt.md, spec-reviewer-prompt.md, code-quality-reviewer-prompt.md | Active |
| 7 | **dispatching-parallel-agents** | Process | Investigate independent failures/domains concurrently | None | Active |

### Code Quality & Review

| # | Skill | Type | Purpose | Dependencies | Status |
|---|-------|------|---------|--------------|--------|
| 8 | **test-driven-development** | Process | Red-Green-Refactor cycle — no production code without failing test first | `testing-anti-patterns.md` companion | Active |
| 9 | **requesting-code-review** | Process | Dispatch code-reviewer subagent with git diff context after implementations | `code-reviewer.md` agent prompt | Active |
| 10 | **receiving-code-review** | Meta | Verify code review feedback against codebase before implementing — no performative agreement | None | Active |
| 11 | **systematic-debugging** | Process | Root cause investigation (4 phases) before any fix. Iron law: no fixes without RCA | `root-cause-tracing.md`, `defense-in-depth.md`, `condition-based-waiting.md`, `find-polluter.sh` | Active |
| 12 | **surgical-coding** | Process | Karpathy-inspired discipline: think first, minimal changes, surface assumptions | None | Active |
| 13 | **karpathy-guidelines** | Process | Think before coding, simplicity first, goal-driven execution | None | Active |
| 14 | **verification-before-completion** | Meta | Never claim work passes without fresh verification evidence | None | Active |

### Completion & Integration

| # | Skill | Type | Purpose | Dependencies | Status |
|---|-------|------|---------|--------------|--------|
| 15 | **finishing-a-development-branch** | Process | Verify tests, present merge/PR/cleanup options, execute choice | verification-before-completion | Active |
| 16 | **using-git-worktrees** | Process | Create isolated workspaces for parallel branch work | None | Active |

### Autonomous & Experimental

| # | Skill | Type | Purpose | Dependencies | Status |
|---|-------|------|---------|--------------|--------|
| 17 | **vibe-coding** | Process | Autonomous feature addition & self-repair — agent as senior partner, minimal user input | None (Kitty-specific: `src/core/`, `src/tools/`) | Active |
| 18 | **epistemic-agent-training** | Architecture | Advanced reasoning (KiP, MCTS, PoT, Council of Five) for Kitty as Knowledge-Building Partner | ChromaDB, SQLite FTS5 (Kitty infrastructure) | Active |
| 19 | **nanochat** | External | Train custom LLMs via Karpathy's nanochat framework | `~/nanochat/` checkout, GPU | Active |
| 20 | **autoresearch-mlx** | External | Autonomous ML research experiments on Apple Silicon | Apple Silicon, MLX, `autoresearch-mlx` checkout | Active |
| 21 | **self-correction** | Meta | Detect stall patterns (repeated no-op tool calls, edit failures, silent loops) and break the cycle | None | Active |

---

## Legacy Skills

Located at `./skills/legacy-skills/`. These are original project skills, likely authored before the superpowers migration.

### Status: ✅ NOW LOADABLE

Crush config has `skills_paths: [..., "./skills", "./skills/legacy-skills"]` — the nested path is now explicitly included so Crush discovers all 11 legacy skills.

### Roster

| # | Skill | Type | Purpose | Dependencies | Status |
|---|-------|------|---------|--------------|--------|
| L1 | **ai-app-improvement-loop** | Process | Iteratively analyze & improve an app one high-impact change at a time | git, grep, find | ✅ Loadable |
| L2 | **code-cleanup** | Process | Remove debug artifacts, format, fix imports, lint | prettier, ruff | ✅ Loadable |
| L3 | **code-optimization** | Process | Performance analysis via grep — find bottlenecks, security issues | grep, awk | ✅ Loadable |
| L4 | **create-style-guide** | Process | Generate STYLE_GUIDE.md from CSS analysis | grep, awk | ✅ Loadable |
| L5 | **deepseek-reasoning-review** | Meta | Switch to R1 model for critical review of correctness/completeness/security | deepseek-reasoner provider | ✅ Loadable |
| L6 | **deployment-safety-review** | Process | Analyze git diffs for regression risk before shipping | git diff | ✅ Loadable |
| L7 | **flashcard-study-system** | Process | Build a full flashcard app with spaced repetition | Python (Flask, SQLite) | ✅ Loadable |
| L8 | **open-code** | Meta | Orchestrator — pipelines cleanup → optimization → safety review → reasoning review | code-cleanup, code-optimization, deployment-safety-review, deepseek-reasoning-review | ✅ Loadable |
| L9 | **technical-documentation** | Process | Generate plain-language FORME.md for non-technical stakeholders | None | ✅ Loadable |
| L10 | **typescript-code-review** | Process | 300+ checkpoint exhaustive code review for TypeScript | TypeScript tooling | ✅ Loadable |
| L11 | **visual-web-app-development** | Process | Modern responsive web app development with UI/UX focus | Flask, SocketIO (Kitty ecosystem) | ✅ Loadable |

### Overlap Analysis

Several legacy skills overlap with superpowers skills in purpose but have different implementation approaches:

| Legacy Skill | Overlapping Superpowers Skill | Recommendation |
|-------------|------------------------------|----------------|
| `code-cleanup` | `surgical-coding`, `karpathy-guidelines` | Superpowers are behavioral/process; legacy is tool-based. Both valuable. Keep if loaded. |
| `code-optimization` | `surgical-coding`, `karpathy-guidelines` | Legacy is grep-based analysis; superpowers are principles. Complementary. |
| `deployment-safety-review` | `verification-before-completion`, `receiving-code-review` | Legacy is diff-focused; superpowers are process-focused. Different scope. |
| `deepseek-reasoning-review` | `requesting-code-review` | Legacy is model-switching for review; superpowers use subagents. Distinct approaches. |

---

## How to Trigger Skills

Skills are accessible via two slash commands in the chat interface:

| Command | Description |
|---------|-------------|
| `/skills` | List all 35 registered skills (21 active, 3 consolidated, 11 archived legacy) |
| `/skill <name>` | Load a skill into active context (max 3 — injected into every subsequent NL query) |
| `/skill-unload <name>` | Remove a loaded skill from context |
| `/skill-clear` | Unload all loaded skills at once |
| `/skill-loaded` | Show which skills are currently loaded and slot usage |

### Examples

```
/skills
/skill brainstorming
/skill systematic-debugging
/skill code-cleanup
/skill visual-web-app-development
```

### Fuzzy Matching

`/skill` includes typo tolerance — if you misspell a skill name, it will suggest close matches:

```
> /skill brainstormig
Unknown skill: brainstormig. Did you mean: brainstorming?
```

### Case Insensitivity

Skill names are matched case-insensitively. All of these work:

```
/skill Brainstorming
/skill BRAINSTORMING
/skill brainstorming
```

### How It Works

- `src/tools/skill_commands.py` scans three skill directories and builds a registry:
  - `src/tools/superpowers/skills/` (21 skills — active)
  - `consolidated-skills/` (3 skills — active)
  - `archive/skills/legacy-skills/` (11 skills — archived, but fully loadable)
- `src/api/dispatcher.py` handles `/skills` and `/skill` commands, calling into `skill_commands.py`'s `list_skills()` and `get_skill()` functions
- All output uses plain `sys.stdout.write()` — no Rich markup, consistent with the existing dispatcher pattern

### Archived Skills

Legacy skills appear in `/skills` with an `[archived]` tag. They are fully loadable and viewable via `/skill` — the tag simply indicates they originate from the archive directory rather than the active skill directories.

---

## Key Observations

1. **Legacy skills are now loadable** — The `./skills/legacy-skills/` path was added to `crush.json` `skills_paths`, making all 11 legacy skills discoverable by Crush.
2. **Superpowers skills are the primary set** — They have scripts, tests, agents, and follow a consistent pattern. The `writing-skills` skill documents how to create new ones.
3. **No conflicting names** — Legacy and superpowers skill names don't collide. They co-exist now that the path is fixed.
4. **Kitty-specific skills** — `epistemic-agent-training`, `vibe-coding`, and `flashcard-study-system` reference Kitty codebase internals (`src/core/`, `src/tools/`, Flask/SocketIO stack).
5. **External-dependent skills** — `nanochat` and `autoresearch-mlx` require repositories (`~/nanochat/`, `autoresearch-mlx`) that may not be present on this machine. They'll fail gracefully at execution time.
6. **Meta skills don't execute code** — They change agent behavior: `using-superpowers`, `deepseek-reasoning-review`, `receiving-code-review`, `verification-before-completion`, `self-correction`.
