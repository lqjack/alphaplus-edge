#!/usr/bin/env bash
# Post-DMG install wizard — real HTTP/MCP checks (no mocks). Safe to re-run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SUPPORT_ENV="${HOME}/Library/Application Support/AlphaPlus-Edge/edge.env"

if [[ -f "${SUPPORT_ENV}" ]]; then
  # shellcheck disable=SC1090
  source "${SUPPORT_ENV}"
fi

export ALPHAPLUS_REPO_ROOT="${ALPHAPLUS_REPO_ROOT:-${REPO_ROOT}}"
export EDGE_ID="${EDGE_ID:-local-edge}"
export EDGE_HEALTH_PORT="${EDGE_HEALTH_PORT:-10490}"
export EDGE_CALLBACK_BASE_URL="${EDGE_CALLBACK_BASE_URL:-http://127.0.0.1:${EDGE_HEALTH_PORT}}"
export GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:${ALPHAPLUS_GATEWAY_PORT:-8001}}"
export PYTHONPATH="${ALPHAPLUS_REPO_ROOT}/dataproai/src:${PYTHONPATH:-}"

pass=0
fail=0
skip=0

step_pass() { echo "PASS: $*"; pass=$((pass + 1)); }
step_fail() { echo "FAIL: $*" >&2; fail=$((fail + 1)); }
step_skip() { echo "SKIP: $*"; skip=$((skip + 1)); }

echo "==> AlphaPlus Edge post-install wizard"
echo "    runtime: ${ALPHAPLUS_REPO_ROOT}"
echo "    health:  ${EDGE_CALLBACK_BASE_URL}"
echo "    gateway: ${GATEWAY_URL}"
echo

APP_PATH="${HOME}/Applications/AlphaPlus Edge.app"
if [[ -d "${APP_PATH}" ]]; then
  step_pass "AlphaPlus Edge.app installed"
else
  step_skip "${APP_PATH} not found — install from DMG first"
fi

if [[ -f "${SUPPORT_ENV}" ]]; then
  step_pass "edge.env present (${SUPPORT_ENV})"
else
  step_skip "edge.env missing — run Install AlphaPlus Edge.command"
fi

echo
echo "==> Edge doctor"
if bash "${SCRIPT_DIR}/edge-doctor.sh"; then
  step_pass "edge-doctor completed"
else
  step_fail "edge-doctor reported issues"
fi

echo
echo "==> Edge MCP (four services)"
if bash "${SCRIPT_DIR}/start-edge-mcp.sh" >/tmp/alphaplus-edge-mcp-wizard.log 2>&1; then
  if bash "${SCRIPT_DIR}/verify-edge-mcp.sh"; then
    step_pass "Edge MCP health 4/4"
  else
    step_fail "verify-edge-mcp.sh — see /tmp/alphaplus-edge-mcp-wizard.log"
  fi
else
  step_fail "start-edge-mcp.sh — see /tmp/alphaplus-edge-mcp-wizard.log"
fi

echo
echo "==> Gateway (optional)"
if curl -sf --max-time 3 "${GATEWAY_URL}/health" >/dev/null 2>&1; then
  step_pass "Gateway reachable"
  if bash "${SCRIPT_DIR}/register-with-gateway.sh" >/tmp/alphaplus-edge-register-wizard.log 2>&1; then
    step_pass "Gateway device register"
  else
    step_skip "register failed — set GATEWAY_URL / EDGE_DEVICE_TOKEN in edge.env"
  fi
else
  step_skip "Gateway down — run: bash scripts/edge/start-mac-gateway.sh"
fi

echo
echo "==> LIVE probes (OpenCLI / wx-cli)"
if [[ "${SKIP_LIVE_EDGE:-0}" == "1" ]]; then
  step_skip "SKIP_LIVE_EDGE=1"
elif bash "${SCRIPT_DIR}/verify-edge-live.sh"; then
  step_pass "verify-edge-live.sh"
else
  step_skip "LIVE tools not ready — install opencli / wx-cli; re-run wizard"
fi

echo
echo "==> Cookie harvest (human browser login)"
echo "    WeChat MP:  bash scripts/edge/harvest-wechat-cookies.sh --once"
echo "    XHS:        bash scripts/edge/harvest-xhs-cookies.sh --once"
echo "    Full xhs→RAG: XHS_LIVE_SHARE_URL=... bash scripts/edge/live-edge-xhs-rag-e2e.sh"

echo
echo "==> Final macOS verify"
if bash "${SCRIPT_DIR}/verify-edge-macos.sh"; then
  step_pass "verify-edge-macos.sh"
else
  step_fail "verify-edge-macos.sh"
fi

echo
echo "Wizard summary: ${pass} passed, ${fail} failed, ${skip} skipped"
if [[ "${fail}" -gt 0 ]]; then
  exit 1
fi
echo "OK: post-install wizard complete (fix skipped ops items manually if needed)"
