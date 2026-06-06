#!/usr/bin/env bash
# Harvest wechat/mp.weixin.qq.com cookies from the user's daily browser (no mocks).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WECHAT_DIR="${REPO_ROOT}/dataproai/src/servers/wechat"
WECHAT_PY="${WECHAT_PYTHON:-${REPO_ROOT}/dataproai/.venv/bin/python3}"

if [[ ! -x "${WECHAT_PY}" ]]; then
  WECHAT_PY="$(command -v python3)"
fi

cd "${WECHAT_DIR}"

if [[ "${1:-}" == "--once" ]]; then
  "${WECHAT_PY}" cookie_harvest.py --once
  if [[ -f cookie_bridge.py ]]; then
    "${WECHAT_PY}" -c "from cookie_bridge import apply_harvest_to_settings; n=apply_harvest_to_settings(); print(f'applied {n} cookies')"
  fi
  exit 0
fi

exec "${WECHAT_PY}" cookie_harvest.py "$@"
