#!/usr/bin/env bash
# Health-check all Edge MCP API servers (no mocks).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=edge-mcp-lib.sh
source "${SCRIPT_DIR}/edge-mcp-lib.sh"

EDGE_MCP_SERVICES="${EDGE_MCP_SERVICES:-xiaohongshu,wx_cli,opencli_weixin,wechat_viewer}"

pass=0
fail=0

check_health() {
  local service="$1"
  local port
  port="$(edge_mcp_service_port "${service}")"
  local url="http://127.0.0.1:${port}/health"
  if curl -sf --max-time 3 "${url}" >/dev/null 2>&1; then
    echo "PASS: ${service} ${url}"
    pass=$((pass + 1))
  else
    echo "FAIL: ${service} ${url}" >&2
    fail=$((fail + 1))
  fi
}

echo "==> Edge MCP health (${EDGE_MCP_SERVICES})"
IFS=',' read -r -a _services <<< "${EDGE_MCP_SERVICES}"
for service in "${_services[@]}"; do
  service="${service// /}"
  [[ -n "${service}" ]] || continue
  check_health "${service}"
done

echo ""
echo "Summary: ${pass} passed, ${fail} failed"
[[ "${fail}" -eq 0 ]]
