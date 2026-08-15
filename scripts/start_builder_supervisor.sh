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
cd "${REPO_ROOT}"

usage() {
  echo "usage: start_builder_supervisor.sh {tick|status|launchd}" >&2
  exit 2
}

command_name="${1:-}"
shift || true

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
