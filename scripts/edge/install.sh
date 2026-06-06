#!/usr/bin/env bash
# Scaffold installer for Edge-local stack (macOS/Linux).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "AlphaPlus Edge installer (scaffold)"
echo "Repo: ${REPO_ROOT}"
echo
echo "This installer will:"
echo "  1. Ensure Python deps (websockets) for tunnel client"
echo "  2. Print env vars for Edge registration"
echo "  3. Start edge health + tunnel via start-edge-stack.sh"
echo

python3 - <<'PY' || pip3 install --user websockets
import websockets  # noqa: F401
print("websockets: OK")
PY

cat <<'EOF'

Recommended env (add to ~/.zshrc or ~/.bashrc):

  export EDGE_ID=local-edge
  export EDGE_DEVICE_TOKEN=dev-edge-token
  export GATEWAY_URL=http://127.0.0.1:8001
  export EDGE_CALLBACK_BASE_URL=http://127.0.0.1:10490
  export VITE_EDGE_HEALTH_URL=http://127.0.0.1:10490/health

Then run:

  bash scripts/edge/start-edge-stack.sh
  bash scripts/edge/edge-doctor.sh

EOF

read -r -p "Start edge stack now? [y/N] " answer
if [[ "${answer}" =~ ^[Yy]$ ]]; then
  bash "${SCRIPT_DIR}/start-edge-stack.sh"
fi
