#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/bin/python3.12}"

"${PYTHON_BIN}" -m py_compile scripts/builder_intake.py scripts/check_file_governance.py scripts/context_pack_generator.py scripts/kitty_builder.py scripts/plan_workspace_separation.py src/utils/security_scanner.py src/observability/evals_dashboard.py
"${PYTHON_BIN}" scripts/check_file_governance.py --dry-run
"${PYTHON_BIN}" -m pytest tests/test_builder_intake.py tests/test_file_governance.py tests/test_context_pack_generator.py tests/test_kitty_builder.py tests/test_security_scanner.py tests/test_evals_dashboard.py tests/test_workspace_separation_plan.py -q --tb=short
