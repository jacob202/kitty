---
name: open-code
description: Master orchestrator for the Open Code quality system — pipelines code cleanup, optimization, deployment safety review, and reasoning verification into one workflow.
---

## Purpose

Orchestrates the complete Open Code quality pipeline across all four sub-skills. Detects language, determines scope, runs each stage in order, and produces a unified report. Use this skill when the user asks for any code quality, review, cleanup, optimization, or deployment safety check.

## When to Activate

Invoke this skill when the user asks to:
- "Run Open Code"
- "Full code review"
- "Quality check"
- "Prepare for deployment"
- Any request that maps to one or more sub-skills

## Open Code Pipeline

### Stage 0: Scope & Language Detection

Determine scope and detect languages:

```
SCOPE=$(git diff --name-only HEAD~1 2>/dev/null || git status --porcelain | cut -c4-)
FILES=$(echo "$SCOPE" | tr '\n' ' ')
```

Detect language by extension:
- `.py` → Python
- `.js`, `.ts`, `.jsx`, `.tsx` → JavaScript/TypeScript
- `.go` → Go
- `.rs` → Rust
- `.rb` → Ruby
- `.java`, `.kt` → JVM
- `.mod`, `.sum` → Go modules

### Stage 1: Code Cleanup

If cleanup requested, delegate to `skills/code-cleanup/SKILL.md`:

1. Remove debug code using language-specific grep patterns
2. Run formatter (ruff/prettier/gofmt/rustfmt)
3. Optimize imports
4. Run linter
5. Clean up comments

### Stage 2: Code Optimization

If optimization requested, delegate to `skills/code-optimization/SKILL.md`:

1. Scan for performance anti-patterns
2. Scan for security vulnerabilities
3. Scan for error handling gaps
4. Scan for edge cases
5. Prioritize findings

### Stage 2.5: Language-Specific Deep Review (TypeScript only)

If the project is TypeScript, run the full 300+ checkpoint review from `skills/typescript-code-review/SKILL.md`:

- Type system analysis (all `any`, `as`, `!` violations)
- Null/undefined safety
- Error handling completeness
- Security vulnerability scan
- Performance bottleneck analysis
- Dead code detection
- Architectural SOLID violations
- Dependency health audit
- Testing gap analysis

### Stage 3: Deployment Safety Review

If deployment review requested, delegate to `skills/deployment-safety-review/SKILL.md`:

1. Run pre-validation (lint + tests)
2. Analyze diff for regression risk
3. Check for breaking changes
4. Identify side effects
5. Assess edge cases

### Stage 4: Reasoning Verification

If complex changes were made, delegate to `skills/deepseek-reasoning-review/SKILL.md`:

1. Feed the diff and findings to the reasoning model
2. Fix CRITICAL/MAJOR issues
3. Iterate until clean

## Unified Report Template

Present a combined report when running multiple stages:

```
## 🔷 Open Code Quality Report

### Scope
- Files: [list]
- Languages: [detected]

### Stage 1: Cleanup
- Debug artifacts removed: [count]
- Files formatted: [count]
- Imports cleaned: [count]
- Lint issues fixed: [count]

### Stage 2: Optimization
- ⚡ Performance: [critical/major/minor count]
- 🔒 Security: [critical/major/minor count]
- ⚠️ Edge Cases: [count]

### Stage 3: Deployment Safety
- Verdict: ✅ SAFE / ⚠️ CAUTION / ❌ UNSAFE
- Regression Risk: 🟢/🟡/🔴
- Breaking Changes: 🟢/🟡/🔴
- Side Effects: 🟢/🟡/🔴

### Stage 4: Reasoning Review
- Status: ✅ PASS / ⚠️ ISSUES FOUND / ❌ FAIL
- Items reviewed: [count]

### 🔴 Must Fix Before Proceeding
1. [item]

### 🟡 Should Fix
1. [item]

### ✅ Summary
[Pass/fail and overall quality assessment]
```

## Skill Inventory

The Open Code system includes all 10 sub-skills:

| # | Skill | Purpose | Auto-Activation |
|---|-------|---------|----------------|
| 1 | `code-cleanup` | Remove debug code, format, fix imports, lint, improve comments | Stage 1 — always |
| 2 | `code-optimization` | Performance, security, error handling, edge case analysis | Stage 2 — always |
| 3 | `deployment-safety-review` | Pre-deployment regression/breaking change/side-effect analysis | Stage 3 — on deploy |
| 4 | `deepseek-reasoning-review` | Critical review of correctness, completeness, and security | Stage 4 — complex changes |
| 5 | `typescript-code-review` | 300+ checkpoint TypeScript-specific code review (type safety, security, perf, architecture, dependencies, testing, config, docs, edge cases) | Stage 2.5 — TypeScript projects |
| 6 | `ai-app-improvement-loop` | Iterative single-improvement-at-a-time development loop | On "improve" requests |
| 7 | `create-style-guide` | Generate comprehensive STYLE_GUIDE.md for projects (colors, typography, spacing, components) | On "style guide" requests |
| 8 | `visual-web-app-development` | Modern, responsive web application development with UI/UX focus | On "web app" or "UI" requests |
| 9 | `flashcard-study-system` | Flashcard application with spaced repetition, confidence tracking, statistics | On "flashcard" or "study" requests |
| 10 | `technical-documentation` | Plain-language project docs for non-technical founders (FORME.md) | On "document" or "explain" requests |

## Cross-Skill Integration

Skills in the Open Code system reference each other:

| From Skill | References | Purpose of Reference |
|-----------|-----------|---------------------|
| `ai-app-improvement-loop` | `code-cleanup`, `code-optimization` | Execution tools during Step 5 (Implement) |
| `deployment-safety-review` | `code-optimization` | Incorporates security findings from Stage 2 |
| `deepseek-reasoning-review` | All skills | Final verification pass over any skill's output |
| `create-style-guide` | `visual-web-app-development` | Style guide feeds into UI development |
| `technical-documentation` | All skills | Documents the project that other skills analyze |

## Pipeline Routing Logic

```
flowchart TD
    A[User Request] --> B{Detect Intent}
    B -->|Cleanup| C[Stage 1: code-cleanup]
    B -->|Optimize| D[Stage 2: code-optimization]
    B -->|TypeScript| E[Stage 2.5: typescript-code-review]
    B -->|Deploy| F[Stage 3: deployment-safety-review]
    B -->|Review| G[Stage 4: deepseek-reasoning-review]
    B -->|Improve| H[ai-app-improvement-loop]
    B -->|Style Guide| I[create-style-guide]
    B -->|Web App| J[visual-web-app-development]
    B -->|Flashcard| K[flashcard-study-system]
    B -->|Document| L[technical-documentation]
    B -->|General| M[Run full pipeline 1→2→4]
```

## Language Profiles

When a specific language is detected, use these specialized checklists in addition to the general pipeline:

### TypeScript/JavaScript
Use all TypeScript-specific checkpoints from `skills/typescript-code-review/`:
- Type system analysis (any types, assertions, generics)
- Null/undefined handling
- Async/concurrency patterns
- Security vulnerabilities
- Performance analysis
- Architectural patterns (SOLID, design patterns, module structure)
- Dependency health analysis
- Testing gaps
- Configuration quality

### Python
Use Python-specific patterns from `skills/code-optimization/`:
- N+1 queries, sync I/O in async functions
- Bare excepts, missing context managers
- Hardcoded secrets (bandit scanner)

### Go
- Defer in hot loops, missing error handling
- fmt.Sprintf over strings.Builder in hot paths

## Principles

- **Pipeline order matters**: Clean before analyzing, analyze before reviewing safety, verify before delivering
- **Fail fast**: If any stage produces CRITICAL findings, stop the pipeline and fix before continuing
- **Language-aware**: Commands and patterns adapt per detected language
- **Idempotent**: Running the pipeline twice in a row should produce the same result (no changes on second run)
- **Traceable**: Every change should be attributable to a specific finding
