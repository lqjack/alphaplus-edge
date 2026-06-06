#!/usr/bin/env bash
# Register local Edge device with cloud Gateway.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8001}"
EDGE_ID="${EDGE_ID:-local-edge}"
EDGE_DEVICE_TOKEN="${EDGE_DEVICE_TOKEN:-dev-edge-token}"
EDGE_CALLBACK_BASE_URL="${EDGE_CALLBACK_BASE_URL:-http://127.0.0.1:10490}"
EDGE_SERVICES="${EDGE_SERVICES:-xiaohongshu,wx_cli,opencli_weixin,wechat_viewer}"
export EDGE_SERVICES

services_json="$(python3 - <<PY
import json, os
services = [s.strip() for s in os.environ.get("EDGE_SERVICES", "").split(",") if s.strip()]
print(json.dumps(services))
PY
)"

payload="$(cat <<EOF
{
  "edge_id": "${EDGE_ID}",
  "device_token": "${EDGE_DEVICE_TOKEN}",
  "callback_base_url": "${EDGE_CALLBACK_BASE_URL}",
  "services": ${services_json},
  "capabilities": {"profile": "edge-user"}
}
EOF
)"

echo "Registering edge ${EDGE_ID} with ${GATEWAY_URL}"
curl -fsS -X POST "${GATEWAY_URL%/}/api/edge/devices/register" \
  -H 'Content-Type: application/json' \
  -d "${payload}"
echo
