#!/usr/bin/env bash
# macOS: start Gateway :8001 for Edge bridge local dev/verify (minimal, no full stack).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
GATEWAY_PORT="${ALPHAPLUS_GATEWAY_PORT:-8001}"
GATEWAY_HOST="${GATEWAY_HOST:-127.0.0.1}"
GATEWAY_LOG="${GATEWAY_LOG:-${REPO_ROOT}/logs/gateway-edge-mac.log}"
PID_FILE="${REPO_ROOT}/.runtime/gateway-edge-mac.pid"

mkdir -p "${REPO_ROOT}/logs" "${REPO_ROOT}/.runtime"
export GATEWAY_DEPLOYMENT_PROFILE="${GATEWAY_DEPLOYMENT_PROFILE:-cloud-only}"
# Edge verify only needs edge API + /health — skip heavy cloud service autostart.
export GATEWAY_SERVICE_AUTOSTART_ENABLED="${GATEWAY_SERVICE_AUTOSTART_ENABLED:-false}"
export EDGE_REGISTRY_STORE="${EDGE_REGISTRY_STORE:-sqlite}"
export EDGE_REGISTRY_PATH="${EDGE_REGISTRY_PATH:-${REPO_ROOT}/dataproai/data/edge_registry.sqlite}"
export GATEWAY_PORT="${GATEWAY_PORT}"
mkdir -p "$(dirname "${EDGE_REGISTRY_PATH}")"

is_listening() {
  /usr/sbin/lsof -nP -iTCP:"${GATEWAY_PORT}" -sTCP:LISTEN >/dev/null 2>&1
}

wait_http() {
  local url="$1"
  local label="$2"
  local max="${3:-60}"
  local i=0
  while (( i < max )); do
    if curl -sf --max-time 2 "${url}" >/dev/null 2>&1; then
      echo "OK: ${label}"
      return 0
    fi
    sleep 1
    i=$((i + 1))
  done
  echo "ERROR: ${label} not ready — ${url}" >&2
  return 1
}

if is_listening "${GATEWAY_PORT}"; then
  echo "Gateway already listening on ${GATEWAY_HOST}:${GATEWAY_PORT}"
else
  PY="${REPO_ROOT}/gateway/.venv/bin/python"
  if [[ ! -x "${PY}" ]]; then
    echo "ERROR: ${PY} missing — create gateway venv first" >&2
    exit 1
  fi
  echo "==> Starting Gateway on ${GATEWAY_HOST}:${GATEWAY_PORT}"
  echo "    profile=${GATEWAY_DEPLOYMENT_PROFILE} autostart=${GATEWAY_SERVICE_AUTOSTART_ENABLED} registry=${EDGE_REGISTRY_STORE}"
  nohup "${PY}" -m gateway.main --host "${GATEWAY_HOST}" --port "${GATEWAY_PORT}" \
    >>"${GATEWAY_LOG}" 2>&1 &
  echo $! >"${PID_FILE}"
  echo "    pid=$(cat "${PID_FILE}") log=${GATEWAY_LOG}"
fi

wait_http "http://${GATEWAY_HOST}:${GATEWAY_PORT}/health" "gateway /health"
wait_http "http://${GATEWAY_HOST}:${GATEWAY_PORT}/api/edge/devices" "gateway edge API"

echo ""
echo "Gateway ready for Edge verify:"
echo "  bash scripts/edge/verify-edge-macos.sh"
echo "  bash scripts/edge/edge-doctor.sh"
