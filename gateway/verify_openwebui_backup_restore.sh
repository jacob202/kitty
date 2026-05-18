#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
BACKUP_DIR="${ROOT_DIR}/data/openwebui/backups"
TMP_DIR="${ROOT_DIR}/data/openwebui/restore_smoke"
mkdir -p "${BACKUP_DIR}" "${TMP_DIR}"

latest_backup="$(ls -1t "${BACKUP_DIR}"/webui-*.db 2>/dev/null | head -n1 || true)"
if [[ -z "${latest_backup}" ]]; then
  echo "No backup found in ${BACKUP_DIR}"
  exit 1
fi

stamp="$(date +%Y%m%d-%H%M%S)"
restore_copy="${TMP_DIR}/restore-smoke-${stamp}.db"
cp "${latest_backup}" "${restore_copy}"

integrity="$(sqlite3 "${restore_copy}" "PRAGMA integrity_check;" || true)"
if [[ "${integrity}" != "ok" ]]; then
  echo "SQLite integrity check failed: ${integrity}"
  exit 1
fi

users="$(sqlite3 "${restore_copy}" "select count(*) from user;" || echo 0)"
configs="$(sqlite3 "${restore_copy}" "select count(*) from config;" || echo 0)"

if [[ "${users}" -lt 1 ]]; then
  echo "Restore smoke failed: expected >=1 user, got ${users}"
  exit 1
fi
if [[ "${configs}" -lt 1 ]]; then
  echo "Restore smoke failed: expected >=1 config row, got ${configs}"
  exit 1
fi

echo "Restore smoke PASS"
echo "- source backup: ${latest_backup}"
echo "- restored copy: ${restore_copy}"
echo "- users: ${users}"
echo "- config rows: ${configs}"
