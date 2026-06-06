#!/usr/bin/env bash
# Quick diagnostics for Edge-local stack.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

EDGE_HEALTH_URL="${EDGE_HEALTH_URL:-http://127.0.0.1:10490/health}"
GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8001}"
EDGE_ID="${EDGE_ID:-local-edge}"

echo "==> Edge health: ${EDGE_HEALTH_URL}"
if curl -fsS "${EDGE_HEALTH_URL}" | python3 -m json.tool; then
  echo "OK: edge health reachable"
else
  echo "WARN: edge health not reachable"
fi

echo
echo "==> Gateway edge devices: ${GATEWAY_URL}/api/edge/devices"
if curl -fsS "${GATEWAY_URL%/}/api/edge/devices" | python3 -m json.tool; then
  echo "OK: gateway edge API reachable"
else
  echo "WARN: gateway edge API not reachable"
fi

echo
echo "==> Gateway tunnel status"
curl -fsS "${GATEWAY_URL%/}/api/edge/tunnel/status" | python3 -m json.tool || true

echo
echo "==> Device status (${EDGE_ID})"
curl -fsS "${GATEWAY_URL%/}/api/edge/devices/${EDGE_ID}/status" | python3 -m json.tool || true

echo
echo "==> OpenCLI / wx-cli LIVE probes"
if [[ "${SKIP_LIVE_EDGE:-0}" == "1" ]]; then
  echo "SKIP: SKIP_LIVE_EDGE=1"
else
  python3 "${SCRIPT_DIR}/verify_edge_live.py" || true
fi

echo
echo "Hints:"
echo "  - Start stack: bash scripts/edge/start-edge-stack.sh"
echo "  - Register:    bash scripts/edge/register-with-gateway.sh"
