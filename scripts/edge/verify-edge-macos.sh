#!/usr/bin/env bash
# Functional verification for macOS Edge install (no mocks — real HTTP + optional Gateway).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ -f "${HOME}/Library/Application Support/AlphaPlus-Edge/edge.env" ]]; then
  # shellcheck disable=SC1090
  source "${HOME}/Library/Application Support/AlphaPlus-Edge/edge.env"
fi

export ALPHAPLUS_REPO_ROOT="${ALPHAPLUS_REPO_ROOT:-${REPO_ROOT}}"
export EDGE_ID="${EDGE_ID:-verify-edge-$(hostname -s | tr '[:upper:]' '[:lower:]')}"
export EDGE_HEALTH_HOST="${EDGE_HEALTH_HOST:-127.0.0.1}"
export EDGE_HEALTH_PORT="${EDGE_HEALTH_PORT:-10490}"
export EDGE_CALLBACK_BASE_URL="${EDGE_CALLBACK_BASE_URL:-http://${EDGE_HEALTH_HOST}:${EDGE_HEALTH_PORT}}"
export GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:${ALPHAPLUS_GATEWAY_PORT:-8001}}"
export PYTHONPATH="${ALPHAPLUS_REPO_ROOT}/dataproai/src:${PYTHONPATH:-}"

HEALTH_PID=""
cleanup() {
  if [[ -n "${HEALTH_PID}" ]] && kill -0 "${HEALTH_PID}" 2>/dev/null; then
    kill "${HEALTH_PID}" 2>/dev/null || true
    wait "${HEALTH_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

pass=0
fail=0

check() {
  local label="$1"
  shift
  if "$@"; then
    echo "PASS: ${label}"
    pass=$((pass + 1))
  else
    echo "FAIL: ${label}" >&2
    fail=$((fail + 1))
  fi
}

echo "==> AlphaPlus Edge macOS verification"
echo "    runtime: ${ALPHAPLUS_REPO_ROOT}"
echo "    health:  ${EDGE_CALLBACK_BASE_URL}"
echo "    gateway: ${GATEWAY_URL}"
echo

echo "==> Contract tests"
check "edge WSS URL builder" python3 -m pytest -q "${SCRIPT_DIR}/test_edge_ws_contract.py"
check "gateway edge API contracts" python3 -m pytest -q \
  "${REPO_ROOT}/gateway/test_edge_api_contract.py" \
  "${REPO_ROOT}/gateway/test_edge_tunnel_contract.py" \
  "${REPO_ROOT}/gateway/test_edge_store_contract.py"

echo
echo "==> Edge health server (live)"
HEALTH_SCRIPT="${ALPHAPLUS_REPO_ROOT}/scripts/edge/edge_health_server.py"
check "health script exists" test -f "${HEALTH_SCRIPT}"

HEALTH_LOG="$(mktemp -t alphaplus-edge-health.XXXXXX.log)"
export EDGE_HEALTH_QUIET=1
python3 "${HEALTH_SCRIPT}" --host "${EDGE_HEALTH_HOST}" --port "${EDGE_HEALTH_PORT}" >>"${HEALTH_LOG}" 2>&1 &
HEALTH_PID=$!

ready=0
for _ in $(seq 1 30); do
  if curl -fsS --max-time 1 "${EDGE_CALLBACK_BASE_URL}/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.2
done
if [[ "${ready}" != "1" ]]; then
  echo "FAIL: health server did not become ready (see ${HEALTH_LOG})" >&2
  fail=$((fail + 1))
else
  if curl -fsS "${EDGE_CALLBACK_BASE_URL}/health" | python3 -c "
import json, sys
raw = sys.stdin.read().strip()
data = json.loads(raw)
assert data.get('ok') is True, data
assert 'services' in data, data
"; then
    echo "PASS: GET /health returns ok"
    pass=$((pass + 1))
  else
    echo "FAIL: GET /health returns ok" >&2
    fail=$((fail + 1))
  fi
fi

echo
echo "==> Gateway integration (optional)"
if curl -fsS --max-time 3 "${GATEWAY_URL%/}/health" >/dev/null 2>&1; then
  TOKEN="${EDGE_DEVICE_TOKEN:-verify-token-$(date +%s)}"
  register_payload=$(python3 - <<PY
import json, os
print(json.dumps({
  "edge_id": os.environ["EDGE_ID"],
  "device_token": "${TOKEN}",
  "callback_base_url": os.environ["EDGE_CALLBACK_BASE_URL"],
  "services": ["xiaohongshu", "wx_cli", "opencli_weixin", "wechat_viewer"],
  "capabilities": {"client": "verify-edge-macos"},
}))
PY
)
  if curl -fsS -X POST "${GATEWAY_URL%/}/api/edge/devices/register" \
    -H "Content-Type: application/json" \
    -d "${register_payload}" | python3 -c "
import json, sys
data = json.load(sys.stdin)
assert data.get('ok') is True or data.get('edge_id'), data
"; then
    echo "PASS: Gateway register"
    pass=$((pass + 1))
  else
    echo "FAIL: Gateway register" >&2
    fail=$((fail + 1))
  fi

  if curl -fsS "${GATEWAY_URL%/}/api/edge/devices/${EDGE_ID}/status" | python3 -c "
import json, sys
data = json.load(sys.stdin)
device = data.get('device') or data
assert device.get('edge_id') == '${EDGE_ID}', data
assert data.get('ok') is True, data
"; then
    echo "PASS: Gateway device status"
    pass=$((pass + 1))
  else
    echo "FAIL: Gateway device status" >&2
    fail=$((fail + 1))
  fi
else
  echo "SKIP: Gateway not reachable at ${GATEWAY_URL} (run: bash scripts/edge/start-mac-gateway.sh)"
fi

echo
echo "==> macOS app bundle (optional)"
APP_PATH="${HOME}/Applications/AlphaPlus Edge.app"
if [[ -d "${APP_PATH}" ]]; then
  check "AlphaPlus Edge.app installed" test -x "${APP_PATH}/Contents/MacOS/alphaplus-edge"
  echo "      ${APP_PATH}"
else
  echo "SKIP: ${APP_PATH} not installed (run Install command from DMG)"
fi

echo
echo "Summary: ${pass} passed, ${fail} failed"
if [[ "${fail}" -gt 0 ]]; then
  exit 1
fi
echo "OK: Edge macOS verification complete"
