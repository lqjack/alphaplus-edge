# -*- coding: utf-8 -*-
"""
Service Gateway Module.
Provides unified access to MCP and HTTP services.
"""

import asyncio
import logging
from typing import Any, Dict, Optional
from core.service.registry import get_service_registry
from core.protocol_client import ProtocolClientFactory

logger = logging.getLogger(__name__)


class ServiceGateway:
    """
    Unified gateway for all MCP and HTTP services.
    Manages client lifecycle and provides consistent interface.
    """

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._registry = get_service_registry()
        self._clients: Dict[str, Any] = {}
        self._initialized = True
        logger.info("[ServiceGateway] Initialized")

    @property
    def registry(self):
        return self._registry

    async def get_client(self, service_alias: str) -> Any:
        """Get or create a client for a service."""
        if service_alias in self._clients:
            return self._clients[service_alias]

        async with self._lock:
            if service_alias in self._clients:
                return self._clients[service_alias]

            service_name, protocol = self._registry.parse_alias(service_alias)
            url = self._registry.get_url(service_name, protocol)

            config = {"name": service_name, "protocol": protocol, "base_url": url}

            logger.info(
                f"[ServiceGateway] Initializing {service_alias} via {protocol} at {url}"
            )
            client = ProtocolClientFactory.create_client(config)
            await client.connect()
            self._clients[service_alias] = client
            return client

    async def call(
        self, service_alias: str, tool_name: str, arguments: Dict[str, Any]
    ) -> Any:
        """Call a tool on a service."""
        client = await self.get_client(service_alias)
        return await client.call(tool_name, arguments)

    async def shutdown(self):
        """Shutdown all clients."""
        async with self._lock:
            for alias, client in self._clients.items():
                try:
                    await client.close()
                except Exception as e:
                    logger.warning(f"Failed closing {alias}: {e}")
            self._clients.clear()


_gateway: Optional[ServiceGateway] = None


def get_service_gateway() -> ServiceGateway:
    """Get the global service gateway instance."""
    global _gateway
    if _gateway is None:
        _gateway = ServiceGateway()
    return _gateway


def call_sync(service_alias: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Synchronous wrapper for service calls."""
    gateway = get_service_gateway()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(
                asyncio.run, gateway.call(service_alias, tool_name, arguments)
            ).result()
    return loop.run_until_complete(gateway.call(service_alias, tool_name, arguments))
