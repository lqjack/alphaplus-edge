"""Policy-gated local tool execution (OpenCLI, wx-cli)."""

from core.local_exec.policy import (
    allow_direct_opencli,
    allow_direct_wx_cli,
    resolve_execution_surface,
)
from core.local_exec.types import LocalToolDomain, is_user_private_tool

__all__ = [
    "LocalToolDomain",
    "LocalToolExecutor",
    "allow_direct_opencli",
    "allow_direct_wx_cli",
    "is_user_private_tool",
    "resolve_execution_surface",
]


def __getattr__(name: str):
    if name == "LocalToolExecutor":
        from core.local_exec.executor import LocalToolExecutor

        return LocalToolExecutor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
