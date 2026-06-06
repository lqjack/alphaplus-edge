#!/usr/bin/env bash
# macOS: minimal cloud stack for Edge xhs→RAG LIVE E2E (direct processes, no supervisor).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PID_DIR="${REPO_ROOT}/.edge-runtime"
mkdir -p "${PID_DIR}" "${REPO_ROOT}/logs"

GATEWAY_PORT="${ALPHAPLUS_GATEWAY_PORT:-8001}"
export ALPHAPLUS_GATEWAY_PORT="${GATEWAY_PORT}"
export GATEWAY_PORT
export GATEWAY_DEPLOYMENT_PROFILE="${GATEWAY_DEPLOYMENT_PROFILE:-cloud-only}"
export GATEWAY_SERVICE_AUTOSTART_ENABLED="${GATEWAY_SERVICE_AUTOSTART_ENABLED:-false}"
export EDGE_REGISTRY_STORE="${EDGE_REGISTRY_STORE:-sqlite}"
export EDGE_REGISTRY_PATH="${EDGE_REGISTRY_PATH:-${REPO_ROOT}/dataproai/data/edge_registry.sqlite}"

is_listening() {
  /usr/sbin/lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

wait_http() {
  local url="$1"
  local label="$2"
  local max="${3:-180}"
  local i=0
  while (( i < max )); do
    if curl -sf --max-time 3 "${url}" >/dev/null 2>&1; then
      echo "OK: ${label}"
      return 0
    fi
    sleep 2
    i=$((i + 2))
  done
  echo "ERROR: ${label} not ready — ${url}" >&2
  return 1
}

start_bg() {
  local name="$1"
  local port="$2"
  local pid_file="$3"
  local workdir="$4"
  local py="$5"
  shift 5

  if is_listening "${port}"; then
    echo "Already listening: ${name} :${port}"
    return 0
  fi
  if [[ ! -x "${py}" ]]; then
    echo "ERROR: ${py} missing for ${name}" >&2
    return 1
  fi
  echo "==> Starting ${name} on :${port}"
  (
    cd "${workdir}"
    nohup "${py}" "$@" >>"${PID_DIR}/${name}.log" 2>&1 &
    echo $! >"${pid_file}"
  )
  echo "    pid=$(cat "${pid_file}") log=${PID_DIR}/${name}.log"
}

DATAPROAI_PY="${REPO_ROOT}/dataproai/.venv/bin/python"
STOCK_PY="${REPO_ROOT}/stock/.venv/bin/python"
SKILLS_PY="${REPO_ROOT}/dataproai/src/servers/skills_api/.mcp_venv/bin/python"
AI_PY="${REPO_ROOT}/dataproai/src/servers/ai/.mcp_venv/bin/python"
STOCK_PYTHONPATH="${REPO_ROOT}/stock:${REPO_ROOT}/dataproai/src/servers:${REPO_ROOT}/dataproai/src"
SHARED_DIR="${REPO_ROOT}/dataproai/src/servers/shared_server"
SKILLS_DIR="${REPO_ROOT}/dataproai/src/servers/skills_api"
AI_DIR="${REPO_ROOT}/dataproai/src/servers/ai"

echo "==> Mac RAG stack (direct) for Edge LIVE E2E"

if ! "${STOCK_PY}" -c "import redis" 2>/dev/null; then
  echo "==> Installing stock venv dependency: redis"
  (cd "${REPO_ROOT}/stock" && uv pip install redis)
fi

bash "${SCRIPT_DIR}/start-mac-gateway.sh"

if is_listening 10000; then
  echo "Already listening: dataproai_backend :10000"
else
  echo "==> Starting dataproai_backend on :10000"
  (
    cd "${REPO_ROOT}/dataproai"
    export PYTHONPATH="${REPO_ROOT}/dataproai/src"
    nohup "${DATAPROAI_PY}" src/main.py >>"${PID_DIR}/dataproai_backend.log" 2>&1 &
    echo $! >"${PID_DIR}/dataproai-backend.pid"
  )
  echo "    pid=$(cat "${PID_DIR}/dataproai-backend.pid") log=${PID_DIR}/dataproai_backend.log"
fi

start_bg shared_rag 10520 "${PID_DIR}/shared-rag.pid" "${SHARED_DIR}" "${DATAPROAI_PY}" \
  server.py --rag-only --host 0.0.0.0 --port 10520

start_bg skills_api 10001 "${PID_DIR}/skills-api.pid" "${SKILLS_DIR}" "${SKILLS_PY}" \
  api_server.py

start_bg ai 10300 "${PID_DIR}/ai-api.pid" "${AI_DIR}" "${AI_PY}" \
  api_server.py

if is_listening 50000; then
  echo "Already listening: stock_backend :50000"
else
  echo "==> Starting stock_backend on :50000"
  (
    cd "${REPO_ROOT}/stock"
    export PYTHONPATH="${STOCK_PYTHONPATH}"
    nohup "${STOCK_PY}" -m uvicorn backend.src.main:app --host 127.0.0.1 --port 50000 \
      >>"${PID_DIR}/stock_backend.log" 2>&1 &
    echo $! >"${PID_DIR}/stock-backend.pid"
  )
  echo "    pid=$(cat "${PID_DIR}/stock-backend.pid") log=${PID_DIR}/stock_backend.log"
fi

wait_http "http://127.0.0.1:${GATEWAY_PORT}/health" "gateway /health" 60
wait_http "http://127.0.0.1:10000/health" "dataproai_backend" 120
wait_http "http://127.0.0.1:10520/api/rag/health" "shared_rag" 180
wait_http "http://127.0.0.1:50000/health" "stock_backend" 120
wait_http "http://127.0.0.1:10001/health" "skills_api" 120
wait_http "http://127.0.0.1:10300/health" "ai" 180

echo ""
echo "Cloud stack ready."
echo "  bash scripts/edge/start-edge-mcp.sh"
echo "  EDGE_START_TUNNEL=false bash scripts/edge/start-edge-stack.sh"
echo "  XHS_LIVE_SHARE_URL=... bash scripts/edge/live-edge-xhs-rag-e2e.sh"
