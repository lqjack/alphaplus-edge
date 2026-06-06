# -*- coding: utf-8 -*-
"""
Protocol Client Abstraction
Supports different interaction protocols including MCP and API (HTTP/REST).
"""

import abc
import asyncio
import logging
import httpx
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class BaseProtocolClient(abc.ABC):
    """Abstract base class for all protocol clients"""

    @abc.abstractmethod
    async def connect(self, timeout: float = 30.0) -> bool:
        """Establish connection to the server"""
        pass

    @abc.abstractmethod
    async def call(self, function_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a function/tool on the server"""
        pass

    @abc.abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """Get current client/server status"""
        pass

    @abc.abstractmethod
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools/functions"""
        pass

    @abc.abstractmethod
    async def close(self):
        """Close connection and clean up resources"""
        pass


class MCPProtocolClient(BaseProtocolClient):
    """Client for MCP protocol (stdio/JSON-RPC)"""

    def __init__(self, mcp_manager, server_name: str):
        self.mcp_manager = mcp_manager
        self.server_name = server_name
        self.connected = False

    async def connect(self, timeout: float = 30.0) -> bool:
        try:
            self.connected = await self.mcp_manager.connect_server(
                self.server_name, timeout=timeout
            )
            return self.connected
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {self.server_name}: {e}")
            return False

    async def call(self, function_name: str, arguments: Dict[str, Any]) -> Any:
        if not self.connected:
            await self.connect()
        return await self.mcp_manager.call_tool(
            self.server_name, function_name, arguments
        )

    async def get_status(self) -> Dict[str, Any]:
        status_map = self.mcp_manager.server_status
        status = status_map.get(self.server_name, "unknown")
        # Return a dict consistent with what resources expect
        return {
            "name": self.server_name,
            "status": status,
            "connected": status == "online",
        }

    async def list_tools(self) -> List[Dict[str, Any]]:
        return await self.mcp_manager.list_tools(self.server_name)

    async def close(self):
        await self.mcp_manager.disconnect_server(self.server_name)
        self.connected = False


class APIProtocolClient(BaseProtocolClient):
    """Client for HTTP/REST API protocol"""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=300.0)

    async def connect(self, timeout: float = 30.0) -> bool:
        # For HTTP, connection is usually stateless, but we can do a health check
        try:
            response = await self.client.get(f"{self.base_url}/health", timeout=5.0)
            return response.status_code == 200
        except Exception:
            # If no health endpoint, assume it's up or will be checked during call
            return True

    async def call(self, function_name: str, arguments: Dict[str, Any]) -> Any:
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        try:
            url = f"{self.base_url}/api/tools/call"
            response = await self.client.post(
                url,
                json={"name": function_name, "arguments": arguments},
                headers=headers,
            )
            if response.status_code == 404:
                url = f"{self.base_url}/tools/{function_name}"
                response = await self.client.post(url, json=arguments, headers=headers)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and "result" in payload:
                return payload["result"]
            return payload
        except Exception as e:
            logger.error(f"API call to {url} failed: {e}")
            raise

    async def get_status(self) -> Dict[str, Any]:
        try:
            resp = await self.client.get(f"{self.base_url}/health", timeout=5.0)
            status = "online" if resp.status_code == 200 else "error"
        except Exception:
            status = "offline"

        return {
            "name": self.base_url,
            "status": status,
            "connected": status == "online",
        }

    async def list_tools(self) -> List[Dict[str, Any]]:
        try:
            resp = await self.client.get(f"{self.base_url}/api/tools/list")
            if resp.status_code == 404:
                resp = await self.client.get(f"{self.base_url}/tools")
            payload = resp.json()
            if isinstance(payload, dict):
                result = payload.get("result")
                if isinstance(result, dict) and isinstance(result.get("tools"), list):
                    return result["tools"]
                if isinstance(payload.get("tools"), list):
                    return payload["tools"]
            return []
        except Exception:
            return []

    async def close(self):
        await self.client.aclose()


class ProtocolClientFactory:
    """Factory to create protocol clients based on configuration"""

    @staticmethod
    def create_client(
        service_config: Dict[str, Any], mcp_manager=None
    ) -> BaseProtocolClient:
        protocol = service_config.get("protocol", "mcp").lower()

        if protocol == "mcp":
            if not mcp_manager:
                from core.server_client import get_mcp_manager

                mcp_manager = get_mcp_manager()

            name = service_config.get("name")
            if not name:
                raise ValueError(
                    f"Missing 'name' in MCP service configuration. Available keys: {list(service_config.keys())}"
                )
            return MCPProtocolClient(mcp_manager, name)
        elif protocol == "api":
            base_url = service_config.get("base_url")
            if not base_url:
                raise ValueError(
                    f"Missing 'base_url' in API service configuration. Available keys: {list(service_config.keys())}"
                )
            return APIProtocolClient(
                base_url=base_url, api_key=service_config.get("api_key")
            )
        else:
            raise ValueError(f"Unsupported protocol: {protocol}")
