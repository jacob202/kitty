#!/usr/bin/env bash
# Fixed diagnostic sweep for the /provider-credit-debugging skill.
# Diagnosis order and judgment calls stay in SKILL.md; this just runs
# the checks that never change. Usage: provider_credit_checks.sh [--since YYYY-MM-DD]
set -euo pipefail
cd "$(dirname "$0")/.."

# This sweep is three files on an interpreter the repository does not provision,
# so it opts out of the global addopts rather than requiring pytest-xdist there.
/opt/homebrew/bin/python3.12 -m pytest tests/test_agentrouter_config.py tests/test_llm_routing.py tests/test_token_spend_report.py -q --tb=short -o addopts="--strict-markers"
python3 scripts/spend_report.py "$@"
python3 scripts/spend_report.py --provider agentrouter --credits 150 "$@"
