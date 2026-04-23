---
name: technical-documentation
description: "Generate plain-language project documentation (FORME.md) that explains complex technical systems to non-technical stakeholders through analogy, narrative, and structure. Use when asked to document a project, explain architecture, or create a technical overview."
---

## Purpose

Generate a `FORME.md` — a living document that explains an entire project in plain language. Designed for non-technical founders, product owners, and designers who need to deeply understand the technical systems they're responsible for, without reading code.

## When to Activate

Invoke this skill when the user asks to:
- "Document this project"
- "Create a README"
- "Explain the architecture"
- "Write technical documentation"
- "Make a FORME.md"
- "Explain like I built it"
- "Document for non-technical audience"

## Detection

Look for these indicators to auto-activate:
- Request includes "plain language" or "non-technical"
- User says they're a founder, product owner, or designer
- Project lacks documentation or README is minimal
- Complex project with multiple services

## Process

### Step 1: Project Analysis

Before writing, gather comprehensive understanding:

```bash
# Get project structure
ls -la

# Count files by type to understand composition
find . -name '*.py' -not -path './node_modules/*' | wc -l
find . -name '*.{js,ts,jsx,tsx}' -not -path './node_modules/*' | wc -l
find . -name '*.go' | wc -l
find . -name '*.rs' | wc -l

# Identify entry points
ls -la src/main.* src/app.* index.* server.* 2>/dev/null
ls -la package.json pyproject.toml Cargo.toml go.mod 2>/dev/null

# Identify external services (APIs, databases)
grep -rn 'DATABASE_URL\|REDIS_URL\|AWS_\|API_KEY\|SUPABASE\|FIREBASE\|MONGODB\|POSTGRES\|REDIS' --include='*.{env,env.*,yaml,yml,json,toml,conf}' . 2>/dev/null | head -20

# Identify routes/endpoints (web projects)
grep -rn '@app\.route\|@router\.\|app\.get\|app\.post\|router\.get\|router\.post\|app\.api' --include='*.py' . 2>/dev/null | head -30
grep -rn 'router\.\(get\|post\|put\|delete\)\|app\.\(get\|post\)' --include='*.{js,ts}' . 2>/dev/null | head -30

# Identify key dependencies
cat package.json 2>/dev/null | grep '"dependencies"' -A 100 | head -30
cat pyproject.toml 2>/dev/null | grep -A 50 '\[project\]' | head -30
cat Cargo.toml 2>/dev/null | grep -A 30 '\[dependencies\]'

# Check for existing documentation
ls -la README.md CONTRIBUTING.md ARCHITECTURE.md docs/ 2>/dev/null

# Check git history for context
git log --oneline -20 2>/dev/null
```

### Step 2: Interview the Builder

Before writing, ask (or infer from code):

1. **What problem does this solve?** — Read README, commit messages, issue tracker
2. **Who are the users?** — Check for auth flows, user roles, API consumers
3. **What are the core user journeys?** — Trace 2-3 key operations through the codebase
4. **What technologies are used and why?** — Check dependency choices against alternatives
5. **What's clever or unusual?** — Look for unique architecture decisions, custom solutions
6. **What hurts?** — Look for TODO/FIXME/HACK comments, complex workarounds

### Step 3: Generate FORME.md

Write `FORME.md` with these sections:

| Section | Content |
|---------|---------|
| **The Big Picture** | 3-4 sentence executive summary + problem statement + user journey + analogy |
| **Architecture Blueprint** | ASCII diagram (boxes+arrows) + explain each layer like a building tour + why-this-not-that for each decision |
| **Codebase Structure** | Folder tree (top 3 levels) + what lives where + entry points + naming conventions |
| **Data Flow** | 2-3 core user actions traced end-to-end + step-by-step walkthrough + what happens if each step fails |
| **Technology Choices** | Table: Technology / What It Does Here / Why This One / Watch Out For |
| **Key Files** | Table: File / Purpose / When to Open / Risk Level |
| **Deployment & Infrastructure** | How it runs + CI/CD pipeline + environment variables + scaling behavior |
| **Troubleshooting** | Common failures + how to detect + who to call + recovery steps |
| **Glossary** | Every technical term defined in one sentence of plain language |

### Step 4: Validate

```bash
# Check that FORME.md was created
ls -la FORME.md

# Verify all referenced files exist
grep -oP '`[\w/.-]+`' FORME.md | tr -d '`' | while read -r f; do
  [ -f "$f" ] || [ -d "$f" ] || echo "⚠️ Referenced but not found: $f"
done
```

### Step 5: Present Results

```
## 📖 Technical Documentation Created

### File Generated
- `FORME.md` — [N] sections, ~[M] words

### What's Covered
- ✅ Executive summary (plain language)
- ✅ Architecture diagram with layer explanations
- ✅ Codebase folder tour
- ✅ [N] core user journeys traced end-to-end
- ✅ [N] technologies documented with tradeoffs
- ✅ Troubleshooting guide
- ✅ Glossary with [N] terms

### 👥 Audience
Non-technical founders, product owners, designers

### 📋 Review Checklist
- [ ] Ask a non-technical person to read it — do they understand?
- [ ] Verify all technical details with the engineering team
- [ ] Update when architecture changes significantly
```

## Cross-References

This skill is part of the Open Code system:
- **Orchestrator**: `skills/open-code/SKILL.md`
- **Pre-documentation**: `skills/code-cleanup/SKILL.md` — clean code before documenting
- **Style guide**: `skills/create-style-guide/SKILL.md` — reference design decisions
- **Code review**: `skills/typescript-code-review/SKILL.md` — reference findings in architecture decisions

## Principles

- **Analogy-driven**: Every complex concept needs a "think of it like..." analog
- **No jargon without definition**: Every technical term goes in the glossary
- **Traceable**: Every claim should be verifiable in the codebase
- **Failure-aware**: Every flow should describe what happens when it breaks
- **Living document**: FORME.md should be updated with every major architecture change
- **One system, one document**: A single FORME.md is better than scattered docs
