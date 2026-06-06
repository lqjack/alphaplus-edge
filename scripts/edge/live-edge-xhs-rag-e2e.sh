#!/usr/bin/env bash
# LIVE: Xiaohongshu share → stock-flow → RAG (Edge xhs MCP + cloud stack). No mocks.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ "${SKIP_LIVE_EDGE_RAG:-0}" == "1" ]]; then
  echo "SKIP: SKIP_LIVE_EDGE_RAG=1"
  exit 0
fi

require_url() {
  local url="$1"
  local label="$2"
  if ! curl -sf --max-time 5 "${url}" >/dev/null 2>&1; then
    echo "ERROR: ${label} not reachable — ${url}" >&2
    echo "Hint: bash scripts/edge/start-mac-rag-stack.sh && bash scripts/edge/start-edge-mcp.sh" >&2
    exit 1
  fi
}

if [[ "${1:-}" == "--check-env" ]]; then
  if [[ -z "${XHS_LIVE_SHARE_URL:-}" && -z "${XHS_LIVE_SHARE_TEXT:-}" ]]; then
    echo "ERROR: set XHS_LIVE_SHARE_URL or XHS_LIVE_SHARE_TEXT (real note URL / share text)" >&2
    exit 1
  fi
  echo "OK: share input configured"
  exit 0
fi

if [[ "${1:-}" == "--check-stack" ]]; then
  echo "==> Edge xhs→RAG stack readiness (no share URL required)"
  require_url "http://127.0.0.1:10350/health" "xiaohongshu MCP"
  require_url "http://127.0.0.1:10000/health" "dataproai_backend"
  require_url "http://127.0.0.1:50000/health" "stock_backend"
  require_url "http://127.0.0.1:10520/api/rag/health" "shared_rag"
  require_url "http://127.0.0.1:${ALPHAPLUS_GATEWAY_PORT:-8001}/health" "gateway"
  require_url "http://127.0.0.1:10001/health" "skills_api"
  require_url "http://127.0.0.1:10300/health" "ai"
  echo "OK: cloud+edge stack ready for xhs RAG LIVE (set XHS_LIVE_SHARE_URL for full E2E)"
  exit 0
fi

if [[ "${1:-}" == "--check-auth" ]]; then
  echo "==> Edge xhs auth readiness (browser cookies, no mocks)"
  if ! bash "${SCRIPT_DIR}/harvest-xhs-cookies.sh" --once; then
    echo "ERROR: log into xiaohongshu.com in Chrome/Safari, then re-run:" >&2
    echo "  bash scripts/edge/harvest-xhs-cookies.sh --once" >&2
    exit 1
  fi
  echo "OK: xiaohongshu session cookies harvested"
  exit 0
fi

ensure_xhs_auth() {
  if [[ "${SKIP_XHS_COOKIE_HARVEST:-0}" == "1" ]]; then
    echo "SKIP: SKIP_XHS_COOKIE_HARVEST=1"
    return 0
  fi
  echo "==> Harvest xiaohongshu browser cookies"
  if ! bash "${SCRIPT_DIR}/harvest-xhs-cookies.sh" --once; then
    echo "ERROR: xhs login required before LIVE E2E. Steps:" >&2
    echo "  1. Open https://www.xiaohongshu.com in Chrome or Safari and log in" >&2
    echo "  2. bash scripts/edge/harvest-xhs-cookies.sh --once" >&2
    echo "  3. Re-run with XHS_LIVE_SHARE_URL=..." >&2
    exit 1
  fi
}

echo "==> Edge xhs→RAG LIVE E2E prerequisites"
require_url "http://127.0.0.1:10350/health" "xiaohongshu MCP"
require_url "http://127.0.0.1:10000/health" "dataproai_backend"
require_url "http://127.0.0.1:50000/health" "stock_backend"
require_url "http://127.0.0.1:10520/api/rag/health" "shared_rag"
require_url "http://127.0.0.1:${ALPHAPLUS_GATEWAY_PORT:-8001}/health" "gateway"

if [[ -z "${XHS_LIVE_SHARE_URL:-}" && -z "${XHS_LIVE_SHARE_TEXT:-}" ]]; then
  echo "ERROR: set XHS_LIVE_SHARE_URL or XHS_LIVE_SHARE_TEXT (real note URL / share text)" >&2
  exit 1
fi

ensure_xhs_auth

ARGS=()
if [[ -n "${XHS_LIVE_SHARE_URL:-}" ]]; then
  ARGS+=(--url "${XHS_LIVE_SHARE_URL}")
fi
if [[ -n "${XHS_LIVE_SHARE_TEXT:-}" ]]; then
  ARGS+=(--share-text "${XHS_LIVE_SHARE_TEXT}")
fi

export STOCK_EDGE_ROUTING="${STOCK_EDGE_ROUTING:-auto}"
cd "${REPO_ROOT}"
exec python3 scripts/live_xiaohongshu_share_to_stock_e2e.py "${ARGS[@]}" "$@"
