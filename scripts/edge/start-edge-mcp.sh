#!/usr/bin/env bash
# Start Edge-local MCP API servers (xiaohongshu, wx_cli, opencli_weixin, wechat_viewer).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PID_DIR="${REPO_ROOT}/.edge-runtime"
mkdir -p "${PID_DIR}"

# shellcheck source=edge-mcp-lib.sh
source "${SCRIPT_DIR}/edge-mcp-lib.sh"

export PYTHONPATH="${REPO_ROOT}/dataproai/src:${REPO_ROOT}/dataproai/src/servers:${PYTHONPATH:-}"
EDGE_MCP_SERVICES="${EDGE_MCP_SERVICES:-xiaohongshu,wx_cli,opencli_weixin,wechat_viewer}"

is_listening() {
  /usr/sbin/lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

wait_http() {
  local url="$1"
  local label="$2"
  local max="${3:-90}"
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

start_edge_mcp_service() {
  local service="$1"
  local port py workdir pid_file
  port="$(edge_mcp_service_port "${service}")"
  py="$(edge_mcp_service_python "${REPO_ROOT}" "${service}")"
  workdir="$(edge_mcp_service_dir "${REPO_ROOT}" "${service}")"
  pid_file="${PID_DIR}/${service}-api.pid"

  if [[ ! -x "${py}" ]]; then
    echo "ERROR: Python missing for ${service}: ${py}" >&2
    return 1
  fi

  echo "==> Ensuring ${service} dependencies"
  edge_mcp_ensure_deps "${REPO_ROOT}" "${service}"

  if is_listening "${port}"; then
    echo "Already listening: ${service} :${port}"
    return 0
  fi

  echo "==> Starting ${service} on :${port}"
  (
    cd "${workdir}"
    edge_mcp_service_env "${REPO_ROOT}" "${service}"
    nohup "${py}" api_server.py >>"${PID_DIR}/${service}.log" 2>&1 &
    echo $! >"${pid_file}"
  )
  echo "    pid=$(cat "${pid_file}") log=${PID_DIR}/${service}.log"
}

IFS=',' read -r -a _EDGE_MCP_LIST <<< "${EDGE_MCP_SERVICES}"
for service in "${_EDGE_MCP_LIST[@]}"; do
  service="${service// /}"
  [[ -n "${service}" ]] || continue
  start_edge_mcp_service "${service}"
done

echo ""
for service in "${_EDGE_MCP_LIST[@]}"; do
  service="${service// /}"
  [[ -n "${service}" ]] || continue
  port="$(edge_mcp_service_port "${service}")"
  wait_http "http://127.0.0.1:${port}/health" "${service} /health"
done

echo ""
echo "Edge MCP APIs ready:"
for service in "${_EDGE_MCP_LIST[@]}"; do
  service="${service// /}"
  [[ -n "${service}" ]] || continue
  port="$(edge_mcp_service_port "${service}")"
  printf "  %-16s http://127.0.0.1:%s\n" "${service}" "${port}"
done
