#!/usr/bin/env python3
"""CLI entry for Edge LIVE tooling checks (OpenCLI / wx-cli / local MCP)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
DATAPROAI_SRC = REPO_ROOT / "dataproai" / "src"
if str(DATAPROAI_SRC) not in sys.path:
    sys.path.insert(0, str(DATAPROAI_SRC))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from edge_live_checks import run_edge_live_suite, summarize  # noqa: E402


def main() -> int:
    if os.getenv("SKIP_LIVE_EDGE", "").strip().lower() in {"1", "true", "yes"}:
        print("SKIP: SKIP_LIVE_EDGE=1")
        return 0

    print("==> Edge LIVE checks (OpenCLI / wx-cli / local MCP)")
    results = run_edge_live_suite()
    for item in results:
        label = f"{item.status.upper()}: {item.name}"
        if item.detail:
            print(f"{label} — {item.detail}")
        else:
            print(label)

    passed, failed, skipped = summarize(results)
    print()
    print(f"Summary: {passed} passed, {failed} failed, {skipped} skipped")
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
