#!/usr/bin/env bash
set -u

PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/bin/python3.12}"
PROJECT_PATH="."
PORT="5001"
REPORT_PATH=""
SKIP_FULL="0"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_phase4_merge_gate.sh [options]

Options:
  --project <path>   Runtime project path to validate (default: .)
  --port <port>      HTTP port for route smoke checks (default: 5001)
  --report <path>    Output markdown report path (default: docs/PHASE4_MERGE_GATE_RUN_<date>.md)
  --skip-full        Skip full pytest suite (faster local check)
  -h, --help         Show this help

Relative --report paths are anchored to the directory given by --project (see
D-0011 in docs/DECISIONS.md). Absolute paths are unchanged.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      PROJECT_PATH="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --report)
      REPORT_PATH="$2"
      shift 2
      ;;
    --skip-full)
      SKIP_FULL="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${REPORT_PATH}" ]]; then
  report_date="$(date +%F)"
  REPORT_PATH="docs/PHASE4_MERGE_GATE_RUN_${report_date}.md"
fi

project_abs="$(cd "${PROJECT_PATH}" 2>/dev/null && pwd)"
if [[ -z "${project_abs}" ]]; then
  echo "Project path not found: ${PROJECT_PATH}" >&2
  exit 2
fi

# Anchor relative report paths to the validated project (D-0011). Otherwise
# mkdir/write_header follow the shell cwd and the report can be truncated or
# written outside the project.
if [[ "${REPORT_PATH}" != /* ]]; then
  REPORT_PATH="${project_abs}/${REPORT_PATH}"
fi

# Normalize python interpreter so relative values like venv/bin/python do not
# break against copied runtime paths that have no local virtualenv.
if [[ ! -x "${PYTHON_BIN}" ]]; then
  if [[ -x "${project_abs}/${PYTHON_BIN}" ]]; then
    PYTHON_BIN="${project_abs}/${PYTHON_BIN}"
  elif [[ -x "/opt/homebrew/bin/python3.12" ]]; then
    PYTHON_BIN="/opt/homebrew/bin/python3.12"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "Python interpreter not found. Set PYTHON_BIN to an executable path." >&2
    exit 2
  fi
fi

mkdir -p "$(dirname "${REPORT_PATH}")"

if [[ -f "${REPORT_PATH}" ]]; then
  REPORT_PATH="${REPORT_PATH%.md}_$(date +%H%M%S).md"
fi

fail_count=0

write_header() {
  cat > "${REPORT_PATH}" <<EOF
# Phase 4 Merge Gate Run

Date: $(date +%F)
Generated at: $(date +%H:%M:%S)
Runtime path: \`${project_abs}\`
Port: ${PORT}
Status: running

EOF
}

run_step() {
  local label="$1"
  local cmd="$2"

  local output=""
  local exit_code=0

  output="$(
    cd "${project_abs}" && eval "${cmd}" 2>&1
  )" || exit_code=$?

  {
    echo "## ${label}"
    echo
    echo "Command:"
    echo
    echo "\`\`\`bash"
    echo "${cmd}"
    echo "\`\`\`"
    echo
    echo "Exit code: ${exit_code}"
    echo
    echo "\`\`\`text"
    printf "%s\n" "${output}"
    echo "\`\`\`"
    echo
  } >> "${REPORT_PATH}"

  if [[ ${exit_code} -ne 0 ]]; then
    fail_count=$((fail_count + 1))
  fi
}

finalize_report() {
  local final_status="pass"
  if [[ ${fail_count} -ne 0 ]]; then
    final_status="fail"
  fi

  {
    echo "## Summary"
    echo
    echo "- Failure count: ${fail_count}"
    echo "- Final status: ${final_status}"
    echo
  } >> "${REPORT_PATH}"

  perl -0pi -e "s/Status: running/Status: ${final_status}/" "${REPORT_PATH}"
}

write_header

if [[ "${SKIP_FULL}" == "1" ]]; then
  {
    echo "## Full Suite"
    echo
    echo "Skipped via --skip-full"
    echo
  } >> "${REPORT_PATH}"
else
  run_step "Full Suite" "${PYTHON_BIN} -m pytest tests/ -q --tb=short"
fi

run_step "Focused Route Suite" "${PYTHON_BIN} -m pytest tests/test_web_chat_phase1.py tests/test_brief_route.py tests/test_commands_route.py -q --tb=short"
run_step "Launcher Status" "./kitty status"
run_step "Brief Smoke" "curl -fsS --connect-timeout 5 --max-time 20 http://localhost:${PORT}/api/brief"
run_step "Command Smoke" "curl -fsS --connect-timeout 5 --max-time 20 -X POST http://localhost:${PORT}/api/command -H \"Content-Type: application/json\" -d '{\"command\":\"/stuck\"}'"
run_step "Chat Smoke" "curl -fsS --connect-timeout 5 --max-time 20 -X POST http://localhost:${PORT}/api/chat -H \"Content-Type: application/json\" -d '{\"message\":\"phase4 merge gate\",\"domain\":\"chat\"}'"

finalize_report

echo "Report written: ${REPORT_PATH}"
if [[ ${fail_count} -ne 0 ]]; then
  echo "Phase 4 merge gate FAILED (${fail_count} failing step(s))." >&2
  exit 1
fi

echo "Phase 4 merge gate PASSED."
exit 0
