#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/kitty_gateway/openwebui.env"
DOCKER_DIR="${ROOT_DIR}/gateway/docker_terminal"
LOG_DIR="${ROOT_DIR}/logs/kitty_gateway"
IMAGE_NAME="kitty-terminal"
CONTAINER_NAME="kitty-terminal"
HOST_PORT=9615
CONTAINER_PORT=9615
DATA_DIR="${ROOT_DIR}/data/docker_terminal"

source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  load_env_assignments "${ROOT_DIR}/.env"
fi
if [[ -f "${ENV_FILE}" ]]; then
  load_env_assignments "${ENV_FILE}"
fi

mkdir -p "${LOG_DIR}" "${DATA_DIR}"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop first."
  exit 1
fi

if [[ -z "${KITTY_DOCKER_TERMINAL_API_KEY:-}" ]]; then
  echo "Missing KITTY_DOCKER_TERMINAL_API_KEY in ${ENV_FILE}"
  exit 1
fi

if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER_NAME}$"; then
  echo "Kitty Docker terminal already running on port ${HOST_PORT}"
  exit 0
fi

echo "Building Docker image..."
docker build -t "${IMAGE_NAME}" "${DOCKER_DIR}" > "${LOG_DIR}/docker-terminal-build.log" 2>&1

docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

docker run -d \
  --name "${CONTAINER_NAME}" \
  --restart unless-stopped \
  -p "${HOST_PORT}:${CONTAINER_PORT}" \
  -e OPEN_TERMINAL_API_KEY="${KITTY_DOCKER_TERMINAL_API_KEY}" \
  -e OPEN_TERMINAL_HOST="0.0.0.0" \
  -e OPEN_TERMINAL_PORT="${CONTAINER_PORT}" \
  -v "${DATA_DIR}:/kitty/data" \
  "${IMAGE_NAME}" > "${LOG_DIR}/docker-terminal-run.log" 2>&1

echo "Kitty Docker terminal started on port ${HOST_PORT}"
echo "Data directory: ${DATA_DIR}"
