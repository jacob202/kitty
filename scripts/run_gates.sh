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

"${PYTHON_BIN}" -m py_compile scripts/builder_intake.py scripts/build_voice_corpus.py scripts/check_agent_coordination.py scripts/check_continuity_state.py scripts/check_file_governance.py scripts/context_pack_generator.py scripts/kitty_builder.py scripts/plan_workspace_separation.py scripts/copy_workspace_separation.py src/utils/security_scanner.py src/observability/evals_dashboard.py
"${PYTHON_BIN}" scripts/check_file_governance.py --dry-run
"${PYTHON_BIN}" scripts/check_agent_coordination.py
"${PYTHON_BIN}" scripts/check_continuity_state.py --max-age-days 21
"${PYTHON_BIN}" -m pytest tests/test_builder_intake.py tests/test_build_voice_corpus.py tests/test_file_governance.py tests/test_context_pack_generator.py tests/test_kitty_builder.py tests/test_security_scanner.py tests/test_evals_dashboard.py tests/test_run_gates_script.py tests/test_skill_runtime_discovery.py tests/test_check_continuity_state.py -q --tb=short

# Full reliability loop (backend smoke + browser-flow + regression + summary).
# Set RUN_GATES_SKIP_EVAL_LOOP=1 for a faster local-only skip.
if [[ "${RUN_GATES_SKIP_EVAL_LOOP:-0}" != "1" ]]; then
  "${PYTHON_BIN}" scripts/eval_loop.py --max-attempts 1 --offline
fi
