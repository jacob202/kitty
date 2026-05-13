#!/usr/bin/env bash
# Shared Open WebUI reachability helpers (used by start_all.sh, status_all.sh).
# Probes use OPENWEBUI_HOST + OPENWEBUI_PORT so they match `open-webui serve`, not a stale WEBUI_URL.

canonical_openwebui_base_url() {
  local h="${OPENWEBUI_HOST:-127.0.0.1}"
  local p="${OPENWEBUI_PORT:-3000}"
  echo "http://${h}:${p}"
}

webui_warn_url_mismatch() {
  local canon
  canon="$(canonical_openwebui_base_url)"
  [[ -z "${WEBUI_URL:-}" ]] && return 0
  local w="${WEBUI_URL%/}"
  if [[ "${w}" != "${canon}" ]]; then
    echo "warning: WEBUI_URL (${WEBUI_URL}) != OPENWEBUI_HOST:PORT (${canon}); health probes use ${canon}" >&2
  fi
}

# One attempt: try /health, /api/health, then / (login may return 401).
# Prints "url|http_code" on success; returns 1 if nothing responded as expected.
probe_openwebui_http_once() {
  local base="$1"
  local max_time="${2:-12}"
  local path code
  base="${base%/}"
  for path in "/health" "/api/health" "/"; do
    code="$(curl -sS -g -o /dev/null -w "%{http_code}" --max-time "${max_time}" "${base}${path}" 2>/dev/null || true)"
    [[ -z "${code}" ]] && code="000"
    case "${code}" in
      200 | 201 | 204 | 301 | 302 | 303 | 307 | 308 | 401 | 403)
        printf '%s|%s\n' "${base}${path}" "${code}"
        return 0
        ;;
    esac
  done
  return 1
}
