#!/usr/bin/env bash
# LIVE: Gateway → Edge callback → local MCP (xiaohongshu / wx_cli).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

export ALPHAPLUS_REPO_ROOT="${ALPHAPLUS_REPO_ROOT:-${REPO_ROOT}}"
export PYTHONPATH="${ALPHAPLUS_REPO_ROOT}/dataproai/src:${PYTHONPATH:-}"
export GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8001}"
export EDGE_CALLBACK_BASE_URL="${EDGE_CALLBACK_BASE_URL:-http://127.0.0.1:10490}"
export EDGE_ID="${EDGE_ID:-local-edge}"

if [[ "${SKIP_LIVE_EDGE:-0}" == "1" ]]; then
  echo "SKIP: SKIP_LIVE_EDGE=1"
  exit 0
fi

python3 "${SCRIPT_DIR}/live_edge_gateway_tool_e2e.py" "$@"
