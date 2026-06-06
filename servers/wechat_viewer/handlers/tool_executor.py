"""
WeChat Viewer Tool Executor

Provides unified tool execution interface for WeChat Viewer REST API.
Updated to use shared event loop management.
"""

import json
import logging
import os
import asyncio
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Shared event loop for all executions
_shared_loop = None


def get_loop() -> asyncio.AbstractEventLoop:
    """Get or create a shared event loop"""
    global _shared_loop
    if _shared_loop is None or _shared_loop.is_closed():
        _shared_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_shared_loop)
    return _shared_loop


class ToolExecutor:
    """Unified tool executor for WeChat Viewer"""

    def __init__(self, tool_handler):
        self.tool_handler = tool_handler
        self.logger = logging.getLogger("wechat_tool_executor")

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools"""
        if hasattr(self.tool_handler, "get_tool_definitions"):
            tools = self.tool_handler.get_tool_definitions()
            tools_dict = []
            for t in tools:
                if hasattr(t, "model_dump"):
                    tools_dict.append(t.model_dump())
                elif hasattr(t, "dict"):
                    tools_dict.append(t.dict())
                else:
                    tools_dict.append(t)
            return tools_dict
        return []

    def execute_tool(
        self, tool_name: str, arguments: Dict[str, Any], format: str = "standard"
    ) -> Dict[str, Any]:
        """Execute a tool"""
        if not hasattr(self.tool_handler, "execute_tool"):
            return {"error": "Tool handler not available"}

        try:
            # Use shared event loop
            loop = get_loop()
            result = loop.run_until_complete(
                self.tool_handler.execute_tool(tool_name, arguments)
            )

            if format == "openai":
                return {
                    "id": f"call_{os.urandom(8).hex()}",
                    "type": "function",
                    "function": {"name": tool_name, "arguments": json.dumps(arguments)},
                    "result": result,
                }
            else:
                return {"result": result}

        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {e}")
            return {"error": str(e), "tool": tool_name}
