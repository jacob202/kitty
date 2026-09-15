#!/usr/bin/env bash
set -euo pipefail

# KittyBuilder autonomous supervisor launcher.
#
# Fixed surface, fixed arguments. This script is the only entry point the
# launchd service may use; it exposes exactly three subcommands:
#
#   tick     run one supervisor tick (one OS lock, deterministic selection of
#            eligible active initiatives, at most two canonical runs)
#   status   read-only supervisor projection
#   launchd  print the launchd plist XML to stdout (never installs anything)
#
# The launchd plist itself is rendered by gateway/builder_supervisor.py with
# RunAtLoad, StartInterval 900, no KeepAlive, a fixed login-safe PATH, the
# canonical repo root as WorkingDirectory, and fixed logs under logs/builder/.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON="${KITTYBUILDER_PYTHON:-${REPO_ROOT}/venv/bin/python}"

if [[ "${PYTHON}" == */* ]]; then
  [[ -x "${PYTHON}" ]] || { echo "error: supervisor Python is not executable: ${PYTHON}" >&2; exit 1; }
elif ! command -v "${PYTHON}" >/dev/null 2>&1; then
  echo "error: supervisor Python not found on PATH: ${PYTHON}" >&2
  exit 1
fi

# The dedicated autonomy runtime deliberately contains no secrets. Reuse the
# canonical Kitty dotenv through the same safe loader used by Gateway/LiteLLM
# so paid OpenRouter children receive credentials without copying keys into the
# runtime worktree, launchd plist, or OpenCode credential store.
ENV_ROOT="${KITTY_BUILDER_REPO_ROOT:-${REPO_ROOT}}"
usage() {
  echo "usage: start_builder_supervisor.sh {tick|status|launchd}" >&2
  exit 2
}

command_name="${1:-}"
shift || true

case "${command_name}" in
  tick|status|launchd)
    ;;
  *)
    usage
    ;;
esac

# load_env_safe.sh parses the dotenv with ${PYTHON_BIN} and returns its parser
# status directly. The canonical launchd plist carries only PATH by design (no
# secrets, no env passthrough), so PYTHON_BIN must come from here.
export PYTHON_BIN="${PYTHON}"
source "${REPO_ROOT}/gateway/lib/load_env_safe.sh"
if ! load_env_assignments "${ENV_ROOT}/.env"; then
  echo "error: could not load ${ENV_ROOT}/.env (PYTHON_BIN=${PYTHON_BIN})" >&2
  exit 1
fi

# Only a paid tick requires an OpenRouter key. Read-only status and the explicit
# free route remain usable without paid credentials.
if [[ "${command_name}" == "tick" ]]; then
  supervisor_route="${KITTY_BUILDER_SUPERVISOR_ROUTE:-cheap}"
  if [[ "${supervisor_route}" != "free" && -z "${OPENROUTER_API_KEY:-}" ]]; then
    echo "error: paid supervisor tick requires OPENROUTER_API_KEY" >&2
    exit 1
  fi
fi

cd "${REPO_ROOT}"

case "${command_name}" in
  tick)
    exec "${PYTHON}" -m gateway.builder_cli supervisor tick "$@"
    ;;
  status)
    exec "${PYTHON}" -m gateway.builder_cli supervisor status "$@"
    ;;
  launchd)
    exec "${PYTHON}" -m gateway.builder_supervisor launchd-plist "$@"
    ;;
  *)
    usage
    ;;
esac
