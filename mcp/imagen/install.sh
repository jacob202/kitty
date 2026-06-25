#!/usr/bin/env bash
# One-command install for the Imagen MCP server.
#
# Creates a venv in mcp/imagen/.venv, installs requirements, and registers the
# server in Claude Code via:
#   - .mcp.json at the repo root (primary; relative paths, portable)
#   - ~/.claude/settings.json  (fallback for global installs; absolute paths)
#
# Idempotent: re-running with the same config is a no-op; with a different
# config, the new config wins (with a warning). To preserve an existing config,
# pass --keep-existing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
IMAGEN_DIR="$REPO_ROOT/mcp/imagen"
VENV_DIR="$IMAGEN_DIR/.venv"
PROJECT_MCP_JSON="$REPO_ROOT/.mcp.json"
GLOBAL_SETTINGS="$HOME/.claude/settings.json"
SCRIPT_PY="$IMAGEN_DIR/scripts/patch_settings.py"
SERVER_REL="./mcp/imagen/server.py"
PY_REL="./mcp/imagen/.venv/bin/python"

DRY_RUN=0
UNINSTALL=0
KEEP_EXISTING=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --uninstall) UNINSTALL=1; shift ;;
        --keep-existing) KEEP_EXISTING=1; shift ;;
        -h|--help)
            sed -n '2,15p' "$0" | sed 's/^# //; s/^#//'
            exit 0
            ;;
        *) echo "unknown flag: $1" >&2; exit 2 ;;
    esac
done

log()  { printf "  %s\n" "$*"; }
ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*" >&2; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$*" >&2; exit 1; }

run() {
    if [[ $DRY_RUN -eq 1 ]]; then
        printf "    [dry-run] %s\n" "$*"
    else
        "$@"
    fi
}

require_python() {
    command -v python3.12 >/dev/null 2>&1 || fail "python3.12 not found. Install Python 3.12 first."
}

patch_mcp_config() {
    local target_path="$1" config_json="$2"
    if [[ ! -f "$SCRIPT_PY" ]]; then
        fail "patcher not found: $SCRIPT_PY"
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        printf "    [dry-run] echo %s | %s %s imagen\n" \
            "$(printf '%s' "$config_json" | sed 's/"/\\"/g')" \
            "python3.12 $SCRIPT_PY" \
            "$target_path"
        return
    fi
    local force_flag=()
    [[ $KEEP_EXISTING -eq 0 ]] && force_flag=(--force)
    printf '%s' "$config_json" | python3.12 "$SCRIPT_PY" "$target_path" imagen "${force_flag[@]}"
}

uninstall() {
    ok "Removing venv at $VENV_DIR"
    run rm -rf "$VENV_DIR"
    ok "Removing 'imagen' from $PROJECT_MCP_JSON"
    if [[ -f "$PROJECT_MCP_JSON" ]]; then
        run python3.12 -c "
import json, sys
p = '$PROJECT_MCP_JSON'
with open(p) as f: d = json.load(f)
d.get('mcpServers', {}).pop('imagen', None)
if d.get('mcpServers') == {}: d.pop('mcpServers', None)
with open(p, 'w') as f: json.dump(d, f, indent=2, sort_keys=False)
"
    fi
    if [[ -f "$GLOBAL_SETTINGS" ]]; then
        ok "Removing 'imagen' from $GLOBAL_SETTINGS"
        run python3.12 -c "
import json, sys
p = '$GLOBAL_SETTINGS'
with open(p) as f: d = json.load(f)
d.get('mcpServers', {}).pop('imagen', None)
if d.get('mcpServers') == {}: d.pop('mcpServers', None)
with open(p, 'w') as f: json.dump(d, f, indent=2, sort_keys=False)
"
    fi
    ok "Uninstall complete. Restart Claude Code to stop the server."
    exit 0
}

require_python

if [[ $UNINSTALL -eq 1 ]]; then
    uninstall
fi

log "Repo root:    $REPO_ROOT"
log "Imagen dir:   $IMAGEN_DIR"

if [[ -d "$VENV_DIR" ]]; then
    ok "venv already exists at $VENV_DIR"
else
    log "Creating venv at $VENV_DIR"
    run python3.12 -m venv "$VENV_DIR"
fi

log "Installing requirements"
run "$VENV_DIR/bin/pip" install -q --upgrade pip
run "$VENV_DIR/bin/pip" install -q -r "$IMAGEN_DIR/requirements.txt"
ok "Requirements installed"

if [[ -z "${GEMINI_API_KEY:-}" && ! -f "$IMAGEN_DIR/.env" ]]; then
    warn "GEMINI_API_KEY not in shell env and no .env file. Image tools will fail at runtime."
    warn "Set GEMINI_API_KEY in your shell profile, or copy .env.example to .env and fill it in."
fi

PY_ABS="$REPO_ROOT/mcp/imagen/.venv/bin/python"
SERVER_ABS="$REPO_ROOT/mcp/imagen/server.py"

REL_CONFIG=$(cat <<EOF
{"type": "stdio", "command": "$PY_REL", "args": ["$SERVER_REL"]}
EOF
)
ABS_CONFIG=$(cat <<EOF
{"type": "stdio", "command": "$PY_ABS", "args": ["$SERVER_ABS"]}
EOF
)

log "Writing $PROJECT_MCP_JSON (primary, relative paths)"
patch_mcp_config "$PROJECT_MCP_JSON" "$REL_CONFIG"
ok "$PROJECT_MCP_JSON registered"

if [[ -f "$GLOBAL_SETTINGS" ]]; then
    log "Patching $GLOBAL_SETTINGS (fallback, absolute paths)"
    patch_mcp_config "$GLOBAL_SETTINGS" "$ABS_CONFIG"
    ok "$GLOBAL_SETTINGS registered"
else
    log "No $GLOBAL_SETTINGS found; skipping fallback patch. Project .mcp.json is sufficient."
fi

cat <<EOF

  \033[32m✓ Install complete\033[0m

  Restart Claude Code. Then try:

    "generate a photo of a misty harbor at dawn"

  The model sees the image; your terminal does not. To view the file, ask
  Claude to "open the last image" (a follow-up tool lands in PR 4) or open
  ~/Pictures/kitty-gen/ in Finder.
EOF
