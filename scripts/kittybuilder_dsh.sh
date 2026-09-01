#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_ROOT="${KITTY_BUILDER_REPO_ROOT:-${REPO_ROOT}}"
if [[ -z "${OPENROUTER_API_KEY:-}" && -f "${ENV_ROOT}/.env" ]]; then
  OPENROUTER_API_KEY="$(
    "${PYTHON_BIN:-$(command -v python3.12 || command -v python3 || echo python3)}" - "${ENV_ROOT}/.env" <<'PY_KEY'
import sys
from dotenv import dotenv_values

value = dotenv_values(sys.argv[1]).get("OPENROUTER_API_KEY")
if value:
    print(value, end="")
PY_KEY
  )"
  [[ -n "${OPENROUTER_API_KEY}" ]] && export OPENROUTER_API_KEY
fi

preset=""
provider="openrouter"
model=""
permission="workspace-write"
task_file=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --preset) preset="${2:?missing --preset value}"; shift 2 ;;
    --provider) provider="${2:?missing --provider value}"; shift 2 ;;
    --model) model="${2:?missing --model value}"; shift 2 ;;
    --permission) permission="${2:?missing --permission value}"; shift 2 ;;
    --task-file) task_file="${2:?missing --task-file value}"; shift 2 ;;
    *) echo "ERROR: unknown kittybuilder_dsh option: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$preset" ]] || { echo "ERROR: --preset is required" >&2; exit 2; }
[[ -n "$model" ]] || { echo "ERROR: --model is required" >&2; exit 2; }
[[ -f "$task_file" ]] || { echo "ERROR: --task-file must name a file" >&2; exit 2; }
case "$permission" in read-only|workspace-write) ;; *) echo "ERROR: unsupported DSH permission: $permission" >&2; exit 2 ;; esac

DSH_BIN="$(command -v dsh || true)"
[[ -n "$DSH_BIN" ]] || { echo "ERROR: dsh is not installed" >&2; exit 75; }
DSH_REAL="$(python3 - "$DSH_BIN" <<'PY'
import os, sys
print(os.path.realpath(sys.argv[1]))
PY
)"
DSH_ROOT="${KITTY_DSH_PACKAGE_ROOT:-$(cd "$(dirname "$DSH_REAL")/.." && pwd)}"
RUNNER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/kittybuilder_dsh_headless.mjs"
[[ -f "$RUNNER" ]] || { echo "ERROR: Kitty DSH headless runner missing: $RUNNER" >&2; exit 1; }

if [[ "$provider" == "openrouter" && "$model" == opencode/* ]]; then
  echo "ERROR: OpenCode-only model alias is not valid for the DSH OpenRouter provider: $model" >&2
  exit 2
fi
if [[ "$provider" == "openrouter" && "$model" == openrouter/* && "$model" != "openrouter/free" ]]; then
  model="${model#openrouter/}"
fi

task="$(cat "$task_file")"
execution_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
preset_source="${execution_root}/config/dsh/presets/${preset}/agent.cordis.yml"
[[ -f "$preset_source" ]] || { echo "ERROR: Kitty DSH preset missing: $preset_source" >&2; exit 1; }
runtime_root="$(mktemp -d "${TMPDIR:-/tmp}/kitty-dsh-runtime.XXXXXX")"
runtime_home="${runtime_root}/home"
user_preset_root="${runtime_home}/.agent-presets"
mkdir -p "${user_preset_root}/${preset}"
cp "$preset_source" "${user_preset_root}/${preset}/agent.cordis.yml"
cat > "${runtime_home}/settings.yaml" <<'SETTINGS'
llm-pi-ai:
  providers:
    openrouter:
      apiKeyEnv: OPENROUTER_API_KEY
      retryPolicy:
        mode: normal
        maxRetries: 0
SETTINGS
patch="${runtime_root}/cordis.patch.yml"
cleanup() { rm -rf "$runtime_root"; }
trap cleanup EXIT
runner_uri="$(python3 - "$RUNNER" <<'PY'
import sys
from pathlib import Path
print(Path(sys.argv[1]).resolve().as_uri())
PY
)"
cat > "$patch" <<EOF
- id: headless-runner
  disabled: true
- id: session-title-llm
  disabled: true
- insert:
    - id: agent-presets
      name: '@deepseek-ai/dsh-agent-presets'
      config:
        default: ${preset}
        includeUserRoot: true
    - id: kitty-headless-runner
      name: '${runner_uri}'
      inject: [headlessStartup, agentPresets]
      config:
        task: !!js ctx.headlessStartup.task
EOF

export KITTY_DSH_PACKAGE_ROOT="$DSH_ROOT"
export KITTY_DSH_PRESET="$preset"
export KITTY_DSH_PROVIDER="$provider"
export KITTY_DSH_MODEL="$model"
export DSH_PERMISSION_MODE="$permission"
export DSH_HOME="$runtime_home"
exec "$DSH_BIN" --profile headless --patch "$patch" "$task"
