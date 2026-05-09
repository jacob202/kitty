# SKILLS COMPARATIVE REPORT
## External Skills vs Our Skills

**Date**: 2026-05-09  
**Purpose**: Compare external skill systems with our implementation

---

## External Skill Systems Reviewed

| Source | Skills | Approach |
|--------|--------|----------|
| **Matt Pocock** | 66375 ⭐ | diagnose, tdd, to-issues, triage, zoom-out |
| **addyosmani/agent-skills** | 7 slash commands | /spec, /plan, /build, /test, /review, /code-simplify, /ship |
| **vlting/claude-skills** | saga, epic, q, relay | Hierarchical: saga→epic→q→relay |
| **clouseryan/agentic-skills** | 13 agents | Multi-agent: orchestrator, ba-agent, dev-agent, etc. |
| **AlirezaRezvani** | 235 skills | Comprehensive across 12 platforms |
| **roman01la/skills-agents** | 18 skills + 10 agents | Router→pipeline pattern |
| **anthropics/skills** | Official reference | Template + document skills |
| **vultuk/coding-agent-skills** | 6 skills | GitHub workflow automation |

---

## Our Skills (Current)

| Skill | File | Purpose |
|-------|------|---------|
| SKILL 1 | PROJECT_REALITY_CHECK.md | Run BEFORE any large work |
| SKILL 2 | (via docs) | Debug & stabilize |
| SKILL 3 | ENGINEERING_LOOP.md | Audit → improve → ship |

---

## Key Differences

### 1. Trigger System

| Their Approach | Our Approach |
|----------------|---------------|
| `/spec`, `/plan`, `/build`, `/test`, `/review` (slash commands) | Read file first (MASTER_INDEX.md) |
| Auto-trigger on context | Grep-based discovery |
| Progressive disclosure | One-file lookup |

**Recommendation**: Add slash-style quick triggers to CLI

### 2. Agent Routing

| Their Approach | Our Approach |
|----------------|---------------|
| `using-superpowers` skill routes to worker agents | Manual selection |
| Pipeline: task-planner → implementer → reviewer | No pipeline defined |
| Automatic route selection | Read docs to find path |

**Recommendation**: Create routing skill (router)

### 3. Multi-Agent Orchestration

| Their Approach | Our Approach |
|----------------|---------------|
| `saga` → `epic` → `q` → `relay` (vlting) | No |
| dev-team: 13 specialized agents | No |
| Swarm pattern | No |

**Recommendation**: Not needed yet (MVP scope)

### 4. Branch/Worktree Pattern

| Their Approach | Our Approach |
|----------------|---------------|
| Isolated worktrees per task | git worktree optional |
| Branch-per-stage | Main branch |
| Feature flags for safe delivery | Not implemented |

**Recommendation**: Add git-guardrails (like pocock)

### 5. PRD/Spec Flow

| Their Approach | Our Approach |
|----------------|---------------|
| `/spec` creates PRD | Handoff creates tasks |
| `/plan` breaks to issues | TASKS.md exists |
| Vertical slices | Our slice approach |

**Recommendation**: Add `/spec` equivalent

---

## What They're Doing Better

### 1. Slash Command Triggers (addyosmani)

```bash
/spec  # Define what to build
/plan  # Small atomic tasks  
/build # One slice at a time
/test  # Tests are proof
/review # Code health
```

### 2. Git Guardrails (pocock)

- Block dangerous git commands before execution
- Pre-commit checks

### 3. PR/Issue Integration (vultuk)

- Load GitHub issue → worktree → PR flow
- Auto-issue-fixer

### 4. Multi-Agent Teams (clouseryan)

- orchestrator + ba-agent + dev-agent + qa-agent + etc.
- Clear role boundaries

---

## Recommendations

### High Priority (Do First)

| # | Recommendation | Source |
|---|----------------|--------|
| 1 | Add slash-like aliases to CLI | addyosmani |
| 2 | Create `/spec` equivalent | pocock |
| 3 | Add git guardrails | pocock |

### Medium Priority (Do Second)

| # | Recommendation | Source |
|---|----------------|--------|
| 4 | Branch-per-stage workflow | vlting |
| 5 | Feature flags | vlting/romans |

### Low Priority (Nice to Have)

| # | Recommendation | Source |
|---|----------------|--------|
| 6 | Multi-agent orchestration | clouseryan/roman |
| 7 | PRD template | vlting |

---

## Implementation Plan

### Add Slash Commands to Kitty

```bash
# In kitty CLI
case "$1" in
  spec)    cat PROJECT_REALITY_CHECK.md ;;
  plan)    cat docs/NEXT_STEPS.md ;;
  build)  echo "Use: python scripts/scaffold.py" ;;
  test)   venv/bin/python -m pytest tests/ -q --tb=short ;;
  review) cat docs/IMPROVEMENT_AUDIT.md ;;
  *)      help ;;
esac
```

### Add Git Guardrails

- Prevent `push --force`
- Block `clean` without flags
- Require PR before merge to main

---

## Gap Summary

| Area | They Have | We Have | Priority |
|------|----------|---------|----------|
| Command triggers | ✅ | ❌ (use file) | HIGH |
| Git safety | ✅ | ❌ | MEDIUM |
| PRD workflow | ✅ | ❌ (handoff) | MEDIUM |
| Multi-agent | ✅ | ❌ (no need) | LOW |
| Feature flags | ✅ | ❌ | LOW |

---

## Next Actions

1. Add slash-style quick commands to `kitty` CLI
2. Add git-guardrails to AGENTS.md
3. Optional: Add `/spec` workflow