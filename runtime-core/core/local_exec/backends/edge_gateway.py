"""Forward local tool calls to Neura Gateway Edge API."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("local-exec.edge")

EDGE_SERVER_BY_DOMAIN = {
    "opencli": "opencli_weixin",
    "wx_cli": "wx_cli",
}


def _gateway_base() -> str:
    for key in ("DATAPROAI_GATEWAY_URL", "GATEWAY_PUBLIC_URL", "GATEWAY_URL"):
        value = os.getenv(key, "").strip().rstrip("/")
        if value:
            return value
    return "http://127.0.0.1:8001"


async def invoke_edge_tool(
    *,
    server: str,
    tool_name: str,
    arguments: Dict[str, Any],
    edge_id: str = "",
    timeout_seconds: float = 180.0,
) -> Dict[str, Any]:
    url = f"{_gateway_base()}/api/edge/tools/call"
    payload = {
        "edge_id": edge_id,
        "server": server,
        "name": tool_name,
        "arguments": arguments,
        "timeout_seconds": timeout_seconds,
    }
    logger.info("edge_gateway: POST %s server=%s tool=%s", url, server, tool_name)
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds + 5, trust_env=False) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 409:
                detail = response.text
                try:
                    detail = response.json().get("detail", detail)
                except Exception:
                    pass
                return {
                    "success": False,
                    "error": str(detail),
                    "code": "EDGE_OFFLINE",
                }
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data
            return {"success": True, "data": data}
    except httpx.HTTPError as exc:
        return {"success": False, "error": str(exc), "code": "EDGE_HTTP_ERROR"}


async def invoke_opencli_via_edge(
    tool_name: str,
    arguments: Dict[str, Any],
    *,
    server: Optional[str] = None,
) -> Dict[str, Any]:
    target = server or EDGE_SERVER_BY_DOMAIN["opencli"]
    return await invoke_edge_tool(server=target, tool_name=tool_name, arguments=arguments)


async def invoke_wx_via_edge(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    return await invoke_edge_tool(
        server=EDGE_SERVER_BY_DOMAIN["wx_cli"],
        tool_name=tool_name,
        arguments=arguments,
    )
