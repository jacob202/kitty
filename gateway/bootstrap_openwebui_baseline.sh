#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
cd "${ROOT_DIR}"

echo "Starting stack..."
bash kitty_gateway/start_all.sh

echo "Syncing integrations..."
bash kitty_gateway/sync_openwebui_integrations.sh

echo "Importing curated functions..."
bash kitty_gateway/import_openwebui_functions.sh

echo "Creating DB backup checkpoint..."
bash kitty_gateway/backup_openwebui_state.sh

echo "Running restore smoke..."
bash kitty_gateway/verify_openwebui_backup_restore.sh

echo "Running doctor check..."
bash kitty_gateway/doctor.sh

echo "Baseline bootstrap complete."
