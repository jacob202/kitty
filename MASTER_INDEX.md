# MASTER_INDEX.md
# Fast-parse index - all paths + anchors
# Usage: grep "^#.*<pattern>" this file

# QUICK (no LLM)
# ./kitty quick status|test|health|index <pattern>|tokens

# DOCS
# docs/STANDUP.md - startup + hooks (READ FIRST)
# docs/IMPROVEMENT_AUDIT.md - audit scores, start here
# docs/DATA_ROUTING.md - storage routing (CRITICAL)
# docs/PROCESS_UPGRADES.md - commands workflow
# docs/REFACTOR_PLAN.md - future changes

# WORKFLOW
# ENGINEERING_LOOP.md - diagnose → audit → improve → ship chain

# CONFIG
# config/README.md - all configs indexed
# src/config/validators.py - Pydantic validate

# VERIFY
# venv/bin/python -m pytest tests/ -q --tb=short

# START
# ./kitty
# bash scripts/start-session.sh

# DOC Anchors
# IMPROVEMENT_AUDIT.md#Executive-Summary
# IMPROVEMENT_AUDIT.md#Findings
# DATA_ROUTING.md#Storage-Routing
# DATA_ROUTING.md#Code-References
# PROCESS_UPGRADES.md#Quick-Commands
# ENGINEERING_LOOP.md#STEP-1-DIAGNOSE
# ENGINEERING_LOOP.md#STEP-2-AUDIT