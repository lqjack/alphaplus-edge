#!/usr/bin/env bash
# Build AlphaPlus Edge macOS .app + .dmg + staged runtime for distribution.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DESKTOP_DIR="${REPO_ROOT}/edge-desktop"
DIST_DIR="${REPO_ROOT}/dist/edge-macos"
RUNTIME_STAGE="${DIST_DIR}/runtime"
DMG_NAME="AlphaPlus-Edge-0.1.0-macos.dmg"

echo "==> AlphaPlus Edge macOS installer build"
mkdir -p "${DIST_DIR}"

echo "==> App icon"
python3 "${SCRIPT_DIR}/generate_app_icon.py"
cd "${DESKTOP_DIR}"
npm install
npx tauri icon app-icon.png

echo "==> Tauri release build (app bundle only — DMG via hdiutil below)"
export ALPHAPLUS_REPO_ROOT="${REPO_ROOT}"
npm run build -- --bundles app

BUNDLE_DIR="${DESKTOP_DIR}/src-tauri/target/release/bundle/macos"
APP_PATH="${BUNDLE_DIR}/AlphaPlus Edge.app"
if [[ ! -d "${APP_PATH}" ]]; then
  APP_PATH="$(find "${BUNDLE_DIR}" -maxdepth 1 -name 'AlphaPlus Edge.app' -print -quit || true)"
fi
if [[ -z "${APP_PATH}" || ! -d "${APP_PATH}" ]]; then
  echo "ERROR: AlphaPlus Edge.app not found under ${BUNDLE_DIR}" >&2
  exit 1
fi
# Remove legacy bundle from prior branding if present.
rm -rf "${BUNDLE_DIR}/Invest-AI Edge.app" 2>/dev/null || true

echo "==> Stage Python runtime"
bash "${SCRIPT_DIR}/stage-macos-runtime.sh" "${RUNTIME_STAGE}"

PKG_ROOT="${DIST_DIR}/package-root"
rm -rf "${PKG_ROOT}"
mkdir -p "${PKG_ROOT}"
cp -R "${APP_PATH}" "${PKG_ROOT}/"
cp -R "${RUNTIME_STAGE}" "${PKG_ROOT}/runtime"
cp "${SCRIPT_DIR}/install-macos.sh" "${PKG_ROOT}/Install AlphaPlus Edge.command"
chmod +x "${PKG_ROOT}/Install AlphaPlus Edge.command"

echo "==> Create DMG"
DMG_PATH="${DIST_DIR}/${DMG_NAME}"
rm -f "${DMG_PATH}"
hdiutil create \
  -volname "AlphaPlus Edge" \
  -srcfolder "${PKG_ROOT}" \
  -ov \
  -format UDZO \
  "${DMG_PATH}" >/dev/null

echo ""
echo "Built artifacts:"
echo "  App:  ${APP_PATH}"
echo "  DMG:  ${DMG_PATH}"
echo "  Runtime: ${RUNTIME_STAGE}"
echo ""
echo "Install (local test):"
echo "  open \"${DMG_PATH}\""
echo "  # then double-click \"Install AlphaPlus Edge.command\""
echo ""
echo "Verify:"
echo "  bash scripts/edge/verify-edge-macos.sh"
