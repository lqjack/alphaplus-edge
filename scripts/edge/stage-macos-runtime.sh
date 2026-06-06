#!/usr/bin/env bash
# Stage minimal Edge Python runtime for macOS install bundle (no MCP server data).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
STAGE_DIR="${1:-${REPO_ROOT}/dist/edge-macos-runtime}"

echo "==> Staging Edge runtime -> ${STAGE_DIR}"
rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}/scripts/edge" \
  "${STAGE_DIR}/dataproai/src/core" \
  "${STAGE_DIR}/dataproai/resources"

rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "${REPO_ROOT}/scripts/edge/" "${STAGE_DIR}/scripts/edge/"

rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "${REPO_ROOT}/dataproai/src/core/" "${STAGE_DIR}/dataproai/src/core/"

cp "${REPO_ROOT}/dataproai/resources/service_ports.json" \
  "${STAGE_DIR}/dataproai/resources/service_ports.json"

touch "${STAGE_DIR}/dataproai/src/__init__.py"

cat > "${STAGE_DIR}/VERSION.txt" <<EOF
alphaplus-edge-runtime
built_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
source_repo=${REPO_ROOT}
EOF

echo "OK: runtime staged ($(du -sh "${STAGE_DIR}" | awk '{print $1}'))"
