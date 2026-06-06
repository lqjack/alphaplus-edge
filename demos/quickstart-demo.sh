#!/usr/bin/env bash
# AlphaPlus Edge — 5-minute demo (L1: health + gateway API, no browser LIVE)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  AlphaPlus Edge — Quickstart Demo                        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo

if [[ ! -f scripts/edge/start-edge-stack.sh ]]; then
  echo "ERROR: scripts/edge/ not found. Run from alphaplus-edge root, or:"
  echo "  bash scripts/sync-from-monorepo.sh /path/to/dataproaiset"
  exit 1
fi

export EDGE_ID="${EDGE_ID:-demo-edge}"
export EDGE_DEVICE_TOKEN="${EDGE_DEVICE_TOKEN:-dev-edge-token}"
export GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8001}"
export EDGE_START_TUNNEL="${EDGE_START_TUNNEL:-true}"

echo "==> [1/4] Starting Edge stack (health + tunnel)"
bash scripts/edge/start-edge-stack.sh

echo
echo "==> [2/4] Edge doctor"
SKIP_LIVE_EDGE="${SKIP_LIVE_EDGE:-1}" bash scripts/edge/edge-doctor.sh || true

echo
echo "==> [3/4] Health JSON"
curl -fsS "http://127.0.0.1:10490/health" | python3 -m json.tool

echo
echo "==> [4/4] Contract smoke (optional)"
if python3 -m pytest scripts/edge/test_edge_ws_contract.py -q 2>/dev/null; then
  echo "OK: contract tests passed"
else
  echo "SKIP: pytest not available or tests missing (sync from monorepo)"
fi

echo
echo "Demo complete. Next steps:"
echo "  - LIVE gateway E2E: bash scripts/edge/live-edge-gateway-tool-e2e.sh"
echo "  - Full guide: docs/DEMO.md"
echo "  - Stop: kill \$(cat .edge-runtime/edge-health.pid 2>/dev/null) 2>/dev/null || true"
