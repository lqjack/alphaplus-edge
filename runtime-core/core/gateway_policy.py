"""Gateway routing policy — server inter-call must go via Gateway unless dev override."""

from __future__ import annotations

import os


def dev_allow_direct_server() -> bool:
    """Allow DirectAPIToolInvoker / direct MCP executor calls (local dev/tests only)."""
    return os.getenv("DEV_ALLOW_DIRECT_SERVER", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
