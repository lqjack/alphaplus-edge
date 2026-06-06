# -*- coding: utf-8 -*-
"""
Channel Plugin Manager
Handles MCP-based channel plugins with registry, health checks, and standardized interaction.
Supports hot-swapping and standardized I/O, auth, rate limiting, and retries.
"""

import os
import asyncio
import logging
import json
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from loguru import logger

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not available, ChannelPluginManager will operate in compatibility mode")

class ChannelStatus(Enum):
    OFFLINE = "offline"
    CONNECTED = "connected"
    ERROR = "error"
    DISABLED = "disabled"

@dataclass
class ChannelMetadata:
    name: str
    endpoint: str  # Command or URL
    args: List[str]
    description: str = ""
    version: str = "1.0.0"
    author: str = "Unknown"
    enabled: bool = True
    auth_config: Dict[str, Any] = None
    rate_limit: int = 10  # Requests per minute
    retry_policy: Dict[str, Any] = None
    health_check_path: str = "health"

class ChannelPlugin:
    """Wrapper for a standardized MCP Channel Plugin"""
    def __init__(self, metadata: ChannelMetadata):
        self.metadata = metadata
        self.session: Optional[ClientSession] = None
        self.status = ChannelStatus.OFFLINE
        self.last_error = None
        self.request_count = 0
        self.last_request_time = 0
        self._exit_stack = None

    async def connect(self):
        if not self.metadata.enabled:
            self.status = ChannelStatus.DISABLED
            return False
        
        try:
            # Setup environment
            env = os.environ.copy()
            if self.metadata.auth_config:
                env.update({k: str(v) for k, v in self.metadata.auth_config.items()})

            params = StdioServerParameters(
                command=self.metadata.endpoint,
                args=self.metadata.args,
                env=env
            )
            
            # This is a simplified version of the MCP connect logic
            # In a real implementation, we'd use AsyncExitStack correctly
            from contextlib import AsyncExitStack
            self._exit_stack = AsyncExitStack()
            
            ctx = stdio_client(params)
            read_stream, write_stream = await self._exit_stack.enter_async_context(ctx)
            self.session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await self.session.initialize()
            
            self.status = ChannelStatus.CONNECTED
            logger.info(f"Channel {self.metadata.name} connected successfully.")
            return True
        except Exception as e:
            self.status = ChannelStatus.ERROR
            self.last_error = str(e)
            logger.error(f"Failed to connect channel {self.metadata.name}: {e}")
            return False

    async def disconnect(self):
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self.session = None
        self.status = ChannelStatus.OFFLINE
        logger.info(f"Channel {self.metadata.name} disconnected.")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if self.status != ChannelStatus.CONNECTED:
            await self.connect()
            if self.status != ChannelStatus.CONNECTED:
                raise ConnectionError(f"Channel {self.metadata.name} is not connected.")

        # Rate limiting check
        now = time.time()
        if now - self.last_request_time < 60 / self.metadata.rate_limit:
            wait_time = (60 / self.metadata.rate_limit) - (now - self.last_request_time)
            logger.debug(f"Rate limiting channel {self.metadata.name}, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

        # Retry logic
        retries = self.metadata.retry_policy.get("max_retries", 3) if self.metadata.retry_policy else 3
        delay = self.metadata.retry_policy.get("initial_delay", 1.0) if self.metadata.retry_policy else 1.0
        
        for attempt in range(retries):
            try:
                self.last_request_time = time.time()
                self.request_count += 1
                result = await self.session.call_tool(tool_name, arguments)
                return result
            except Exception as e:
                if attempt == retries - 1:
                    logger.error(f"Tool {tool_name} failed on {self.metadata.name} after {retries} retries: {e}")
                    raise
                logger.warning(f"Tool {tool_name} failed on {self.metadata.name} (attempt {attempt+1}/{retries}): {e}")
                await asyncio.sleep(delay * (2 ** attempt))

    async def health_check(self) -> bool:
        try:
            # Standard health check via MCP tool or property if implemented
            # For now, we just check if it can list tools
            await self.session.list_tools()
            return True
        except:
            return False

class ChannelPluginManager:
    """Registry and manager for channel plugins"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChannelPluginManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.plugins: Dict[str, ChannelPlugin] = {}
        self._initialized = True
        self.config_path = os.getenv("CHANNEL_CONFIG_PATH", "conf/channels.json")

    async def load_plugins(self):
        """Load plugins from configuration file"""
        if not os.path.exists(self.config_path):
            logger.warning(f"Channel config file {self.config_path} not found.")
            # Default empty config
            self._save_config({})
            
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            for name, meta_dict in config.items():
                metadata = ChannelMetadata(**meta_dict)
                plugin = ChannelPlugin(metadata)
                self.plugins[name] = plugin
                if metadata.enabled:
                    await plugin.connect()
        except Exception as e:
            logger.error(f"Error loading channel plugins: {e}")

    def _save_config(self, config: Dict[str, Any]):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=4)

    async def register_channel(self, metadata: ChannelMetadata):
        """Register a new channel (Hot-swap support)"""
        if metadata.name in self.plugins:
            await self.plugins[metadata.name].disconnect()
        
        plugin = ChannelPlugin(metadata)
        self.plugins[metadata.name] = plugin
        
        # Save to config
        config = self._get_current_config_dict()
        config[metadata.name] = asdict(metadata)
        self._save_config(config)
        
        if metadata.enabled:
            await plugin.connect()
        logger.info(f"Channel {metadata.name} registered and saved.")

    async def unregister_channel(self, name: str):
        """Unregister a channel"""
        if name in self.plugins:
            await self.plugins[name].disconnect()
            del self.plugins[name]
            
            config = self._get_current_config_dict()
            if name in config:
                del config[name]
                self._save_config(config)
            logger.info(f"Channel {name} unregistered.")

    def _get_current_config_dict(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}

    async def get_plugin(self, name: str) -> Optional[ChannelPlugin]:
        return self.plugins.get(name)

    def list_channels(self) -> List[Dict[str, Any]]:
        return [{
            "name": p.metadata.name,
            "status": p.status.value,
            "description": p.metadata.description,
            "enabled": p.metadata.enabled
        } for p in self.plugins.values()]

    def discover_plugins(self) -> List[str]:
        """Discover available channel plugins"""
        return list(self.plugins.keys())

    async def load_plugin(self, plugin_name: str):
        """Load a specific plugin"""
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            if plugin.metadata.enabled and plugin.status != ChannelStatus.CONNECTED:
                await plugin.connect()
            return plugin
        return None

# Global manager instance
channel_manager = ChannelPluginManager()
