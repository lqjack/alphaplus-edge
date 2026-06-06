# -*- coding: utf-8 -*-
"""
MCP Utility Functions.
"""

from core.mcp.manager import MCPClientManager

# Singleton instance
_manager_instance = None

def get_mcp_manager() -> MCPClientManager:
    """Get the singleton MCP client manager instance"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MCPClientManager()
    return _manager_instance