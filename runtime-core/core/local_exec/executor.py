"""Local tool executor — OpenCLI / wx-cli with policy-gated backends."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.local_exec.backends.edge_gateway import invoke_opencli_via_edge, invoke_wx_via_edge
from core.local_exec.policy import (
    direct_dependency_forbidden_message,
    resolve_execution_surface,
)
from core.local_exec.types import LocalToolDomain

logger = logging.getLogger("local-exec")


class LocalToolExecutor:
    """
    Single entry for host-local CLI tools.

    Handlers must not import OpenCLIClient or spawn wx-cli directly — use this class.
    """

    def __init__(self, *, opencli_session: Optional[str] = None):
        self._opencli_session = opencli_session
        self._opencli_client = None
        self._wx_handler = None

    def _get_opencli_client(self):
        if self._opencli_client is None:
            from shared.opencli_client import OpenCLIClient

            self._opencli_client = OpenCLIClient(session=self._opencli_session)
        return self._opencli_client

    def _get_wx_handler(self):
        if self._wx_handler is None:
            from servers.wx_cli.handlers.tool_handler import WxCliToolHandler

            self._wx_handler = WxCliToolHandler()
        return self._wx_handler

    async def opencli_run(
        self,
        *args: str,
        fmt: Optional[str] = None,
        timeout: Optional[int] = None,
        tool_name: str = "opencli_invoke",
    ) -> Dict[str, Any]:
        surface = resolve_execution_surface(LocalToolDomain.OPENCLI, tool_name=tool_name)
        if surface == "forbidden":
            return {"success": False, "error": direct_dependency_forbidden_message(LocalToolDomain.OPENCLI)}

        if surface == "edge":
            return await invoke_opencli_via_edge(
                tool_name,
                {"argv": list(args), "format": fmt, "timeout": timeout},
            )

        if surface == "runner":
            return {
                "success": False,
                "error": (
                    "Runner delegation must be initiated from NeuraDesk "
                    "(POST /api/gateway/runners/:id/invoke with local_exec). "
                    "NeuraDesk falls back to Edge when no runner is online."
                ),
                "code": "RUNNER_DELEGATE_FROM_DESK",
            }

        client = self._get_opencli_client()
        return await client.run(*args, fmt=fmt, timeout=timeout)

    async def wx_run(
        self,
        *args: str,
        json_output: bool = True,
        tool_name: str = "wx_invoke",
    ) -> Dict[str, Any]:
        surface = resolve_execution_surface(LocalToolDomain.WX_CLI, tool_name=tool_name)
        if surface == "forbidden":
            return {"success": False, "error": direct_dependency_forbidden_message(LocalToolDomain.WX_CLI)}

        if surface == "edge":
            return await invoke_wx_via_edge(
                tool_name,
                {"argv": list(args), "json_output": json_output},
            )

        if surface == "runner":
            return {
                "success": False,
                "error": (
                    "wx-cli must run on NeuraRunner (user machine). "
                    "Configure runner in NeuraDesk and invoke via local_exec."
                ),
                "code": "RUNNER_DELEGATE_FROM_DESK",
            }

        handler = self._get_wx_handler()
        return await handler._run_wx_direct(*args, json_output=json_output)
