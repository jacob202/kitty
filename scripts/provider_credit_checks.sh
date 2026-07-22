#!/usr/bin/env bash
# Fixed diagnostic sweep for the /provider-credit-debugging skill.
# Diagnosis order and judgment calls stay in SKILL.md; this just runs
# the checks that never change. Usage: provider_credit_checks.sh [--since YYYY-MM-DD]
set -euo pipefail
cd "$(dirname "$0")/.."

/opt/homebrew/bin/python3.12 -m pytest tests/test_agentrouter_config.py tests/test_llm_routing.py tests/test_token_spend_report.py -q --tb=short
python3 scripts/spend_report.py "$@"
python3 scripts/spend_report.py --provider agentrouter --credits 150 "$@"
