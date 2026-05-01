#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/bin/python3.12}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  if [[ -x "${PWD}/${PYTHON_BIN}" ]]; then
    PYTHON_BIN="${PWD}/${PYTHON_BIN}"
  elif [[ -x "/opt/homebrew/bin/python3.12" ]]; then
    PYTHON_BIN="/opt/homebrew/bin/python3.12"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "Python interpreter not found. Set PYTHON_BIN to an executable path." >&2
    exit 2
  fi
fi

# Syntax gate for Bash scripts touched in runtime/control lanes.
bash -n autolaunch.sh kittybuilder scripts/*.sh

"${PYTHON_BIN}" -m py_compile scripts/builder_intake.py scripts/check_agent_coordination.py scripts/check_file_governance.py scripts/context_pack_generator.py scripts/kitty_builder.py scripts/plan_workspace_separation.py scripts/copy_workspace_separation.py src/utils/security_scanner.py src/observability/evals_dashboard.py
"${PYTHON_BIN}" scripts/check_file_governance.py --dry-run
"${PYTHON_BIN}" scripts/check_agent_coordination.py
"${PYTHON_BIN}" -m pytest tests/test_builder_intake.py tests/test_file_governance.py tests/test_context_pack_generator.py tests/test_kitty_builder.py tests/test_security_scanner.py tests/test_evals_dashboard.py tests/test_workspace_separation_plan.py tests/test_copy_workspace_separation.py -q --tb=short
