#!/usr/bin/env bash
# LIVE Edge tooling verification — real opencli doctor / wx-cli / local MCP (no mocks).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

export ALPHAPLUS_REPO_ROOT="${ALPHAPLUS_REPO_ROOT:-${REPO_ROOT}}"
export PYTHONPATH="${ALPHAPLUS_REPO_ROOT}/dataproai/src:${PYTHONPATH:-}"

if [[ "${SKIP_LIVE_EDGE:-0}" == "1" ]]; then
  echo "SKIP: SKIP_LIVE_EDGE=1"
  exit 0
fi

python3 "${SCRIPT_DIR}/verify_edge_live.py"
