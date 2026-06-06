#!/usr/bin/env bash
# Export monorepo Edge assets into alphaplus-edge/ (in-repo standalone tree).
# Does NOT remove or modify scripts/edge/ or edge-desktop/ in monorepo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STANDALONE="${REPO_ROOT}/alphaplus-edge"

if [[ ! -d "${STANDALONE}" ]]; then
  echo "ERROR: ${STANDALONE} not found" >&2
  exit 1
fi

bash "${STANDALONE}/scripts/sync-from-monorepo.sh" "${REPO_ROOT}"

echo
echo "Monorepo edge unchanged. Standalone tree updated at: ${STANDALONE}"
echo "Publish: see alphaplus-edge/docs/PUBLISH_CHECKLIST.md"
