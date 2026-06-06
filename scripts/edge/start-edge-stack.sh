#!/usr/bin/env bash
# Start Edge-local health server, optional tunnel, and print next steps.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

export EDGE_ID="${EDGE_ID:-local-edge}"
export EDGE_DEVICE_TOKEN="${EDGE_DEVICE_TOKEN:-dev-edge-token}"
export EDGE_HEALTH_HOST="${EDGE_HEALTH_HOST:-127.0.0.1}"
export EDGE_HEALTH_PORT="${EDGE_HEALTH_PORT:-10490}"
export EDGE_CALLBACK_BASE_URL="${EDGE_CALLBACK_BASE_URL:-http://${EDGE_HEALTH_HOST}:${EDGE_HEALTH_PORT}}"
export GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8001}"
export EDGE_SERVICES="${EDGE_SERVICES:-xiaohongshu,wx_cli,opencli_weixin,wechat_viewer}"
export PYTHONPATH="${REPO_ROOT}/dataproai/src:${PYTHONPATH:-}"

PID_DIR="${REPO_ROOT}/.edge-runtime"
mkdir -p "${PID_DIR}"
HEALTH_PID_FILE="${PID_DIR}/edge-health.pid"
TUNNEL_PID_FILE="${PID_DIR}/edge-tunnel.pid"

start_background() {
  local name="$1"
  local pid_file="$2"
  shift 2
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    echo "Already running: ${name} (pid $(cat "${pid_file}"))"
    return 0
  fi
  nohup "$@" >"${PID_DIR}/${name}.log" 2>&1 &
  echo $! >"${pid_file}"
  echo "Started ${name} (pid $(cat "${pid_file}"))"
}

echo "==> Starting Edge health server on ${EDGE_CALLBACK_BASE_URL}"
start_background edge-health "${HEALTH_PID_FILE}" \
  python3 "${SCRIPT_DIR}/edge_health_server.py" \
  --host "${EDGE_HEALTH_HOST}" --port "${EDGE_HEALTH_PORT}"

if [[ "${EDGE_START_TUNNEL:-true}" == "true" ]]; then
  echo "==> Starting Edge tunnel client -> ${GATEWAY_URL}"
  start_background edge-tunnel "${TUNNEL_PID_FILE}" \
    python3 "${SCRIPT_DIR}/edge_tunnel_client.py" \
    --gateway-url "${GATEWAY_URL}" \
    --token "${EDGE_DEVICE_TOKEN}" \
    --edge-id "${EDGE_ID}"
fi

echo
echo "==> Registering with Gateway"
bash "${SCRIPT_DIR}/register-with-gateway.sh" || echo "WARN: registration failed (is Gateway up?)"

echo
echo "Edge stack started."
echo "  Health:  ${EDGE_CALLBACK_BASE_URL}/health"
echo "  Doctor:  bash scripts/edge/edge-doctor.sh"
echo "  Logs:    ${PID_DIR}/edge-health.log , ${PID_DIR}/edge-tunnel.log"
