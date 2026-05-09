# PROJECT_REALITY_CHECK.md
# SKILL 1: Project Foundation & Reality Check
# Must run BEFORE any large coding work

# USAGE: Run this first when starting/resuming a project

## STEP 1: ANALYZE CURRENT SITUATION

### Answer these questions first:
- What's the actual project goal?
- Who are target users?
- What features are truly required?
- What's the budget?
- What's the hardware?
- What's the privacy requirement?
- What's the maintenance burden?

## STEP 2: INSPECT EXISTING PROJECT STATE

### Run these commands:
```bash
pwd  # Must show /Users/jacobbrizinski/Projects/kitty
ls -la
cat package.json  # or requirements.txt
cat README.md
ls src/
ls tests/
```

## STEP 3: BUILD UNDERSTANDING DOCS

### Run: create these files
- PROJECT.md - What this project is
- MVP_ROADMAP.md - Minimum viable product  
- CODEBASE_MAP.md - File organization
- KNOWN_ISSUES.md - What's broken
- CURRENT_STATE.md - What works right now

## STEP 4: DEFINE MVP BOUNDARIES

### Ask:
- [ ] Essential features only
- [ ] Future ideas deferred
- [ ] Unnecessary complexity removed
- [ ] Speculative systems parked

## STEP 5: SIMPLIFY ARCHITECTURE

### Prefer:
- local-first
- inspectable systems  
- boring stable tech
- minimal dependencies
- single startup path
- explicit configuration

### Avoid:
- unnecessary agents
- microservices
- orchestration complexity
- framework hopping
- premature scaling

## STEP 6: DEFINE OPERATIONAL RULES

### Before any work:
- [ ] Inspect before editing
- [ ] Minimal diffs
- [ ] Retry limit: 3x then summary
- [ ] Git checkpoint before risky work
- [ ] Source-of-truth discipline
- [ ] Tests must pass

## STARTUP COMMANDS

```bash
# Verify correct project
pwd  # /Users/jacobbrizinski/Projects/kitty

# Check server
./kitty status

# Run tests  
venv/bin/python -m pytest tests/ -q --tb=short

# API check
curl -s http://localhost:5001/api/brief
```

## FOR NEW AGENTS: START HERE

If you're new to this project:
1. Run `./kitty quick status` - server running?
2. Run `venv/bin/python -m pytest tests/ -q --tb=short` - tests pass?
3. Read MASTER_INDEX.md
4. Then read ENGINEERING_LOOP.md for workflow