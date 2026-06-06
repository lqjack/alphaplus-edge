# Contributing to AlphaPlus Edge

Thanks for improving the local Edge bridge. This repo syncs from [dataproaiset](https://github.com/lqjack/dataproaiset); prefer fixing runtime bugs in monorepo `scripts/edge/` then re-sync.

## Development setup

```bash
git clone https://github.com/lqjack/alphaplus-edge.git
cd alphaplus-edge
bash scripts/sync-from-monorepo.sh ../dataproaiset   # if you have monorepo checkout
cp .env.example .env.edge
bash demos/quickstart-demo.sh
```

## Pull requests

1. Fork and branch from `main`
2. Run contract tests: `python3 -m pytest scripts/edge/test_edge_*_contract.py -q`
3. Update `CHANGELOG.md` under `[Unreleased]`
4. No secrets, cookies, or `.edge-runtime/` in commits

## Reporting issues

Use GitHub Issues with:

- OS / arch
- `bash scripts/edge/edge-doctor.sh` output (redact tokens)
- Gateway URL (not token)

## Code of conduct

Be respectful; no harassment. Research tooling community standards apply.
