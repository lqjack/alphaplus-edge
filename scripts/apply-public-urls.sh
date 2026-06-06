#!/usr/bin/env bash
# Replace YOUR_ORG and Edge Gateway URLs in docs/README for public publish.
# NeuraDesk (gateway.datapro.asia :3000) is NOT rewritten — only Neura Gateway Edge API.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

ORG="${GITHUB_ORG:-lqjack}"
REPO="${GITHUB_REPO:-alphaplus-edge}"
GATEWAY_PUBLIC="${GATEWAY_PUBLIC_URL:-https://alphaplus-api.datapro.asia}"

echo "==> apply-public-urls org=${ORG} repo=${REPO}"
echo "    GATEWAY_PUBLIC_URL (Edge API)=${GATEWAY_PUBLIC}"

replace_org() {
  local f="$1"
  [[ -f "${f}" ]] || return 0
  sed -i \
    -e "s|YOUR_ORG|${ORG}|g" \
    -e "s|github.com/YOUR_ORG/alphaplus-edge|github.com/${ORG}/${REPO}|g" \
    "${f}"
}

replace_edge_gateway() {
  local f="$1"
  [[ -f "${f}" ]] || return 0
  sed -i \
    -e "s|CLOUD_GATEWAY_URL=https://gateway.datapro.asia|CLOUD_GATEWAY_URL=${GATEWAY_PUBLIC}|g" \
    -e "s|GATEWAY_PUBLIC_URL=https://gateway.datapro.asia|GATEWAY_PUBLIC_URL=${GATEWAY_PUBLIC}|g" \
    -e "s|export GATEWAY_URL=https://gateway.datapro.asia|export GATEWAY_URL=${GATEWAY_PUBLIC}|g" \
    -e "s|Gateway URL: https://gateway.datapro.asia|Gateway URL: ${GATEWAY_PUBLIC}|g" \
    "${f}"
}

for f in README.md CHANGELOG.md docs/README.md docs/MARKETING_PLAN.md docs/ASSETS_NEEDED.md \
  docs/DEMO.md docs/NARRATIVE.md docs/delivery/*.md; do
  replace_org "${f}"
done

for f in .env.example docs/CLOUD_INTEGRATION.md docs/ASSETS_NEEDED.md README.md; do
  replace_edge_gateway "${f}"
  replace_org "${f}"
done

chmod +x "${ROOT}/scripts/publish-to-github.sh" 2>/dev/null || true

echo "OK: review git diff — LAUNCH_PLAYBOOK.md keeps NeuraDesk vs Edge URL table as-is"
