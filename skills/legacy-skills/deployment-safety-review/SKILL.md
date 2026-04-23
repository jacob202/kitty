---
name: deployment-safety-review
description: Review code changes for deployment safety — analyze diffs for regression risk, breaking changes, side effects, and edge cases before shipping
---

## Purpose

Review changes (commits, staged diffs, or PR branches) for deployment safety. Catches regressions, breaking changes, and risks before they hit production.

## When to Activate

Invoke this skill when the user asks:
- "Is it safe to deploy?"
- "Review these changes before shipping"
- "Check this PR/commit for risks"
- "Deployment safety check"
- "Oracle review"
- Any request involving reviewing changes for production readiness

Also activated automatically as Stage 3 of the Open Code pipeline (`skills/open-code/SKILL.md`).

## Review Process

### Step 1: Gather Context

Collect the diff and branch information:

```bash
# Get the diff since base branch or last commit
BASE_BRANCH="${1:-main}"
git fetch origin "$BASE_BRANCH" 2>/dev/null
git diff "$BASE_BRANCH..." --stat          # Files changed summary
git diff "$BASE_BRANCH..."                  # Full diff
git log "$BASE_BRANCH..." --oneline         # Commit messages
```

```bash
# For staged changes (pre-commit)
git diff --cached --stat
git diff --cached
```

```bash
# Check for merge conflicts
git status | grep -c "both modified"
```

```bash
# Check CI status if available
gh pr view --json statusCheckRollup 2>/dev/null
```

### Step 2: Pre-Validation

Run available checks and block if they fail:

```bash
# Lint check (language-appropriate)
ruff check . --quiet 2>/dev/null || echo "❌ Lint failures"
npm run lint 2>/dev/null || echo "❌ Lint failures"
golangci-lint run ./... 2>/dev/null || echo "❌ Lint failures"

# Test quick check
pytest -x --timeout=30 -q 2>/dev/null || echo "❌ Test failures"
npm test -- --bail --passing 2>/dev/null || echo "❌ Test failures"

# Type check
mypy . --strict 2>/dev/null || echo "❌ Type check warnings"
npx tsc --noEmit 2>/dev/null || echo "❌ Type errors"
```

**Blocking failures** (stop here):
- ❌ Lint failures that prevent build
- ❌ Test failures
- ❌ Type errors in changed code
- ❌ Merge conflicts

### Step 3: Structural Analysis

Analyze the diff using targeted grep commands:

**1. Regression Risk**

```bash
# Changes to core/shared modules
echo "$FILES" | grep -E '(utils/|lib/|shared/|core/|common/|base/)'

# Renamed/removed exports
git diff "$BASE_BRANCH..." | grep -E '^-.*(def |class |func |function |export |pub fn)'

# Changed function signatures
git diff "$BASE_BRANCH..." | grep -E '^[-+].*\(.*\).*:' | grep -v '^\+\+\+' | grep -v '^---'

# Modified error handling
git diff "$BASE_BRANCH..." | grep -E '^[-+].*(raise |return err|throw |try:|except |catch )'
```

**2. Breaking Changes**

```bash
# API changes (endpoints, routes)
git diff "$BASE_BRANCH..." | grep -E '^[-+].*(@app\.route|@router\.|app\.get|app\.post|router\.(get|post|put|delete))'

# Database changes
git diff "$BASE_BRANCH..." | grep -E '^[-+].*(CREATE |ALTER |DROP |migrate|Migration|schema)'

# Configuration changes
git diff "$BASE_BRANCH..." --name-only | grep -E '(config|\.env|\.yaml|\.toml|settings)'

# Dependency bumps
git diff "$BASE_BRANCH..." | grep -E '^[-+].*"[~^]?\d+\.\d+\.\d+"'
```

**3. Side Effects**

```bash
# Changes touching multiple unrelated systems
git diff "$BASE_BRANCH..." --name-only | wc -l | xargs -I {} echo "Files changed: {}"
# If > 20 files, flag for review

# Init/shutdown modifications
git diff "$BASE_BRANCH..." | grep -E '^[-+].*(__init__|__main__|main\(|startup|shutdown|on_start|on_stop)'

# Logging/metrics changes
git diff "$BASE_BRANCH..." | grep -E '^[-+].*(log\.|metrics\.|monitor|telemetry)'

# Global state changes
git diff "$BASE_BRANCH..." | grep -E '^[-+].*(global |singleton|_instance|_shared)'
```

**4. Edge Cases**

```bash
# Empty/null handling
git diff "$BASE_BRANCH..." | grep -E '^[-+].*(if .* is None|if not .*:|if .* === null|if .* === undefined|\.get\()'

# Concurrent access
git diff "$BASE_BRANCH..." | grep -E '^[-+].*(thread|lock|mutex|async|await|go )'

# File/network operations
git diff "$BASE_BRANCH..." | grep -E '^[-+].*(open\(|read\(|write\(|requests|fetch\(|http\.)'

# Boundary conditions
git diff "$BASE_BRANCH..." | grep -E '^[-+].*(<=|>=|< 0|> max|len\(|\.length|range\()'
```

### Step 4: Generate Report

```
## 🔍 Deployment Safety Review

### Pre-Validation
- Lint: ✅ / ❌ [details]
- Tests: ✅ / ❌ [pass/total]
- Types: ✅ / ❌ [details]
- Merge Conflicts: ✅ None / ❌ Found
- Blocking issues: Yes/No

### Verdict: ✅ SAFE / ⚠️ CAUTION / ❌ UNSAFE

### Changes Summary
- Files changed: [N]
- Insertions: [N]
- Deletions: [N]
- First-time modified files: [list]

### Risk Analysis
| Area | Risk Level | Description |
|------|-----------|-------------|
| Regression | 🟢 Low / 🟡 Medium / 🔴 High | [assessment] |
| Breaking Changes | 🟢 Low / 🟡 Medium / 🔴 High | [assessment] |
| Side Effects | 🟢 Low / 🟡 Medium / 🔴 High | [assessment] |
| Edge Cases | 🟢 Low / 🟡 Medium / 🔴 High | [assessment] |

### Key Findings
1. **[CRITICAL/MAJOR/MINOR/INFO]** [Finding] → [Recommendation]
2. **[CRITICAL/MAJOR/MINOR/INFO]** [Finding] → [Recommendation]

### Rollback Plan
- **Rollback strategy**: [revert commit / feature flag toggle / database migration revert]
- **Deploy order**: [what goes first, what depends on what]
- **Verification steps**: [specific metrics/logs to check after deploy]

### Post-Deploy Monitoring
- [Specific metrics, logs, or dashboards to watch for 30 min post-deploy]
```

## Severity Levels

| Level | Label | Action Required |
|-------|-------|----------------|
| P0 - CRITICAL | 🚨 | Blocking — must fix before deploy |
| P1 - MAJOR | 🔴 | Strongly recommended to fix |
| P2 - MINOR | 🟡 | Note for future improvement |
| P3 - INFO | ⚪ | Observable behavior change to verify post-deploy |

## Cross-References

This skill is part of the Open Code system:
- **Orchestrator**: `skills/open-code/SKILL.md` — runs this as Stage 3
- **Previous stage**: `skills/code-optimization/SKILL.md` — security/performance findings feed into risk analysis
- **Previous stage**: `skills/typescript-code-review/SKILL.md` — TS-specific findings feed into risk analysis
- **Verification layer**: `skills/deepseek-reasoning-review/SKILL.md` — final reasoning pass over deployment decision

## Principles

- **Be conservative**: When uncertain, flag it. Better to over-flag than ship a regression
- **Be specific**: Reference exact file:line, not vague areas
- **Be actionable**: Every finding should have a clear recommendation
- **Pre-validation first**: Don't review unsafe code — block early if tests/lint fail
- **Context-aware**: A change to a rarely-touched utility is higher risk than a routine feature commit
- **Rollback-ready**: Every deploy should have a clear one-step undo
