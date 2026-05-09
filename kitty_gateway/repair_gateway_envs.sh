#!/bin/bash
set -euo pipefail

OPENWEBUI_VENV="${OPENWEBUI_VENV:-$HOME/kitty-services/venv}"
LITELLM_VENV="${LITELLM_VENV:-$HOME/kitty-services/venv-litellm}"
ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"

echo "Using existing OpenWebUI venv: ${OPENWEBUI_VENV}"
if [[ ! -x "${OPENWEBUI_VENV}/bin/open-webui" ]]; then
  echo "Error: open-webui not found in ${OPENWEBUI_VENV}."
  echo "Install it first, or set OPENWEBUI_VENV to a venv containing open-webui."
  exit 1
fi

echo "Creating/updating LiteLLM venv: ${LITELLM_VENV}"
/opt/homebrew/bin/python3.12 -m venv "${LITELLM_VENV}"
source "${LITELLM_VENV}/bin/activate"
pip install --upgrade pip
pip install --upgrade -r "${ROOT_DIR}/kitty_gateway/requirements.litellm.txt"
deactivate

echo "Done."
echo "OpenWebUI venv: ${OPENWEBUI_VENV}"
echo "LiteLLM venv:  ${LITELLM_VENV}"
