# -*- coding: utf-8 -*-
"""wx-cli tool handler — wraps jackwener/wx-cli for personal WeChat chat data."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from typing import Any, Dict, List, Optional

from core.local_exec.backends.edge_gateway import invoke_wx_via_edge
from core.local_exec.policy import resolve_execution_surface
from core.local_exec.types import LocalToolDomain

logger = logging.getLogger("handler-wx-cli")

WX_BIN = os.environ.get("WX_CLI_BIN", "wx")
DEFAULT_TIMEOUT = int(os.environ.get("WX_CLI_TIMEOUT", "120"))


def _tool(name: str, description: str, properties: Optional[Dict] = None, required: Optional[List[str]] = None):
    schema: Dict[str, Any] = {"type": "object", "properties": properties or {}}
    if required:
        schema["required"] = required
    return {"name": name, "description": description, "inputSchema": schema}


class WxCliToolHandler:
    """Execute wx-cli commands and return JSON payloads for agents."""

    def __init__(self, dep_manager=None):
        self.dep_manager = dep_manager
        self.tools = {
            "wx_daemon_status": _tool(
                "wx_daemon_status",
                "Check wx-cli daemon status (requires wx init on host)",
            ),
            "wx_list_sessions": _tool(
                "wx_list_sessions",
                "List recent WeChat chat sessions",
                {"limit": {"type": "integer", "default": 20}},
            ),
            "wx_get_unread": _tool(
                "wx_get_unread",
                "List sessions with unread messages",
                {
                    "filter": {
                        "type": "string",
                        "description": "Comma-separated: private,group,official_account",
                    }
                },
            ),
            "wx_get_new_messages": _tool(
                "wx_get_new_messages",
                "Incremental new messages since last check",
            ),
            "wx_get_history": _tool(
                "wx_get_history",
                "Fetch chat history for a contact or group",
                {
                    "chat": {"type": "string", "description": "Contact or group display name"},
                    "limit": {"type": "integer", "default": 50},
                    "since": {"type": "string", "description": "YYYY-MM-DD"},
                    "until": {"type": "string", "description": "YYYY-MM-DD"},
                },
                required=["chat"],
            ),
            "wx_search_messages": _tool(
                "wx_search_messages",
                "Search messages across local WeChat DB",
                {
                    "query": {"type": "string"},
                    "chat": {"type": "string", "description": "Optional scope to one chat"},
                    "limit": {"type": "integer", "default": 100},
                    "since": {"type": "string"},
                },
                required=["query"],
            ),
            "wx_list_contacts": _tool(
                "wx_list_contacts",
                "List WeChat contacts",
                {"query": {"type": "string", "description": "Optional name filter"}},
            ),
            "wx_get_members": _tool(
                "wx_get_members",
                "List members of a WeChat group",
                {"group": {"type": "string", "description": "Group display name"}},
                required=["group"],
            ),
        }

    async def list_tools(self) -> List[Dict[str, Any]]:
        return list(self.tools.values())

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        dispatch = {
            "wx_daemon_status": self._daemon_status,
            "wx_list_sessions": self._list_sessions,
            "wx_get_unread": self._get_unread,
            "wx_get_new_messages": self._new_messages,
            "wx_get_history": self._history,
            "wx_search_messages": self._search,
            "wx_list_contacts": self._contacts,
            "wx_get_members": self._members,
        }
        handler = dispatch.get(name)
        if not handler:
            return {"success": False, "error": f"Unknown tool: {name}"}
        return await handler(arguments or {})

    async def _run_wx(self, *args: str, json_output: bool = True, tool_name: str = "wx_invoke") -> Dict[str, Any]:
        surface = resolve_execution_surface(LocalToolDomain.WX_CLI, tool_name=tool_name)
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
        if surface == "forbidden":
            from core.local_exec.policy import direct_dependency_forbidden_message

            return {"success": False, "error": direct_dependency_forbidden_message(LocalToolDomain.WX_CLI)}

        return await self._run_wx_direct(*args, json_output=json_output)

    async def _run_wx_direct(self, *args: str, json_output: bool = True) -> Dict[str, Any]:
        """Direct wx-cli subprocess — only after policy allows ``direct`` surface."""
        if not shutil.which(WX_BIN):
            return {
                "success": False,
                "error": f"{WX_BIN} not found — install: npm i -g @jackwener/wx-cli",
            }
        cmd = [WX_BIN, *args]
        if json_output:
            cmd.append("--json")
        logger.info("wx-cli: %s", " ".join(cmd))
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=DEFAULT_TIMEOUT)
        except asyncio.TimeoutError:
            return {"success": False, "error": f"wx-cli timed out after {DEFAULT_TIMEOUT}s"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            return {
                "success": False,
                "error": err or out or f"exit {proc.returncode}",
                "stderr": err,
            }

        if not out:
            return {"success": True, "data": None, "stderr": err or None}

        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            data = out

        return {"success": True, "data": data, "stderr": err or None}

    async def _daemon_status(self, _: Dict[str, Any]) -> Dict[str, Any]:
        return await self._run_wx("daemon", "status", json_output=False, tool_name="wx_daemon_status")

    async def _list_sessions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(args.get("limit") or 20)
        return await self._run_wx("sessions", "-n", str(limit), tool_name="wx_list_sessions")

    async def _get_unread(self, args: Dict[str, Any]) -> Dict[str, Any]:
        cmd = ["unread"]
        if args.get("filter"):
            cmd.extend(["--filter", str(args["filter"])])
        return await self._run_wx(*cmd, tool_name="wx_get_unread")

    async def _new_messages(self, _: Dict[str, Any]) -> Dict[str, Any]:
        return await self._run_wx("new-messages", tool_name="wx_get_new_messages")

    async def _history(self, args: Dict[str, Any]) -> Dict[str, Any]:
        chat = str(args.get("chat") or "").strip()
        if not chat:
            return {"success": False, "error": "chat is required"}
        cmd = ["history", chat, "-n", str(int(args.get("limit") or 50))]
        if args.get("since"):
            cmd.extend(["--since", str(args["since"])])
        if args.get("until"):
            cmd.extend(["--until", str(args["until"])])
        return await self._run_wx(*cmd, tool_name="wx_get_history")

    async def _search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = str(args.get("query") or "").strip()
        if not query:
            return {"success": False, "error": "query is required"}
        cmd = ["search", query, "-n", str(int(args.get("limit") or 100))]
        if args.get("chat"):
            cmd.extend(["--in", str(args["chat"])])
        if args.get("since"):
            cmd.extend(["--since", str(args["since"])])
        return await self._run_wx(*cmd, tool_name="wx_search_messages")

    async def _contacts(self, args: Dict[str, Any]) -> Dict[str, Any]:
        cmd = ["contacts"]
        if args.get("query"):
            cmd.extend(["--query", str(args["query"])])
        return await self._run_wx(*cmd, tool_name="wx_list_contacts")

    async def _members(self, args: Dict[str, Any]) -> Dict[str, Any]:
        group = str(args.get("group") or "").strip()
        if not group:
            return {"success": False, "error": "group is required"}
        return await self._run_wx("members", group, tool_name="wx_get_members")
