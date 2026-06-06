#!/usr/bin/env bash
# Publish alphaplus-edge/ as a new public GitHub repo.
# Prerequisite: fill ASSETS_NEEDED P0 items; replace YOUR_ORG in README.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

ORG="${GITHUB_ORG:-YOUR_ORG}"
REPO="${GITHUB_REPO:-alphaplus-edge}"

if [[ "${ORG}" == "YOUR_ORG" ]]; then
  echo "ERROR: set GITHUB_ORG (e.g. export GITHUB_ORG=lqjack)" >&2
  echo "See docs/ASSETS_NEEDED.md #1" >&2
  exit 1
fi

if grep -rq 'YOUR_ORG' README.md docs/ CHANGELOG.md 2>/dev/null; then
  echo "WARN: README/docs still contain YOUR_ORG — replace before publish (see docs/ASSETS_NEEDED.md #1)"
  if [[ "${FORCE_PUBLISH:-}" != "1" ]]; then
    exit 1
  fi
fi

echo "==> Sync from monorepo (if nested)"
if [[ -f "${ROOT}/../scripts/edge/sync-to-standalone-repo.sh" ]]; then
  bash "${ROOT}/../scripts/edge/sync-to-standalone-repo.sh"
elif [[ -f "${ROOT}/scripts/sync-from-monorepo.sh" ]]; then
  bash "${ROOT}/scripts/sync-from-monorepo.sh" "${ROOT}/.." 2>/dev/null || true
fi

echo "==> Contract smoke"
if command -v pytest >/dev/null 2>&1; then
  python3 -m pytest scripts/edge/test_edge_ws_contract.py -q
fi

if [[ ! -d .git ]]; then
  git init
  git branch -M main
fi

git add -A
git status --short

if ! git diff --cached --quiet 2>/dev/null || [[ -n "$(git status -s)" ]]; then
  git commit -m "$(cat <<EOF
Initial public release: AlphaPlus Edge docs + runtime sync

Standalone export from dataproaiset; monorepo edge paths unchanged.
EOF
)" || true
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create "${ORG}/${REPO}" --public --source=. --remote=origin \
    --description "Local sensitive-data bridge for AlphaPlus research stack (MCP + WSS tunnel)"
fi

git push -u origin main

echo
echo "Published: https://github.com/${ORG}/${REPO}"
echo "Next: gh release create v0.1.0 --notes-file CHANGELOG.md"
echo "Checklist: docs/PUBLISH_CHECKLIST.md"
