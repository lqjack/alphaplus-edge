#!/usr/bin/env bash
# Install AlphaPlus Edge.app + Python runtime on macOS (user scope).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="${SCRIPT_DIR}"

APP_NAME="AlphaPlus Edge.app"
SUPPORT_DIR="${HOME}/Library/Application Support/AlphaPlus-Edge"
RUNTIME_DIR="${SUPPORT_DIR}/runtime"
APPLICATIONS_DIR="${HOME}/Applications"

resolve_app() {
  if [[ -d "${SOURCE_ROOT}/${APP_NAME}" ]]; then
    echo "${SOURCE_ROOT}/${APP_NAME}"
    return 0
  fi
  if [[ -d "${SCRIPT_DIR}/${APP_NAME}" ]]; then
    echo "${SCRIPT_DIR}/${APP_NAME}"
    return 0
  fi
  return 1
}

APP_SRC="$(resolve_app)" || {
  echo "ERROR: ${APP_NAME} not found next to installer." >&2
  exit 1
}

RUNTIME_SRC="${SOURCE_ROOT}/runtime"
if [[ ! -d "${RUNTIME_SRC}" ]]; then
  RUNTIME_SRC="${SCRIPT_DIR}/runtime"
fi
if [[ ! -f "${RUNTIME_SRC}/scripts/edge/edge_health_server.py" ]]; then
  echo "ERROR: runtime bundle missing (scripts/edge/edge_health_server.py)" >&2
  exit 1
fi

echo "==> Installing AlphaPlus Edge"
echo "    App:     ${APPLICATIONS_DIR}/${APP_NAME}"
echo "    Runtime: ${RUNTIME_DIR}"

mkdir -p "${APPLICATIONS_DIR}" "${SUPPORT_DIR}"
rm -rf "${APPLICATIONS_DIR}/${APP_NAME}"
cp -R "${APP_SRC}" "${APPLICATIONS_DIR}/"

rm -rf "${RUNTIME_DIR}"
mkdir -p "${RUNTIME_DIR}"
cp -R "${RUNTIME_SRC}/." "${RUNTIME_DIR}/"

echo "==> Python dependency: websockets (tunnel client)"
python3 -m pip install --user --upgrade 'websockets>=12,<16' >/dev/null 2>&1 || \
  python3 -m pip install --user --upgrade websockets >/dev/null

cat > "${SUPPORT_DIR}/edge.env" <<EOF
# AlphaPlus Edge — loaded by verify script / manual shell
export ALPHAPLUS_REPO_ROOT="${RUNTIME_DIR}"
export EDGE_ID=local-edge
export EDGE_HEALTH_PORT=10490
export EDGE_CALLBACK_BASE_URL=http://127.0.0.1:10490
export VITE_EDGE_HEALTH_URL=http://127.0.0.1:10490/health
# Set your cloud Gateway URL:
# export GATEWAY_URL=https://your-gateway.example.com
EOF

echo ""
echo "Installed successfully."
echo "  1. Open ${APPLICATIONS_DIR}/${APP_NAME}"
echo "  2. Fill Gateway URL + register, or set GATEWAY_URL in:"
echo "     ${SUPPORT_DIR}/edge.env"
echo "  3. Run post-install wizard (recommended):"
echo "     bash \"${RUNTIME_DIR}/scripts/edge/edge-post-install-wizard.sh\""
echo "  4. Or quick verify only:"
echo "     bash \"${RUNTIME_DIR}/scripts/edge/verify-edge-macos.sh\""
echo ""

if [[ "${1:-}" == "--wizard" ]] || [[ "${EDGE_POST_INSTALL_WIZARD:-0}" == "1" ]]; then
  bash "${RUNTIME_DIR}/scripts/edge/edge-post-install-wizard.sh" || true
fi

if [[ "${1:-}" != "--no-open" && "${1:-}" != "--wizard" ]]; then
  open "${APPLICATIONS_DIR}/${APP_NAME}" || true
fi
