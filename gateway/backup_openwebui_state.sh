#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
ENV_FILE="${ROOT_DIR}/kitty_gateway/openwebui.env"
STAMP="$(date +%Y%m%d-%H%M%S)"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ENV_FILE}"
  set +a
fi

OPENWEBUI_DATA_DIR="${OPENWEBUI_DATA_DIR:-${HOME}/kitty-services/open-webui-data}"
SRC_DB="${OPENWEBUI_DATA_DIR}/webui.db"
BACKUP_DIR="${ROOT_DIR}/data/openwebui/backups"
mkdir -p "${BACKUP_DIR}"

if [[ ! -f "${SRC_DB}" ]]; then
  echo "OpenWebUI DB not found: ${SRC_DB}"
  exit 1
fi

cp "${SRC_DB}" "${BACKUP_DIR}/webui-${STAMP}.db"
echo "Backup written: ${BACKUP_DIR}/webui-${STAMP}.db"
