"""Local tool execution — domain and surface types."""

from __future__ import annotations

from enum import Enum
from typing import Literal

ExecutionSurface = Literal["runner", "edge", "direct", "forbidden"]


class LocalToolDomain(str, Enum):
    """Host-local CLI families — never assume present on cloud servers."""

    OPENCLI = "opencli"
    WX_CLI = "wx_cli"


# Tools that read user-local private data (WeChat DB, logged-in browser, etc.)
USER_PRIVATE_TOOL_PREFIXES: tuple[str, ...] = (
    "wx_",
    "weixin_",
    "wechat_",
    "browser_",
    "opencli_",
)

# OpenCLI tools safe to run on a shared server (none by default — extend explicitly).
SERVER_GENERIC_OPENCLI_TOOLS: frozenset[str] = frozenset()


def is_user_private_tool(tool_name: str) -> bool:
    name = (tool_name or "").strip()
    if name.startswith("wx_"):
        return True
    if name in SERVER_GENERIC_OPENCLI_TOOLS:
        return False
    return any(name.startswith(prefix) for prefix in USER_PRIVATE_TOOL_PREFIXES)
