#!/usr/bin/env bash
# Sync Edge runtime from dataproaiset monorepo into alphaplus-edge standalone tree.
# Usage: bash scripts/sync-from-monorepo.sh [MONOREPO_ROOT]
# Default MONOREPO_ROOT: ../  (parent of alphaplus-edge when nested) or ../../ when in monorepo
set -euo pipefail

STANDALONE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -n "${1:-}" ]]; then
  MONOREPO="$(cd "$1" && pwd)"
elif [[ -d "${STANDALONE_ROOT}/../gateway" && -d "${STANDALONE_ROOT}/../scripts/edge" ]]; then
  MONOREPO="$(cd "${STANDALONE_ROOT}/.." && pwd)"
elif [[ -d "${STANDALONE_ROOT}/../../gateway" ]]; then
  MONOREPO="$(cd "${STANDALONE_ROOT}/../.." && pwd)"
else
  echo "ERROR: pass monorepo path: bash scripts/sync-from-monorepo.sh /path/to/dataproaiset" >&2
  exit 1
fi

echo "Standalone: ${STANDALONE_ROOT}"
echo "Monorepo:   ${MONOREPO}"

copy_tree() {
  local src="$1"
  local dst="$2"
  if [[ ! -e "${src}" ]]; then
    echo "WARN: skip missing ${src}"
    return 0
  fi
  mkdir -p "$(dirname "${dst}")"
  rsync -a --delete \
    --exclude '.edge-runtime' \
    --exclude '__pycache__' \
    --exclude '.mcp_venv' \
    --exclude 'target' \
    --exclude '*.log' \
    --exclude '.DS_Store' \
    "${src}/" "${dst}/"
  echo "Synced: ${src} -> ${dst}"
}

# Core edge scripts
copy_tree "${MONOREPO}/scripts/edge" "${STANDALONE_ROOT}/scripts/edge"

# Tauri desktop (exclude build artifacts via rsync exclude above)
copy_tree "${MONOREPO}/edge-desktop" "${STANDALONE_ROOT}/edge-desktop"

# Edge MCP servers (minimal vendored subset for standalone usability)
RUNTIME="${MONOREPO}/neura-runtime"
if [[ ! -d "${RUNTIME}" && -d "${MONOREPO}/dataproai" ]]; then
  RUNTIME="${MONOREPO}/dataproai"
fi

for svc in xiaohongshu wx_cli opencli_weixin wechat_viewer; do
  copy_tree "${RUNTIME}/src/servers/${svc}" "${STANDALONE_ROOT}/servers/${svc}"
done

# Shared core deps used by edge MCP
mkdir -p "${STANDALONE_ROOT}/runtime-core"
copy_tree "${RUNTIME}/src/core" "${STANDALONE_ROOT}/runtime-core/core"

# Marketing screenshots (CLS closed-loop demo)
ASSET_SRC="${MONOREPO}/docs/assets/alphaplus"
mkdir -p "${ASSET_SRC}"
# Normalize raw drops in docs/alphaplus*.png → standardized names
_raw01="${MONOREPO}/docs/alphaplus01.png"
[[ -f "${_raw01}" ]] || _raw01="${MONOREPO}/docs/alphapluus01.png"
[[ -f "${_raw01}" ]] && cp -f "${_raw01}" "${ASSET_SRC}/alphaplus01-content-hub.png"
[[ -f "${MONOREPO}/docs/alphaplus02.png" ]] && cp -f "${MONOREPO}/docs/alphaplus02.png" "${ASSET_SRC}/alphaplus02-strategy.png"
[[ -f "${MONOREPO}/docs/alphaplus03.png" ]] && cp -f "${MONOREPO}/docs/alphaplus03.png" "${ASSET_SRC}/alphaplus03-audit-cls-trace.png"

if [[ -d "${ASSET_SRC}" ]]; then
  mkdir -p "${STANDALONE_ROOT}/assets/screenshots"
  rsync -a "${MONOREPO}/docs/assets/alphaplus/"*.png "${STANDALONE_ROOT}/assets/screenshots/" 2>/dev/null || true
  cp -f "${MONOREPO}/docs/assets/alphaplus/README.md" "${STANDALONE_ROOT}/assets/screenshots/README.md" 2>/dev/null || true
  echo "Synced: docs/assets/alphaplus -> assets/screenshots"
fi

# Gateway edge config reference
mkdir -p "${STANDALONE_ROOT}/config"
cp -f "${MONOREPO}/gateway/config/edge_tools.yaml" "${STANDALONE_ROOT}/config/edge_tools.yaml" 2>/dev/null || true

# Patch edge-mcp-lib paths for standalone layout (if servers/ exists)
LIB="${STANDALONE_ROOT}/scripts/edge/edge-mcp-lib.sh"
if [[ -f "${LIB}" ]] && grep -q 'dataproai/src/servers' "${LIB}"; then
  sed -i.bak \
    -e "s|\${repo_root}/dataproai/src/servers|\${repo_root}/servers|g" \
    -e "s|\${repo_root}/dataproai/src|\${repo_root}/runtime-core|g" \
    -e "s|\${repo_root}/dataproai/.venv|\${repo_root}/.venv|g" \
    "${LIB}"
  rm -f "${LIB}.bak"
  echo "Patched edge-mcp-lib.sh for standalone paths"
fi

echo
echo "Sync complete. Verify:"
echo "  bash demos/quickstart-demo.sh"
echo "  python3 -m pytest scripts/edge/test_edge_ws_contract.py -q"
