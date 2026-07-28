#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_ROOT="${KITTY_FOUNDATION_WORKDIR:-$HOME/.cache/kitty-foundation-spike}"
LIBRECHAT_DIR="$WORK_ROOT/librechat"
ANYTHINGLLM_DIR="$WORK_ROOT/anythingllm"

LIBRECHAT_REPO="https://github.com/danny-avila/LibreChat.git"
LIBRECHAT_SHA="a53936d27351e798d320df8f717be3f2272fc49d"
ANYTHINGLLM_REPO="https://github.com/Mintplex-Labs/anything-llm.git"
ANYTHINGLLM_SHA="30c047e61b9dc96d9fcb93fbb1d3d5f0f1fec22e"

fail() {
  printf 'foundation-spike: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

require_gateway_secret() {
  [[ -n "${GATEWAY_SECRET:-}" ]] || fail "export GATEWAY_SECRET with the value used by Kitty Gateway"
  [[ "$GATEWAY_SECRET" != *$'\n'* ]] || fail "GATEWAY_SECRET must not contain a newline"
}

append_dotenv_value() {
  local file="$1"
  local key="$2"
  local value="$3"

  python3 - "$file" "$key" "$value" <<'PY'
import json
import sys

path, key, value = sys.argv[1:]
with open(path, "a", encoding="utf-8") as handle:
    handle.write(f"\n{key}={json.dumps(value)}\n")
PY
}

prepare_checkout() {
  local name="$1"
  local repo="$2"
  local sha="$3"
  local directory="$4"

  mkdir -p "$WORK_ROOT"
  if [[ ! -d "$directory/.git" ]]; then
    rm -rf "$directory"
    mkdir -p "$directory"
    git -C "$directory" init -q
    git -C "$directory" remote add origin "$repo"
  fi

  if ! git -C "$directory" diff --quiet || ! git -C "$directory" diff --cached --quiet; then
    fail "$name checkout is dirty: $directory"
  fi

  git -C "$directory" fetch -q --depth 1 origin "$sha"
  git -C "$directory" checkout -q --detach FETCH_HEAD
  [[ "$(git -C "$directory" rev-parse HEAD)" == "$sha" ]] || fail "$name did not checkout pinned commit $sha"
}

verify_mit_license() {
  local name="$1"
  local directory="$2"
  local license_file=""

  for candidate in LICENSE LICENSE.md LICENSE.txt; do
    if [[ -f "$directory/$candidate" ]]; then
      license_file="$directory/$candidate"
      break
    fi
  done

  [[ -n "$license_file" ]] || fail "$name checkout has no recognized license file"
  grep -qi "MIT License" "$license_file" || fail "$name is not carrying the expected MIT license"
  printf '%s license verified: %s\n' "$name" "$license_file"
}

wait_http() {
  local url="$1"
  local attempts="${2:-60}"
  local count
  for ((count = 1; count <= attempts; count++)); do
    if curl -fsS --max-time 3 "$url" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  fail "service did not become ready: $url"
}

verify_gateway() {
  require_gateway_secret
  curl -fsS --max-time 5 "http://127.0.0.1:8000/health" >/dev/null \
    || fail "Kitty Gateway health check failed on 127.0.0.1:8000"

  local payload
  payload="$(curl -fsS --max-time 5 \
    -H "Authorization: Bearer $GATEWAY_SECRET" \
    "http://127.0.0.1:8000/v1/models")" \
    || fail "Kitty Gateway does not expose the required /v1/models compatibility endpoint"

  python3 - "$payload" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
models = payload.get("data")
if payload.get("object") != "list" or not isinstance(models, list):
    raise SystemExit("invalid OpenAI-compatible models response")
if not any(item.get("id") == "kitty-default" for item in models if isinstance(item, dict)):
    raise SystemExit("kitty-default is missing from models response")
PY
  printf 'Kitty Gateway compatibility surface verified.\n'
}

start_librechat() {
  require_gateway_secret
  prepare_checkout "LibreChat" "$LIBRECHAT_REPO" "$LIBRECHAT_SHA" "$LIBRECHAT_DIR"
  verify_mit_license "LibreChat" "$LIBRECHAT_DIR"

  cp "$LIBRECHAT_DIR/.env.example" "$LIBRECHAT_DIR/.env"
  append_dotenv_value "$LIBRECHAT_DIR/.env" "KITTY_GATEWAY_SECRET" "$GATEWAY_SECRET"
  cp "$SCRIPT_DIR/librechat/librechat.yaml" "$LIBRECHAT_DIR/librechat.yaml"
  cp "$SCRIPT_DIR/librechat/docker-compose.override.yml" "$LIBRECHAT_DIR/docker-compose.override.yml"

  docker compose -f "$LIBRECHAT_DIR/docker-compose.yml" \
    -f "$LIBRECHAT_DIR/docker-compose.override.yml" \
    --project-directory "$LIBRECHAT_DIR" up -d
  wait_http "http://127.0.0.1:3080"
  printf 'LibreChat prototype is running at http://127.0.0.1:3080\n'
}

start_anythingllm() {
  require_gateway_secret
  prepare_checkout "AnythingLLM" "$ANYTHINGLLM_REPO" "$ANYTHINGLLM_SHA" "$ANYTHINGLLM_DIR"
  verify_mit_license "AnythingLLM" "$ANYTHINGLLM_DIR"

  cp "$ANYTHINGLLM_DIR/docker/.env.example" "$ANYTHINGLLM_DIR/docker/.env"
  cat "$SCRIPT_DIR/anythingllm/kitty.env" >>"$ANYTHINGLLM_DIR/docker/.env"
  append_dotenv_value "$ANYTHINGLLM_DIR/docker/.env" "GENERIC_OPEN_AI_API_KEY" "$GATEWAY_SECRET"
  append_dotenv_value "$ANYTHINGLLM_DIR/docker/.env" "UID" "$(id -u)"
  append_dotenv_value "$ANYTHINGLLM_DIR/docker/.env" "GID" "$(id -g)"
  mkdir -p \
    "$ANYTHINGLLM_DIR/server/storage" \
    "$ANYTHINGLLM_DIR/collector/hotdir" \
    "$ANYTHINGLLM_DIR/collector/outputs"

  docker compose -f "$ANYTHINGLLM_DIR/docker/docker-compose.yml" \
    --project-directory "$ANYTHINGLLM_DIR/docker" up -d --build
  wait_http "http://127.0.0.1:3001"
  printf 'AnythingLLM prototype is running at http://127.0.0.1:3001\n'
}

stop_candidate() {
  case "${1:-}" in
    librechat)
      [[ -d "$LIBRECHAT_DIR" ]] || return 0
      docker compose -f "$LIBRECHAT_DIR/docker-compose.yml" \
        -f "$LIBRECHAT_DIR/docker-compose.override.yml" \
        --project-directory "$LIBRECHAT_DIR" down
      ;;
    anythingllm)
      [[ -d "$ANYTHINGLLM_DIR" ]] || return 0
      docker compose -f "$ANYTHINGLLM_DIR/docker/docker-compose.yml" \
        --project-directory "$ANYTHINGLLM_DIR/docker" down
      ;;
    *) fail "usage: $0 stop {librechat|anythingllm}" ;;
  esac
}

main() {
  require_command git
  require_command curl
  require_command python3

  case "${1:-}" in
    verify)
      verify_gateway
      ;;
    librechat)
      require_command docker
      docker compose version >/dev/null
      verify_gateway
      start_librechat
      ;;
    anythingllm)
      require_command docker
      docker compose version >/dev/null
      verify_gateway
      start_anythingllm
      ;;
    stop)
      require_command docker
      docker compose version >/dev/null
      stop_candidate "${2:-}"
      ;;
    *)
      fail "usage: $0 {verify|librechat|anythingllm|stop librechat|stop anythingllm}"
      ;;
  esac
}

main "$@"
