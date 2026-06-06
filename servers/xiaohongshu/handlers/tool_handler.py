"""
Xiaohongshu Tool Handler — legacy 或 OpenCLI 混合后端
"""
import os
import sys
from typing import Any, Dict, List

import mcp.types as types

USE_OPENCLI_BACKEND = os.environ.get("XIAOHONGSHU_BACKEND", "opencli").strip().lower() in {
    "opencli",
    "1",
    "true",
    "yes",
}


class XiaohongshuToolHandler:
    """Factory：默认 OpenCLI + XHS-Downloader；legacy 保留旧工具集"""

    def __init__(self, dep_manager, api_client=None):
        self.dep_manager = dep_manager
        self.api_client = api_client
        self._delegate = self._build_delegate()

    def _build_delegate(self):
        if USE_OPENCLI_BACKEND:
            try:
                from shared.opencli_xhs_handler import OpenCLIXHSToolHandler

                return OpenCLIXHSToolHandler(self.dep_manager, self.api_client)
            except (ImportError, TypeError) as exc:
                print(f"WARN: OpenCLI XHS handler unavailable: {exc}", file=sys.stderr)
        return _LegacyXiaohongshuToolHandler(self.dep_manager, self.api_client)

    @property
    def tools(self) -> Dict[str, Dict[str, Any]]:
        return self._delegate.tools

    def get_tool_definitions(self) -> List[types.Tool]:
        return self._delegate.get_tool_definitions()

    async def list_tools(self) -> List[Dict[str, Any]]:
        if hasattr(self._delegate, "list_tools"):
            return await self._delegate.list_tools()
        return list(self.tools.values())

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        return await self._delegate.execute_tool(name, arguments)


class _LegacyXiaohongshuToolHandler:
    """原始工具集（sync_user / sync_notes / search_notes）"""

    def __init__(self, dep_manager, api_client):
        self.dep_manager = dep_manager
        self.api_client = api_client
        self.tools = self._define_tools()

    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "sync_user": {
                "name": "sync_user",
                "description": "同步小红书用户信息",
                "inputSchema": {
                    "type": "object",
                    "properties": {"user_id": {"type": "string"}},
                    "required": ["user_id"],
                },
            },
            "sync_notes": {
                "name": "sync_notes",
                "description": "同步小红书笔记（user_id=笔记 URL）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["user_id"],
                },
            },
            "search_notes": {
                "name": "search_notes",
                "description": "搜索已同步笔记",
                "inputSchema": {
                    "type": "object",
                    "properties": {"keyword": {"type": "string"}},
                    "required": ["keyword"],
                },
            },
            "delete_note": {
                "name": "delete_note",
                "description": "删除已同步笔记",
                "inputSchema": {
                    "type": "object",
                    "properties": {"article_id": {"type": "integer"}},
                    "required": ["article_id"],
                },
            },
            "run_scheduled_task": {
                "name": "run_scheduled_task",
                "description": "运行定时任务",
                "inputSchema": {"type": "object", "properties": {}},
            },
        }

    def get_tool_definitions(self) -> List[types.Tool]:
        return [
            types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in self.tools.values()
        ]

    async def list_tools(self) -> List[Dict[str, Any]]:
        return list(self.tools.values())

    @staticmethod
    def _source_url(arguments: Dict[str, Any]) -> str:
        for key in ("user_id", "source_url", "url", "share_text"):
            value = arguments.get(key)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        try:
            if name == "sync_user":
                return self.api_client.sync_user(arguments.get("user_id"))
            if name == "sync_notes":
                return await self.api_client.sync_notes(
                    arguments.get("user_id") or self._source_url(arguments),
                    arguments.get("limit", 20),
                )
            if name == "search_notes":
                return self.api_client.search_notes(arguments.get("keyword"))
            if name == "delete_note":
                return self.api_client.delete_note(str(arguments.get("article_id")))
            if name == "run_scheduled_task":
                return await self.api_client.run_scheduled_task()
            return {"success": False, "error": f"Unknown tool: {name}"}
        except Exception as exc:
            return {"success": False, "error": str(exc), "tool": name}
