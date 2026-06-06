#!/usr/bin/env bash
# Rotate Edge device token via Gateway API.
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8001}"
EDGE_ID="${EDGE_ID:-local-edge}"
EDGE_DEVICE_TOKEN="${EDGE_DEVICE_TOKEN:-dev-edge-token}"
ADMIN_KEY="${EDGE_ADMIN_KEY:-}"

token="${EDGE_DEVICE_TOKEN}"
if [[ -n "${ADMIN_KEY}" ]]; then
  token="${ADMIN_KEY}"
fi

payload="$(cat <<EOF
{"edge_id":"${EDGE_ID}","device_token":"${token}"}
EOF
)"

echo "Rotating token for edge ${EDGE_ID}"
response="$(curl -fsS -X POST "${GATEWAY_URL%/}/api/edge/devices/rotate-token" \
  -H 'Content-Type: application/json' \
  -d "${payload}")"
echo "${response}" | python3 -m json.tool

new_token="$(echo "${response}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("device_token",""))')"
if [[ -n "${new_token}" ]]; then
  echo
  echo "Export new token:"
  echo "  export EDGE_DEVICE_TOKEN=${new_token}"
fi
