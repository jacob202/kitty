#!/usr/bin/env bash
# setup_brief.sh — Set up the morning brief launchd job
# Checks for Pushover credentials, then loads the plist.

set -euo pipefail

ENV_FILE="/Users/jacobbrizinski/Projects/kitty/.env"
PLIST="$HOME/Library/LaunchAgents/com.kitty.morning-brief.plist"

echo "=== Kitty Morning Brief Setup ==="

# Check .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env file not found at $ENV_FILE"
    exit 1
fi

# Check for Pushover credentials
MISSING=0

if ! grep -q '^PUSHOVER_USER_KEY=' "$ENV_FILE"; then
    echo "MISSING: PUSHOVER_USER_KEY not found in .env"
    MISSING=1
fi

if ! grep -q '^PUSHOVER_API_TOKEN=' "$ENV_FILE"; then
    echo "MISSING: PUSHOVER_API_TOKEN not found in .env"
    MISSING=1
fi

if [ "$MISSING" -eq 1 ]; then
    echo ""
    echo "Get your Pushover credentials:"
    echo "  1. Sign up at https://pushover.net"
    echo "  2. Your User Key is on the main dashboard (top right)"
    echo "  3. Create an Application at https://pushover.net/apps/build to get an API Token"
    echo ""
    echo "Then add these lines to your .env file:"
    echo "  PUSHOVER_USER_KEY=your_user_key_here"
    echo "  PUSHOVER_API_TOKEN=your_api_token_here"
    echo ""
    echo "After that, run this script again."
    exit 1
fi

echo "Pushover credentials found."

# Check plist symlink exists
if [ ! -L "$PLIST" ]; then
    echo "ERROR: Plist symlink not found at $PLIST"
    echo "Run: ln -sf /Users/jacobbrizinski/Projects/kitty/kitty_gateway/com.kitty.morning-brief.plist ~/Library/LaunchAgents/com.kitty.morning-brief.plist"
    exit 1
fi

# Unload if already loaded (idempotent)
launchctl unload "$PLIST" 2>/dev/null || true

# Load the plist
launchctl load "$PLIST"
echo "Loaded morning brief plist. Will run daily at 7:00 AM."
echo "Test now with: python3.12 /Users/jacobbrizinski/Projects/kitty/scripts/brief.py --notify"
