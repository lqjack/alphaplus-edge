#!/usr/bin/env bash
# Harvest douyin.com cookies from the user's daily browser (no mocks).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DOUYIN_DIR="${REPO_ROOT}/dataproai/src/servers/douyin"
DOUYIN_PY="${DOUYIN_PYTHON:-${REPO_ROOT}/dataproai/.venv/bin/python3}"

if [[ ! -x "${DOUYIN_PY}" ]]; then
  DOUYIN_PY="$(command -v python3)"
fi

cd "${DOUYIN_DIR}"

if [[ "${1:-}" == "--once" ]]; then
  "${DOUYIN_PY}" cookie_harvest.py --once
  exit 0
fi

exec "${DOUYIN_PY}" cookie_harvest.py "$@"
