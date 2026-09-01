#!/usr/bin/env bash
# Nightly unattended drain of the active KittyBuilder initiative on free models.
#
# Replaces hand-starting "KittyBuilder free packet worker" sessions — that title
# was 11 of the last 30 OpenCode sessions, every one launched manually.
#
# Deliberately conservative:
#   --free        free DSH/OpenRouter model ladder, $0
#   --gate manual work stops at the gate; nothing auto-publishes or auto-merges
#   --max-runtime hard wall so a wedged run can't burn the night
#   mkdir lock    two drains never overlap (macOS has no flock)
#
# Usage: nightly_packet_drain.sh [initiative-id]   (default: the active one)
set -euo pipefail

REPO="/Users/jacobbrizinski/Projects/kitty"
LOG_DIR="$REPO/data/kittybuilder/drain-logs"
LOCK="/tmp/kitty-packet-drain.lock.d"
MAX_RUNTIME="${MAX_RUNTIME:-5400}"   # 90 min

mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$LOG_DIR/drain-$STAMP.log"

# mkdir is atomic on every POSIX fs; macOS ships no flock.
if ! mkdir "$LOCK" 2>/dev/null; then
  # Reap a lock whose owner died.
  if [[ -f "$LOCK/pid" ]] && ! kill -0 "$(cat "$LOCK/pid" 2>/dev/null)" 2>/dev/null; then
    rm -rf "$LOCK"
    mkdir "$LOCK" 2>/dev/null || { echo "$(date -Iseconds) lock race; exiting" >>"$LOG"; exit 0; }
  else
    echo "$(date -Iseconds) another drain holds the lock; exiting" >>"$LOG"
    exit 0
  fi
fi
echo $$ >"$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT INT TERM

cd "$REPO"

# Pick the initiative: explicit arg, else the single [active] one.
INIT="${1:-}"
if [[ -z "$INIT" ]]; then
  INIT="$(./kitty builder initiative list 2>/dev/null | awk '/\[active\]/{print $1; exit}')"
fi

if [[ -z "$INIT" ]]; then
  echo "$(date -Iseconds) no active initiative; nothing to drain" >>"$LOG"
  exit 0
fi

QUEUED="$(./kitty builder queue status 2>/dev/null | awk '/queued:/{print $2; exit}')"
QUEUED="${QUEUED:-0}"
if [[ "$QUEUED" -eq 0 ]]; then
  echo "$(date -Iseconds) initiative=$INIT but queue is empty; nothing to drain" >>"$LOG"
  exit 0
fi

{
  echo "=== $(date -Iseconds) draining initiative=$INIT queued=$QUEUED ==="
  git rev-parse --abbrev-ref HEAD
  git rev-parse --short HEAD
} >>"$LOG"

set +e
./kitty builder initiative run "$INIT" \
  --free \
  --gate manual \
  --max-runtime "$MAX_RUNTIME" \
  >>"$LOG" 2>&1
RC=$?
set -e

{
  echo "=== $(date -Iseconds) exit=$RC ==="
  ./kitty builder queue status 2>/dev/null || true
} >>"$LOG"

# Leave a breadcrumb where the next session will actually look.
SUMMARY="$REPO/data/kittybuilder/LAST_DRAIN.md"
{
  echo "# Last nightly drain"
  echo
  echo "- **When:** $(date -Iseconds)"
  echo "- **Initiative:** $INIT"
  echo "- **Exit code:** $RC $([[ $RC -eq 0 ]] && echo '(clean)' || echo '(FAILED — read the log)')"
  echo "- **Log:** \`${LOG/#$HOME/\~}\`"
  echo "- **Queue after:**"
  ./kitty builder queue status 2>/dev/null | sed 's/^/      /' || true
  echo
  echo "Gate is \`manual\` — nothing was published or merged. Review before shipping."
} >"$SUMMARY"

exit "$RC"
