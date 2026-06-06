# -*- coding: utf-8 -*-
"""
Server Client Module.
Unified client for MCP and HTTP servers with port validation and protocol selection.

This module provides:
- Port validation using service_ports.json rules
- Protocol selection (HTTP, MCP/Stdio, SSE)
- Integration with data_services for stock data
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Import MCP components
from core.mcp.plugin_manager import PluginManager, get_plugin_manager
from core.mcp.utils import get_mcp_manager
from core.mcp.manager import MCPClientManager
from core.mcp.sessions import (
    BaseClientSession,
    StdioMcpSession,
    SseMcpSession,
    HttpApiSession
)

# Import data services components
# Import components from the new service registry
from core.service.registry import get_service_registry
from core.protocol_client import ProtocolClientFactory, APIProtocolClient, MCPProtocolClient

# Constants
timeout = 300

# Default protocols by service type
DEFAULT_PROTOCOLS = {
    "stock_market": "http",
    "stock_fundflow": "http",
    "stock_sentiment": "http",
    "stock_news": "http",
}


class ServerClientManager:
    """
    Backward-compatibility wrapper for ServiceGateway.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        from core.service.gateway import get_service_gateway
        self._gateway = get_service_gateway()
    
    def get_server_url(self, service_name: str, protocol: Optional[str] = None) -> str:
        from core.service.registry import get_service_registry
        reg = get_service_registry()
        return reg.get_url(service_name, protocol or "api")
    
    def get_client(self, service_name: str, protocol: Optional[str] = None, use_data_service: bool = True) -> Any:
        # Resolve alias
        alias = f"{service_name}_{protocol or 'api'}"
        from core.service.gateway import call_sync
        # We return a Proxy object that can perform calls if the original code expects a client object
        # Or better, just get the actual client async-safely
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Risky to block here, but we'll try to get it if already started
            return self._gateway._clients.get(alias)
        return loop.run_until_complete(self._gateway.get_client(alias))
    
    def get_data_client(self, service_name: str) -> Any:
        # Note: UnifiedDataClient deprecated, return gateway-managed client
        return self.get_client(service_name)
    
    async def connect_all(self):
        pass # Lifecycle handled on-demand
    
    async def close_all(self):
        await self._gateway.shutdown()


# Global manager instance
_server_client_manager: Optional[ServerClientManager] = None


def get_server_client_manager(config: Optional[Dict[str, Any]] = None) -> ServerClientManager:
    """Get global server client manager"""
    global _server_client_manager
    if _server_client_manager is None:
        _server_client_manager = ServerClientManager(config)
    return _server_client_manager


def get_stock_server_url(service_name: str, protocol: str = "http") -> str:
    """
    Get validated stock server URL.
    
    Args:
        service_name: Stock service name (market, fundflow, sentiment, news)
        protocol: Protocol type
    
    Returns:
        Server URL
    """
    manager = get_server_client_manager()
    return manager.get_server_url(f"stock_{service_name}", protocol)


# Backward compatibility - re-export MCP components
__all__ = [
    # MCP Components (backward compatible)
    "MCPClientManager",
    "PluginManager",
    "get_plugin_manager",
    "get_mcp_manager",
    "BaseClientSession",
    "StdioMcpSession",
    "SseMcpSession",
    "HttpApiSession",
    # Server Client Manager
    "ServerClientManager",
    "get_server_client_manager",
    "get_stock_server_url",
    # Constants
    "timeout",
    "DEFAULT_PROTOCOLS",
]
