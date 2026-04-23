---
name: code-cleanup
description: Clean up code for production readiness — remove debug artifacts, format, fix imports, lint, and optimize comments. Use when asked to clean, format, or polish code.
---

## Purpose

Systematically clean code for production readiness: remove debugging artifacts, fix formatting, optimize imports, resolve lint issues, and improve comments.

## When to Activate

Invoke this skill when the user asks you to:
- "Clean up this code"
- "Format this file/project"
- "Remove debug code"
- "Fix linting issues"
- "Polish the code"
- "Prepare for PR/production"
- "Run cleanup"
- "Tidy up" or "organize imports"
- "Remove commented code" or "clean up comments"

Also activated automatically as Stage 1 of the Open Code pipeline (`skills/open-code/SKILL.md`).

## Cleanup Process

### Step 1: Analyze Scope

- If user specified files/directories → focus there
- If not → check `git status` for modified files, or inspect recent changes
- Identify file types and applicable cleanup operations
- **Pre-flight check**: Verify required tools are available before starting
- **Subagent dispatch**: If the scope covers 20+ files or 5+ directories, dispatch parallel subagents — one per directory or language — to run cleanup independently, then reconcile results

```bash
# Check which cleanup tools are available
LANGUAGES=""
which ruff 2>/dev/null && LANGUAGES="$LANGUAGES python"
which gofmt 2>/dev/null && LANGUAGES="$LANGUAGES go"
which rustfmt 2>/dev/null && LANGUAGES="$LANGUAGES rust"
which prettier 2>/dev/null && LANGUAGES="$LANGUAGES js/ts"
command -v npx 2>/dev/null >/dev/null && echo "npx available (prettier, eslint)"
```

- **Safety checkpoint**: Create a restore point before making changes

```bash
# If in a git repo, verify clean state to enable undo
git status --porcelain 2>/dev/null | head -5
# If no git repo or user wants safety, suggest:
# cp -r project/ project.backup/
```

- Capture baseline metrics before cleanup (for delta reporting):

```bash
# Count debug artifacts before cleanup
DEBUG_BEFORE=$(grep -rn 'console\.\(log\|debug\)\|print(\|fmt\.Print\|println!\|dbg!' --include='*.{py,js,ts,go,rs}' . 2>/dev/null | wc -l | tr -d ' ')

# Count import statements (language-dependent heuristic)
IMPORTS_BEFORE=$(grep -rn 'import\|from\|require' --include='*.{py,js,ts,go,rs}' . 2>/dev/null | wc -l | tr -d ' ')

# Count TODO/FIXME markers
TODOS_BEFORE=$(grep -rn 'TODO\|FIXME\|HACK\|XXX' --include='*.{py,js,ts,go,rs}' . 2>/dev/null | wc -l | tr -d ' ')

# Count hardcoded secrets (baseline for security cleanup)
SECRETS_BEFORE=$(grep -rn 'password\s*=\|api_key\s*=\|secret\s*=\|token\s*=' --include='*.{py,js,ts,go,rs}' . 2>/dev/null | grep -v 'os\.\|env\|\.env\|config' | wc -l | tr -d ' ')
```

### Step 2: Remove Debug Code

Use language-specific grep patterns to find debug artifacts:

**Python**:
```bash
# Print/debug statements
grep -rn '^\s*print(' --include='*.py'
grep -rn '^\s*logging\.(debug|info)(' --include='*.py'
grep -rn 'import pdb; pdb.set_trace()' --include='*.py'
grep -rn 'breakpoint()' --include='*.py'
```

**JavaScript/TypeScript**:
```bash
# Console statements
grep -rn 'console\.\(log\|debug\|warn\|error\|info\)' --include='*.{js,ts,jsx,tsx}'
grep -rn 'debugger' --include='*.{js,ts,jsx,tsx}'
```

**Go**:
```bash
grep -rn 'fmt\.Print\(ln\)\?' --include='*.go'
grep -rn 'log\.\(Print\|Printf\|Println\)' --include='*.go'
grep -rn 'spew\.Dump\|pp\.Printf' --include='*.go'
```

**Rust**:
```bash
grep -rn 'println!\|dbg!\|eprintln!' --include='*.rs'
```

**Commented-out code** (all languages):
```bash
# Find commented code blocks (3+ consecutive commented lines)
# Matches Python, JS/TS, Go, Rust comment styles
python3 -c "
import re, sys, glob
for ext in ['*.py', '*.js', '*.ts', '*.go', '*.rs']:
    for f in glob.glob('**/' + ext, recursive=True):
        lines = open(f).readlines()
        in_block = 0
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('*'):
                in_block += 1
            else:
                if in_block >= 3:
                    print(f'{f}:{i-in_block}-{i-1} ({in_block} commented lines)')
                in_block = 0
        if in_block >= 3:
            print(f'{f}:{len(lines)-in_block+1}-{len(lines)} ({in_block} commented lines)')
" 2>/dev/null
```

**Alternative** (simpler, no Python dependency):
```bash
# Single-line commented code detection (less accurate but works without Python)
grep -rn -B2 -A2 '^[[:space:]]*//\|^[[:space:]]*#' --include='*.{py,js,ts,go,rs}' 2>/dev/null | grep -B2 -A2 '^[[:space:]]*//\|^[[:space:]]*#' | grep -E '^[^:]+:[0-9]+:' | sort -u
```

**Stale TODO/FIXME**:
```bash
# Review these — remove if stale, keep if actionable
# Staleness indicators:
# - References functions/variables that no longer exist (check grep for those names)
# - More than 6 months old (check git blame) — strongly consider removing
# - More than 30 days with no associated issue/ticket number — flag for review
# - Describes behavior that matches current implementation (already done)
# - Linter ignores that suppress rules no longer applicable (check ESLint/ruff version compat)
# Threshold: 3+ stale TODOs with no ticket reference → batch remove
grep -rn 'TODO\|FIXME\|HACK\|XXX\|WORKAROUND\|STALE\|HACKFIX' --include='*.{py,js,ts,go,rs}'
```

**Remove** each instance unless it contains valuable documentation. For commented-out code blocks, preserve only blocks that explain *why* a decision was made (not *how* the code works).

**Safety rule**: Before removing any code (commented or otherwise), check git blame to see who wrote it and when. If the commit is recent (< 30 days), verify with the author before removing — it may be in-progress work that was temporarily commented out.

### Step 3: Fix Formatting

Check for `.editorconfig` first and respect its rules. Then run formatters based on detected language:

| Language | Formatter | Command |
|----------|-----------|---------|
| Python | ruff | `ruff format [files]` |
| Python (alt) | black | `black [files]` |
| JavaScript/TypeScript | prettier | `npx prettier --write [files]` |
| Go | gofmt | `gofmt -w [files]` |
| Rust | rustfmt | `rustfmt [files]` |
| Ruby | rubocop | `rubocop -a [files]` |
| Java | google-java-format | `google-java-format -i [files]` |
| HTML/CSS/Sass | prettier | `npx prettier --write [files]` |
| YAML/TOML | prettier/yq | `npx prettier --write [files]` / `yq -i [files]` |
| Markdown | prettier | `npx prettier --write [files]` |
| Dockerfile | hadolint | `hadolint [files]` |

If no formatter is available:
- Apply consistent indentation (check `.editorconfig` first, then default to 4-space)
- Standardize quotes (single for JS/TS, double for Go/Python per PEP 8)
- Normalize trailing commas per project convention
- Trim trailing whitespace: `sed -i '' 's/[[:space:]]*$//' [files]`
- Ensure single trailing newline at EOF

### Step 4: Optimize Imports

**Python**:
```bash
# Sort and clean imports
ruff check --select I --fix [files]   # if ruff available
isort [files]                         # alt
autoflake --remove-all-unused-imports -i [files]
```

**JavaScript/TypeScript**:
```bash
npx eslint --fix --rule 'unused-imports/no-unused-imports: error' [files]
```

**Go**:
```bash
goimports -w [files]
```

**General rules**:
- Sort order: stdlib → third-party → local/project
- No unused imports (remove them)
- No duplicate imports from the same module
- Use project-standard import style (check 2-3 existing files)

### Step 5: Remove Hardcoded Secrets

Detect and flag hardcoded credentials, API keys, tokens, and other secrets that should be managed via environment variables or a secrets manager:

```bash
# Generic secret patterns across all languages
# Exclude known safe references (os.environ, config files, etc.)
grep -rn 'password\s*=\|api_key\s*=\|secret\s*=\|token\s*=\|credential\|auth.*key\|SECRET_KEY\|DATABASE_URL' \
  --include='*.{py,js,ts,go,rs,yaml,yml,toml,json,env}' . 2>/dev/null | \
  grep -v 'os\.environ\|os\.getenv\|\.env\|\.git\|node_modules\|__pycache__'

# Python config files with hardcoded values
for f in settings.py config.py app.py; do
  [ -f "$f" ] && grep -n '=\s*["'"'"'][A-Za-z0-9_!@#$%^&*()]' "$f" | grep -v 'os\.' | head -20
done

# Check .env.example for documented vars that are missing from .env
if [ -f .env.example ] && [ -f .env ]; then
  echo "Missing from .env:"
  grep -o '^[A-Z_]*=' .env.example | sed 's/=$//' | while read var; do
    grep -q "^$var=" .env || echo "  - $var"
  done
fi
```

**Action**: Replace any hardcoded secrets with environment variable lookups (e.g., `os.getenv`, `process.env`, `os.Environ`). Flag items for the user to rotate compromised credentials.

### Step 6: Clean Build Artifacts

Remove generated files and build artifacts that shouldn't be committed:

```bash
# Python
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
find . -name '*.pyc' -o -name '*.pyo' -delete 2>/dev/null
find . -name '.mypy_cache' -o -name '.pytest_cache' -type d -exec rm -rf {} + 2>/dev/null

# JavaScript/Node
find . -name 'node_modules' -type d -prune 2>/dev/null  # Flag presence, don't delete
find . -name 'dist' -type d -prune 2>/dev/null           # Check if dist/ is in .gitignore
find . -name '.next' -o -name '.nuxt' -type d -prune 2>/dev/null

# macOS artifacts
find . -name '.DS_Store' -delete 2>/dev/null
find . -name '*.swp' -o -name '*.swo' -delete 2>/dev/null

# Logs & coverage
find . -name '*.log' -type f -delete 2>/dev/null
find . -name '.coverage' -o -name 'coverage' -type d -exec rm -rf {} + 2>/dev/null
find . -name 'htmlcov' -type d -exec rm -rf {} + 2>/dev/null
```

**Check .gitignore**: After cleaning, verify common artifact patterns are listed in `.gitignore`. If missing, suggest adding them.

### Step 7: Fix Lint Issues

Run linter based on language:

| Language | Linter | Command |
|----------|--------|---------|
| Python | ruff | `ruff check --fix [files]` |
| JavaScript/TypeScript | eslint | `npx eslint --fix [files]` |
| Go | golangci-lint | `golangci-lint run [files]` |
| Rust | clippy | `cargo clippy -- -D warnings [files]` |
| Ruby | rubocop | `rubocop -a [files]` |

After auto-fix, review remaining warnings and report anything that needs manual attention.

### Step 8: Improve Comments

Remove redundant comments — these add noise without value:
```python
# Bad: states the obvious
i += 1  # Increment i
x = get_user()  # Get the user

# Good: explains why
i += 1  # Skip the header row (index 0)
```

Improve unclear or misleading comments — if reading the code and comment gives different mental models, fix the comment.

Add docstrings for public APIs if missing (concisely — one line summary + one line details if needed).

Remove commented-out code (see Step 2).

### Step 9: Measure Delta

After cleanup, re-count metrics and compute improvement:

```bash
DEBUG_AFTER=$(grep -rn 'console\.\(log\|debug\)\|print(\|fmt\.Print\|println!\|dbg!' --include='*.{py,js,ts,go,rs}' . 2>/dev/null | wc -l | tr -d ' ')
IMPORTS_AFTER=$(grep -rn 'import\|from\|require' --include='*.{py,js,ts,go,rs}' . 2>/dev/null | wc -l | tr -d ' ')
echo "📊 Debug artifacts: $DEBUG_BEFORE → $DEBUG_AFTER ($((DEBUG_BEFORE - DEBUG_AFTER)) removed)"
echo "📊 Import statements: $IMPORTS_BEFORE → $IMPORTS_AFTER"
```

### Step 10: Present Results

```
## 📋 Cleanup Results

### Files Processed
- [list of files changed]

### Actions Taken
- Debug code removed: [count]
- Files formatted: [count]
- Unused imports removed: [count]
- Lint issues fixed: [count]
- Comments improved: [count]

### Summary
| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Debug artifacts | ${DEBUG_BEFORE} | ${DEBUG_AFTER} | -${delta} |
| Import statements | ${IMPORTS_BEFORE} | ${IMPORTS_AFTER} | -${delta} |
| TODO/FIXME markers | ${TODOS_BEFORE} | reviewed | see manual |

### ⚠️ Manual Actions Needed
- [issues requiring human intervention]

### ✅ Summary
[Overall quality delta — e.g., "12 issues fixed across 5 files, 2 remaining items need manual review"]
```

### Step 11: Validate Cleanup

After all cleanup steps, verify the codebase is still valid:

```bash
# Python: check syntax
for f in $(find . -name '*.py' -type f); do
  python3 -c "compile(open('$f').read(), '$f', 'exec')" 2>/dev/null || echo "❌ Syntax error: $f"
done

# JavaScript/TypeScript: parse check
npx tsc --noEmit 2>/dev/null || echo "⚠️ TypeScript errors (may be pre-existing)"

# General: check no files were deleted unintentionally
# (compare file list if baseline was captured)
```

If any syntax errors are found, revert the affected file and report what went wrong.

## Principles

- **Production ready**: No debug artifacts, no dead code, no commented-out code
- **Consistent style**: Match project conventions exactly (check existing files first)
- **Minimal diffs**: Don't reformat entire files if the user asked for targeted cleanup
- **Preserve intent**: Don't remove comments that explain *why* even if they seem obvious to you
- **Don't break things**: Focus on safe, automated cleanup. Suggest manual fixes for risky changes
- **Idempotent**: Running cleanup twice should result in no additional changes

## Cross-References

This skill is part of the Open Code system:
- **Orchestrator**: `skills/open-code/SKILL.md` — runs this as Stage 1
- **Next stage**: `skills/code-optimization/SKILL.md` — analyzes code after cleanup
- **Execution tool**: `skills/ai-app-improvement-loop/SKILL.md` — uses this skill during Step 5 (Implement)

## CI Integration (Optional)

For teams using pre-commit hooks or CI pipelines, add these cleanup checks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.0.0
    hooks:
      - id: black
  - repo: https://github.com/pycqa/isort
    rev: 5.13.0
    hooks:
      - id: isort
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.1.0
    hooks:
      - id: prettier
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: debug-statements
```

```bash
# GitHub Actions — cleanup validation
# .github/workflows/cleanup-check.yml
name: Cleanup Check
on: [pull_request]
jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          echo "Checking for debug artifacts..."
          ! grep -rn 'console\.\(log\|debug\)\|debugger\|pdb\.set_trace\|breakpoint()' --include='*.{py,js,ts,jsx,tsx}' .
          echo "✅ No debug artifacts found"
```
