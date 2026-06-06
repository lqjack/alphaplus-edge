# -*- coding: utf-8 -*-
"""
MCP Client Sessions.
Defines base class and specific implementations for different protocols:
- StdioMcpSession: Local process via Stdio.
- SseMcpSession: Remote Connection via SSE.
- HttpApiSession: Remote API via HTTP/REST.
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json

# Third-party imports
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

# Try importing sse_client
try:
    from mcp.client.sse import sse_client
except ImportError:
    sse_client = None

# Try importing MCP content types
try:
    from mcp.types import TextContent, ImageContent, EmbeddedResource
except ImportError:
    # Fallback: define simplified content types
    TextContent = None
    ImageContent = None
    EmbeddedResource = None
    from servers.shared.models import ContentItem as FallbackContentItem

# Global timeout configuration
TIMEOUT = 300

@dataclass
class CallToolResult:
    """Standardized result structure for tool calls"""
    content: List[Any]  # Can be TextContent, ImageContent, EmbeddedResource, or dict
    isError: bool = False

class BaseClientSession(ABC):
    """Abstract Base Class for all Client Sessions"""

    def __init__(self, name: str, config: Dict[str, Any], logger: logging.Logger):
        self.name = name
        self.config = config
        self.logger = logger
        self._connected = False

    @abstractmethod
    async def connect(self, exit_stack: AsyncExitStack):
        """Establish connection and initialize session"""
        pass

    @abstractmethod
    async def list_tools(self) -> List[Any]:
        """List available tools"""
        pass

    @abstractmethod
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a specific tool"""
        pass

    @abstractmethod
    async def close(self):
        """Close connection"""
        self._connected = False


class McpSessionMixin:
    """Mixin for MCP-protocol sessions (Stdio & SSE)"""
    def __init__(self):
        self._session: Optional[ClientSession] = None

    async def _init_mcp_session(self, read_stream, write_stream, exit_stack: AsyncExitStack):
        self._session = await exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        self.logger.info(f"Initializing MCP session for {self.name}...")
        await asyncio.wait_for(self._session.initialize(), timeout=TIMEOUT)
        self.logger.info(f"MCP Session initialized for {self.name}")
        self._connected = True

    async def list_tools(self) -> List[Any]:
        if not self._session:
            raise ConnectionError(f"Session {self.name} not initialized")
        result = await self._session.list_tools()
        # Ensure result is compatible with what callers expect (list of Tool objects)
        return result.tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        if not self._session:
            raise ConnectionError(f"Session {self.name} not initialized")
        return await self._session.call_tool(name, arguments or {})

    async def close(self):
        # Session closed by ExitStack managed by caller (usually Manager)
        pass


class StdioMcpSession(McpSessionMixin, BaseClientSession):
    """MCP Client using Stdio (Local Process)"""

    def __init__(self, name, config, logger):
        BaseClientSession.__init__(self, name, config, logger)
        McpSessionMixin.__init__(self)

    async def connect(self, exit_stack: AsyncExitStack):
        command = self.config.get("command")
        args = self.config.get("args", [])
        cwd = self.config.get("cwd")
        env = self.config.get("env", os.environ.copy())

        # Validate command
        if not command:
            raise ValueError(f"Command not specified for Stdio session {self.name}")

        self.logger.info(f"Starting stdio process for {self.name}: {command} {' '.join(args)}")

        params = StdioServerParameters(
            command=command,
            args=args,
            env=env,
            cwd=cwd
        )
        
        ctx = stdio_client(params)
        read_stream, write_stream = await exit_stack.enter_async_context(ctx)
        
        # Initialize MCP Session
        await self._init_mcp_session(read_stream, write_stream, exit_stack)


class SseMcpSession(McpSessionMixin, BaseClientSession):
    """MCP Client using SSE (Remote)"""

    def __init__(self, name, config, logger):
        BaseClientSession.__init__(self, name, config, logger)
        McpSessionMixin.__init__(self)

    async def connect(self, exit_stack: AsyncExitStack):
        url = self.config.get("url")
        if not url:
            raise ValueError(f"URL required for SSE session {self.name}")
        
        if not sse_client:
             raise ImportError("mcp.client.sse module not available")

        self.logger.info(f"Connecting to SSE endpoint for {self.name} at {url}")
        
        # Connect to SSE
        ctx = sse_client(url)
        read_stream, write_stream = await exit_stack.enter_async_context(ctx)
        
        # Initialize MCP Session
        await self._init_mcp_session(read_stream, write_stream, exit_stack)


class HttpApiSession(BaseClientSession):
    """Client for Remote HTTP API (Non-MCP protocol / REST)"""
    
    def __init__(self, name, config, logger):
        super().__init__(name, config, logger)
        self.client: Optional[httpx.AsyncClient] = None
        self.base_url = config.get("url", "").rstrip("/")

    async def connect(self, exit_stack: AsyncExitStack):
        self.logger.info(f"Initializing HTTP Client for {self.name} at {self.base_url}")
        
        # trust_env=False so loopback calls don't get hijacked by the macOS
        # system proxy (``scutil --proxy``) or HTTP_PROXY env vars.
        self.client = await exit_stack.enter_async_context(
            httpx.AsyncClient(timeout=TIMEOUT, trust_env=False)
        )
        
        # Health Check
        try:
            resp = await self.client.get(f"{self.base_url}/health")
            if resp.status_code != 200:
                self.logger.warning(f"Health check failed for {self.name}: {resp.status_code}")
            else:
                self.logger.info(f"Health check passed for {self.name}")
        except Exception as e:
            self.logger.warning(f"Health check exception for {self.name}: {e}")
        
        self._connected = True

    async def list_tools(self) -> List[Any]:
        if not self.client:
            raise ConnectionError("Client not initialized")
        
        resp = await self.client.get(f"{self.base_url}/api/tools/list")
        resp.raise_for_status()
        data = resp.json()
        
        # Adapt response to match standard list format
        if "result" in data and isinstance(data["result"], list):
             return data["result"]
        if "result" in data and "tools" in data["result"]:
             return data["result"]["tools"]
        
        return data.get("result", [])

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        if not self.client:
            raise ConnectionError("Client not initialized")

        payload = {"name": name, "arguments": arguments}
        resp = await self.client.post(f"{self.base_url}/api/tools/call", json=payload)
        resp.raise_for_status()

        data = resp.json()
        result = data.get("result", {})

        # Convert API result to MCP standard format
        # The API server returns {"response": "...", "status": "success"} format
        # We need to convert this to MCP TextContent format

        content_items = []
        if isinstance(result, str):
            # Direct string response
            if TextContent is not None:
                content_items.append(TextContent(type="text", text=result))
            else:
                content_items.append({"type": "text", "text": result})
        elif isinstance(result, dict):
            # Check for AI API response format: {"response": "...", "status": "success"}
            if "response" in result:
                response_text = result.get("response", "")
                if TextContent is not None:
                    content_items.append(TextContent(type="text", text=response_text))
                else:
                    content_items.append({"type": "text", "text": response_text})
            else:
                # Generic dict, convert to JSON string
                if TextContent is not None:
                    content_items.append(TextContent(type="text", text=json.dumps(result, ensure_ascii=False)))
                else:
                    content_items.append({"type": "text", "text": json.dumps(result, ensure_ascii=False)})
        elif isinstance(result, list):
            # List of items
            for item in result:
                if isinstance(item, dict):
                    if "type" in item and "text" in item:
                        # Already in MCP format
                        content_items.append(item)
                    else:
                        if TextContent is not None:
                            content_items.append(TextContent(type="text", text=json.dumps(item, ensure_ascii=False)))
                        else:
                            content_items.append({"type": "text", "text": json.dumps(item, ensure_ascii=False)})
                else:
                    if TextContent is not None:
                        content_items.append(TextContent(type="text", text=str(item)))
                    else:
                        content_items.append({"type": "text", "text": str(item)})
        else:
            # Other types
            if TextContent is not None:
                content_items.append(TextContent(type="text", text=str(result)))
            else:
                content_items.append({"type": "text", "text": str(result)})

        return CallToolResult(content=content_items)

    async def close(self):
        # Client closed by ExitStack
        self._connected = False
