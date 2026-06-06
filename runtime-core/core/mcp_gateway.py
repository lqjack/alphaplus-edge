# -*- coding: utf-8 -*-
"""
Revised MCP Gateway Service.
Consolidated single entry point for all service management.
Follows local design documents for light-weight, tool-based architecture.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from core.service.registry import get_service_registry
from core.protocol_client import ProtocolClientFactory

logger = logging.getLogger(__name__)

class MCPGateway:
    """Unified Gateway for all MCP/API Services with automated lifecycle."""

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, service_manager=None):
        if self._initialized: return
        self._registry = get_service_registry()
        self._clients: Dict[str, Any] = {}
        self._initialized = True
        logger.info("[MCPGateway] Consolidated Gateway initialized")

    @property
    def registry(self): return self._registry

    async def get_client(self, service_alias: str) -> Any:
        """Fetch or start a client by its alias (e.g. 'stock_market_mcp')"""
        if service_alias in self._clients:
            return self._clients[service_alias]

        async with self._lock:
            if service_alias in self._clients:
                return self._clients[service_alias]

            service_name, protocol = self._registry.parse_alias(service_alias)
            url = self._registry.get_url(service_name, protocol)
            
            config = {
                "name": service_name,
                "protocol": protocol,
                "base_url": url
            }
            
            logger.info(f"[MCPGateway] Initializing {service_alias} via {protocol} at {url}")
            client = ProtocolClientFactory.create_client(config)
            await client.connect()
            self._clients[service_alias] = client
            return client

    async def call(self, service_alias: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        client = await self.get_client(service_alias)
        return await client.call(tool_name, arguments)

    async def list_tools(self, service_alias: str) -> List[Dict[str, Any]]:
        client = await self.get_client(service_alias)
        return await client.list_tools()

    async def get_service_status(self, service_name: str, protocol: str = "mcp") -> Dict[str, Any]:
        alias = f"{service_name}_{protocol}"
        client = await self.get_client(alias)
        return await client.get_status()

    def list_services(self) -> List[Dict[str, Any]]:
        """List all active service aliases"""
        return [{"alias": alias} for alias in self._clients.keys()]

    async def shutdown(self):
        async with self._lock:
            for alias, client in self._clients.items():
                try:
                    await client.close()
                except Exception as e:
                    logger.warning(f"Failed closing {alias}: {e}")
            self._clients.clear()

def get_mcp_gateway(service_manager=None) -> MCPGateway:
    return MCPGateway(service_manager)

# --- Legacy Sync Wrappers for REST/Sync APIs ---

def _run_sync(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return loop.run_until_complete(coro)

def call_sync(service_alias: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
    return _run_sync(get_mcp_gateway().call(service_alias, tool_name, arguments))

def list_tools_sync(service_alias: str) -> List[Dict[str, Any]]:
    return _run_sync(get_mcp_gateway().list_tools(service_alias))

def get_status_sync(service_alias: str = None) -> Dict[str, Any]:
    if service_alias:
        return _run_sync(get_mcp_gateway().get_service_status(*get_service_registry().parse_alias(service_alias)))
    
    # Summary of all active
    all_active = get_mcp_gateway().list_services()
    results = {}
    for item in all_active:
        alias = item["alias"]
        results[alias] = _run_sync(get_mcp_gateway().get_service_status(*get_service_registry().parse_alias(alias)))
    return results

__all__ = ["MCPGateway", "get_mcp_gateway", "call_sync", "list_tools_sync", "get_status_sync"]
