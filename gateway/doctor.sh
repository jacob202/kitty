#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/kitty_gateway/openwebui.env"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ENV_FILE}"
  set +a
fi

OPENWEBUI_VENV="${OPENWEBUI_VENV:-${HOME}/kitty-services/venv}"
PYTHON_BIN="${OPENWEBUI_VENV}/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

exec "${PYTHON_BIN}" "${ROOT_DIR}/gateway/doctor.py" "$@"
