# Spec: Response Quality Critic
## Source Request
Phase 5 — Skills and Quality: Build response quality critic for SOUL-aligned reviews.

## Problem
Kitty needs a way to review complex responses before showing them, checking for directness, padding, validation, scope creep, and SOUL alignment.

## Non-goals
- Do not wire to web.py yet
- Do not auto-update SOUL.md
- Do not use LLM for this (deterministic checks)

## Files Allowed To Change
- src/space_kitty/quality_critic.py
- tests/test_quality_critic.py
- specs/quality-critic.spec.md (this file)
- docs/SOUL_LEARNED_RULES.md (append-only, pending review)

## Files Forbidden To Change
- web.py
- src/api/__init__.py
- src/core/orchestrator.py

## Required Behaviour
- `review_draft(draft, soul_context="") -> dict`: returns {score: int 0-10, flags: list, refined: str}
- `extract_learned_rule(draft, user_correction) -> str`: returns rule for pending review
- Checks: directness, padding, actionable next step, scope creep, validation presence, SOUL alignment
- Score <=4 with flags returns refined draft with "[Critic suggestions: ...]"

## Acceptance Tests
- test_directness_flag: indirect language flagged, score reduced
- test_padding_flag: excessive empty lines flagged
- test_actionable: missing next step flagged
- test_no_scope_creep: scope creep flagged
- test_include_validation: missing validation for code flagged
- test_high_score_for_good_draft: good draft scores >=8
- test_refined_includes_suggestions: refined includes critic suggestions
- test_no_correction: empty rule
- test_with_correction: extracts rule from user correction
- test_rule_format: rule starts with "Rule:"

## Smoke Test
Command:
```bash
python3 -c "from src.space_kitty.quality_critic import review_draft; d=review_draft('Run this. Maybe perhaps.'); print(d['score'], d['flags'])"
```
Expected: score <10, flags non-empty.

## Validation
```bash
python3 -m pytest tests/test_quality_critic.py -q
bash scripts/run_gates.sh
```

## Completion Report Required
- files read: src/space_kitty/quality_critic.py, tests/test_quality_critic.py
- files changed: new files only
- tests passed: 10/10
- gates passed: 65 passed
- docs updated: SESSION_SUMMARY.md, TASKS.md
- known risks: none
- next smallest action: self-correction skill using quality_critic
