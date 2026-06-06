#!/usr/bin/env bash
# Harvest xiaohongshu cookies from the user's daily browser (no mocks).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
XHS_DIR="${REPO_ROOT}/dataproai/src/servers/xiaohongshu"
XHS_PY="${XHS_PYTHON:-${XHS_DIR}/.mcp_venv/bin/python3.12}"

if [[ ! -x "${XHS_PY}" ]]; then
  echo "ERROR: ${XHS_PY} missing — run bash scripts/edge/start-edge-mcp.sh first" >&2
  exit 1
fi

cd "${XHS_DIR}"

if [[ "${1:-}" == "--once" ]]; then
  "${XHS_PY}" cookie_harvest.py --once
  "${XHS_PY}" -c "from cookie_bridge import apply_harvest_to_settings; n=apply_harvest_to_settings(); print(f'applied {n} cookies to settings.yaml')"
  exit 0
fi

exec "${XHS_PY}" cookie_harvest.py "$@"
