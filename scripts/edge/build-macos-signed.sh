#!/usr/bin/env bash
# Build and optionally sign/notarize AlphaPlus Edge for macOS.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DESKTOP_DIR="${REPO_ROOT}/edge-desktop"

: "${APPLE_SIGNING_IDENTITY:=Developer ID Application: Your Team (TEAMID)}"
: "${APPLE_NOTarize:=0}"

echo "==> Building AlphaPlus Edge (macOS)"
cd "${DESKTOP_DIR}"
npm install

export APPLE_SIGNING_IDENTITY
if [[ -n "${APPLE_SIGNING_IDENTITY}" && "${APPLE_SIGNING_IDENTITY}" != *"Your Team"* ]]; then
  echo "Signing with: ${APPLE_SIGNING_IDENTITY}"
  npm run build
else
  echo "WARN: APPLE_SIGNING_IDENTITY not configured — building unsigned bundle"
  npm run build
fi

APP_PATH="$(find "${DESKTOP_DIR}/src-tauri/target/release/bundle/macos" -name '*.app' -maxdepth 1 | head -n 1 || true)"
if [[ -z "${APP_PATH}" ]]; then
  echo "ERROR: .app bundle not found under src-tauri/target/release/bundle/macos"
  exit 1
fi

echo "Built: ${APP_PATH}"

if [[ "${APPLE_NOTarize}" == "1" ]]; then
  : "${APPLE_ID:?Set APPLE_ID for notarization}"
  : "${APPLE_APP_SPECIFIC_PASSWORD:?Set APPLE_APP_SPECIFIC_PASSWORD}"
  : "${APPLE_TEAM_ID:?Set APPLE_TEAM_ID}"

  ARCHIVE="${DESKTOP_DIR}/AlphaPlus-Edge.zip"
  echo "==> Notarizing ${APP_PATH}"
  ditto -c -k --keepParent "${APP_PATH}" "${ARCHIVE}"
  xcrun notarytool submit "${ARCHIVE}" \
    --apple-id "${APPLE_ID}" \
    --password "${APPLE_APP_SPECIFIC_PASSWORD}" \
    --team-id "${APPLE_TEAM_ID}" \
    --wait
  xcrun stapler staple "${APP_PATH}"
  echo "Notarized and stapled: ${APP_PATH}"
fi

echo "Done."
