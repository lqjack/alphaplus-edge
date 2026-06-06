"""Resolve where OpenCLI / wx-cli may execute."""

from __future__ import annotations

import os

from core.gateway_policy import dev_allow_direct_server
from core.local_exec.types import ExecutionSurface, LocalToolDomain, is_user_private_tool


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def gateway_deployment_profile() -> str:
    return os.getenv("GATEWAY_DEPLOYMENT_PROFILE", "cloud-only").strip().lower()


def edge_mode() -> str:
    return os.getenv("EDGE_MODE", "").strip().lower()


def is_private_or_edge_host() -> bool:
    profile = gateway_deployment_profile()
    mode = edge_mode()
    if mode in {"local", "edge"}:
        return True
    if profile in {"private", "edge-user", "edge", "standalone", "team-private"}:
        return True
    if _truthy("PRIVATE_DEPLOY"):
        return True
    return False


def allow_direct_opencli() -> bool:
    if _truthy("ALLOW_DIRECT_OPENCLI"):
        return True
    if dev_allow_direct_server() and _truthy("DEV_ALLOW_DIRECT_OPENCLI"):
        return True
    if is_private_or_edge_host() and _truthy("PRIVATE_ALLOW_DIRECT_OPENCLI"):
        return True
    # Running MCP on the user's machine (edge stack) — process is already local.
    if is_private_or_edge_host():
        return True
    return False


def allow_direct_wx_cli() -> bool:
    """wx-cli reads local WeChat DB — never on shared cloud by default."""
    if _truthy("ALLOW_DIRECT_WX_CLI"):
        return True
    if dev_allow_direct_server() and _truthy("DEV_ALLOW_DIRECT_WX_CLI"):
        return True
    if is_private_or_edge_host():
        return True
    return False


def configured_surface_override() -> ExecutionSurface | None:
    raw = os.getenv("LOCAL_EXEC_SURFACE", "").strip().lower()
    if raw in {"runner", "edge", "direct", "forbidden"}:
        return raw  # type: ignore[return-value]
    return None


def resolve_execution_surface(
    domain: LocalToolDomain,
    *,
    tool_name: str = "",
) -> ExecutionSurface:
    """Pick runner/edge/direct/forbidden for a local tool invocation."""
    override = configured_surface_override()
    if override:
        if override == "direct":
            if domain == LocalToolDomain.WX_CLI and not allow_direct_wx_cli():
                return "forbidden"
            if domain == LocalToolDomain.OPENCLI and not allow_direct_opencli():
                return "forbidden"
        return override

    if domain == LocalToolDomain.WX_CLI:
        if allow_direct_wx_cli():
            return "direct"
        if _truthy("LOCAL_EXEC_VIA_RUNNER") or os.getenv("LOCAL_EXEC_RUNNER_ID", "").strip():
            return "runner"
        if os.getenv("GATEWAY_PUBLIC_URL") or os.getenv("DATAPROAI_GATEWAY_URL"):
            return "edge"
        return "forbidden"

    # OPENCLI
    if is_user_private_tool(tool_name) and not allow_direct_opencli():
        if _truthy("LOCAL_EXEC_VIA_RUNNER") or os.getenv("LOCAL_EXEC_RUNNER_ID", "").strip():
            return "runner"
        if os.getenv("GATEWAY_PUBLIC_URL") or os.getenv("DATAPROAI_GATEWAY_URL"):
            return "edge"
        return "forbidden"

    if allow_direct_opencli():
        return "direct"

    if os.getenv("GATEWAY_PUBLIC_URL") or os.getenv("DATAPROAI_GATEWAY_URL"):
        return "edge"

    return "forbidden"


def direct_dependency_forbidden_message(domain: LocalToolDomain) -> str:
    if domain == LocalToolDomain.WX_CLI:
        return (
            "Direct wx-cli is disabled on this host. "
            "Bind NeuraRunner or route via Gateway Edge "
            "(set ALLOW_DIRECT_WX_CLI=1 only on private user machines)."
        )
    return (
        "Direct OpenCLI is disabled on this host. "
        "Configure NeuraRunner in NeuraDesk or use Gateway Edge forwarding "
        "(set ALLOW_DIRECT_OPENCLI=1 or PRIVATE_DEPLOY on private hosts only)."
    )
