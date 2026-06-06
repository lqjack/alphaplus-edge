"""
WeChat Viewer Server Handler

Handles MCP server lifecycle and protocol operations for WeChat Viewer.
"""
from mcp.server import Server
import mcp.types as types


class WeChatViewerServerHandler:
    """Handles MCP server operations for WeChat Viewer"""

    def __init__(self, tool_handler):
        self.tool_handler = tool_handler
        self.app = Server("wechat-viewer-mcp")

        # Register MCP handlers
        self.app.list_tools()(self._list_tools)
        self.app.call_tool()(self._call_tool)

    async def _list_tools(self) -> list[types.Tool]:
        """List available WeChat Viewer tools"""
        return self.tool_handler.get_tool_definitions()

    async def _call_tool(self, name: str, arguments: dict) -> any:
        """Execute WeChat Viewer tool"""
        return await self.tool_handler.execute_tool(name, arguments)

    def get_app(self) -> Server:
        """Get the MCP server app instance"""
        return self.app
