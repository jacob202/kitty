# ENGINEERING_LOOP.md
# Chained workflow: diagnose → audit → improve → ship
# Usage: grep "# STEP" this file

# QUICK COMMANDS (no LLM)
./kitty quick status|test|health|index <pattern>
venv/bin/python -m pytest tests/ -q --tb=short

# STEP 1: DIAGNOSE (Matt Pocock style)
# Problem: something is broken
# 1. reproduce - get exact error
# 2. minimise - smallest repro
# 3. hypothesise - root cause
# 4. instrument - add logging
# 5. fix - apply fix
# 6. regression-test - run tests
# Command: grep error .kitty.log && pytest

# STEP 2: AUDIT (SKILL 3)
# Problem: codebase needs review  
# 1. inspect - files, logs, dependencies
# 2. audit - architecture, retrieval, docs
# 3. score - rate aspects 1-10
# 4. report - create IMPROVEMENT_AUDIT.md
# 1. run: mkdir -p docs && echo "# IMPROVEMENT_AUDIT.md" 

# STEP 3: IMPROVE (SKILL 3)
# Problem: need to scale/fix
# 1. refactor plan - REFACTOR_PLAN.md
# 2. process - PROCESS_UPGRADES.md
# 3. validate - tests still pass
# run: docs/REFACTOR_PLAN.md exists

# STEP 4: SHIP (SKILL 1: Build?)
# 1. tests pass
# 2. commit
# 3. document in handoff
# run: git commit -m "FIX: description"

# CHAIN EXAMPLE
# diagnose (error) → audit (why broken) → improve (fix root cause) → ship (commit)

# DOCS TO CHECK
# MASTER_INDEX.md - fast paths
# docs/IMPROVEMENT_AUDIT.md - scores
# docs/DATA_ROUTING.md - storage

# NEW AGENT START
# 1. Read STANDUP.md
# 2. Read MASTER_INDEX.md  
# 3. ./kitty quick test (verify baseline)
# 4. Do work
# 5. Test
# 6. Commit with description

# DON'T
# ❌ retry 3x without summary
# ❌ rewrite entire files
# ❌ add features during stabilization
# ❌ ignore test failures

# WORKFLOW SUMMARY
# Problem → diagnose → audit → improve → ship → handoff