#!/usr/bin/env bash
# Weekly — verify kitty.db migrations are idempotent and in sync.
set -euo pipefail

KITTY="$HOME/Projects/kitty"
OUT="$KITTY/docs/migration-health.md"
DATE=$(date "+%Y-%m-%d")
PYTHON="python3.12"

cd "$KITTY"

# Run migrations against test DB twice — second run must be a no-op
TMPDB=$(mktemp /tmp/kitty-migration-audit-XXXXXX.db)
trap "rm -f $TMPDB" EXIT

STATUS="PASS"
NOTES=()

run_migrate() {
  $PYTHON -c "
import sys; sys.path.insert(0, '.')
from gateway.db import migrate
from pathlib import Path
migrate(db_file=Path('$TMPDB'))
" 2>&1
}

if ! run_migrate > /tmp/migrate-run1.txt 2>&1; then STATUS="FAIL"; NOTES+=("First migration run failed — see /tmp/migrate-run1.txt"); fi
if ! run_migrate > /tmp/migrate-run2.txt 2>&1; then STATUS="FAIL"; NOTES+=("Second migration run failed"); fi

# Check idempotency: second run should apply 0 new migrations
SECOND_NEW=$(grep -cE "Applying|applied" /tmp/migrate-run2.txt 2>/dev/null || true)
SECOND_NEW=${SECOND_NEW:-0}
if [[ "$SECOND_NEW" -gt 0 ]]; then STATUS="WARN"; NOTES+=("Second run applied ${SECOND_NEW} migration(s) — not idempotent"); fi

# Check schema_migrations matches files
DB_MIGRATIONS=$(sqlite3 "$TMPDB" "SELECT COUNT(*) FROM schema_migrations;" 2>/dev/null) || DB_MIGRATIONS="?"
FILE_MIGRATIONS=$(find "$KITTY/gateway/migrations/" -name "*.sql" 2>/dev/null | wc -l | tr -d ' ')
if [[ "$DB_MIGRATIONS" != "$FILE_MIGRATIONS" ]]; then STATUS="WARN"; NOTES+=("DB has $DB_MIGRATIONS migrations, files have $FILE_MIGRATIONS"); fi

{
  echo "# Migration Health — $DATE"
  echo ""
  echo "**Status:** $STATUS"
  echo "**Migrations in DB:** $DB_MIGRATIONS"
  echo "**Migration files:** $FILE_MIGRATIONS"
  echo ""
  if [[ ${#NOTES[@]} -gt 0 ]]; then
    echo "## Issues"
    for n in "${NOTES[@]}"; do echo "- $n"; done
  else
    echo "All checks passed. Migrations are idempotent and in sync."
  fi
} > "$OUT"

echo "[migration-audit] $STATUS → $OUT"
