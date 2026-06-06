# -*- coding: utf-8 -*-
"""
MCP Client Manager.
Orchestrates connections to multiple MCP servers using different protocols.
"""

import asyncio
import logging
import os
import sys
from contextlib import AsyncExitStack
from typing import Dict, Any, Optional
from asyncio import AbstractEventLoop

from core.logger import setup_logger
from core.mcp.plugin_manager import get_plugin_manager
from core.mcp.sessions import (
    BaseClientSession,
    StdioMcpSession,
    SseMcpSession,
    HttpApiSession,
)


class MCPClientManager:
    """MCP Client Manager - Supporting Multiple Protocols"""

    def __init__(self, config: Dict[str, Any] = None):
        self.logger = setup_logger("MCP-Client-Manager", log_to_console=True)
        self.plugin_manager = get_plugin_manager()
        self.exit_stack = AsyncExitStack()

        self.sessions: Dict[str, BaseClientSession] = {}
        self.connected = False

        # Connection management
        self._connection_locks: Dict[str, asyncio.Lock] = {}
        self._locks_initialized_loop: Optional[AbstractEventLoop] = None

        # Load configuration
        self.config = config or self._build_config()

    def _build_config(self) -> Dict[str, Any]:
        """Build configuration from plugins and environment variables"""
        config = {}

        # Iterate through all discovered plugins
        for plugin_name, plugin_info in self.plugin_manager.plugins.items():
            # Check for Remote URL override in Environment
            # Format: MCP_{PLUGIN_NAME_UPPER}_URL
            env_var = f"MCP_{plugin_name.upper()}_URL"
            remote_url = os.getenv(env_var)

            if remote_url:
                self.logger.info(
                    f"Configuring {plugin_name} for Remote Connection: {remote_url}"
                )
                # Determine protocol type
                # Heuristic: _api suffix -> HTTP REST, else SSE
                protocol_type = "http" if plugin_name.endswith("_api") else "sse"

                config[plugin_name] = {
                    "type": protocol_type,
                    "url": remote_url,
                    "name": plugin_name,
                }
            else:
                # Default to Local Stdio
                # Get python executable (ensure installed)
                python_path = self.plugin_manager.get_plugin_python(
                    plugin_name, install_if_missing=False
                )

                # Command
                cmd_python = str(python_path) if python_path else sys.executable

                # Check strict venv rule: if plugin has .mcp-venv, usage is preferred.
                # If python_path is None (deps not installed yet), we might install them on connect or use fallback
                # Here we assume we use what's available or default to sys.executable (main venv)

                config[plugin_name] = {
                    "type": "stdio",
                    "command": cmd_python,
                    "args": [str(plugin_info["entry"])],
                    "cwd": str(plugin_info["dir"]),
                    "name": plugin_name,
                    "dependencies": [],  # handled by plugin manager
                }

        return config

    async def connect_all(self):
        """Connect to all configured servers"""
        if self.connected:
            return

        self.logger.info("Connecting to all MCP services...")

        # Connect to each server
        for server_name in self.config:
            try:
                await self.connect_server(server_name)
            except Exception as e:
                self.logger.error(f"Failed to connect to {server_name}: {e}")

        self.connected = True

    async def connect_server(self, server_name: str, timeout: float = 30.0):
        """Connect to a specific server"""
        if server_name in self.sessions:
            return

        cfg = self.config.get(server_name)
        if not cfg:
            raise ValueError(f"Server {server_name} not found in config")

        # Instantiate implementation based on type
        protocol_type = cfg.get("type", "stdio")
        session: BaseClientSession = None

        if protocol_type == "sse":
            session = SseMcpSession(server_name, cfg, self.logger)
        elif protocol_type == "http":
            session = HttpApiSession(server_name, cfg, self.logger)
        else:
            # Stdio - Prepare Environment
            env = os.environ.copy()

            # Setup PYTHONPATH
            # Currently in src/core/mcp, need parent of src/core -> src
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            env["PYTHONPATH"] = f"{project_root}{os.pathsep}{env.get('PYTHONPATH', '')}"
            env["VIRTUAL_ENV"] = ""  # Clear to avoid conflicts

            # Add Plugin Venv to PATH if applicable
            command = cfg.get("command")
            if command and ("site-packages" not in command):
                bin_dir = os.path.dirname(command)
                env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

            cfg["env"] = env
            session = StdioMcpSession(server_name, cfg, self.logger)

        # Connect
        self.logger.info(f"Initiating {protocol_type} connection to {server_name}...")
        await session.connect(self.exit_stack)
        self.sessions[server_name] = session
        self.logger.info(f"Connected to {server_name}")

    async def list_tools(self, server_name: str):
        """List tools for a server"""
        if server_name not in self.sessions:
            await self.connect_server(server_name)

        return await self.sessions[server_name].list_tools()

    def _get_connection_lock(self, server_name: str) -> asyncio.Lock:
        """Get or create a Lock for the given server, ensuring it's bound to the current event loop."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if server_name not in self._connection_locks:
            self._connection_locks[server_name] = asyncio.Lock()
            self._locks_initialized_loop = current_loop
            return self._connection_locks[server_name]

        lock = self._connection_locks[server_name]
        if (
            self._locks_initialized_loop is not None
            and current_loop is not None
            and self._locks_initialized_loop is not current_loop
        ):
            self.logger.warning(
                f"Event loop mismatch for lock {server_name}: "
                f"created in loop {id(self._locks_initialized_loop)}, "
                f"now running in loop {id(current_loop)}. Recreating lock."
            )
            lock = asyncio.Lock()
            self._connection_locks[server_name] = lock
            self._locks_initialized_loop = current_loop

        return lock

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: Dict[str, Any] = None
    ):
        """Call a tool on a server"""
        lock = self._get_connection_lock(server_name)

        async with lock:
            if server_name not in self.sessions:
                await self.connect_server(server_name)

            session = self.sessions[server_name]
            return await session.call_tool(tool_name, arguments or {})

    async def restart_server(self, server_name: str):
        """Restart a specific server"""
        self.logger.info(f"Restarting server: {server_name}")

        lock = self._get_connection_lock(server_name)

        async with lock:
            if server_name in self.sessions:
                try:
                    await self.sessions[server_name].close()
                except Exception as e:
                    self.logger.warning(
                        f"Error closing {server_name} during restart: {e}"
                    )
                del self.sessions[server_name]

            try:
                await self.connect_server(server_name)
                return True
            except Exception as e:
                self.logger.error(f"Failed to restart {server_name}: {e}")
                return False

    async def close(self):
        """Close all connections via ExitStack"""
        self.logger.info("Closing all MCP connections...")
        await self.exit_stack.aclose()
        self.sessions.clear()
        self.connected = False

    def is_connected(self, server_name: str) -> bool:
        """Check if a server is connected"""
        return server_name in self.sessions

    def get_registered_servers(self) -> list:
        """Get list of all registered servers"""
        return list(self.config.keys())

    async def shutdown(self):
        await self.close()

    def register_server(self, config: Dict[str, Any]):
        """Register a new server configuration

        If a server is already configured (e.g., from environment variable),
        the existing remote configuration is preserved and this registration is skipped.
        """
        if not self.config:
            self.config = {}

        server_name = config.get("name")
        if not server_name:
            self.logger.warning("register_server: missing 'name' in config")
            return

        # Check if server is already configured
        if server_name in self.config:
            existing_config = self.config[server_name]

            # If existing config is a remote connection (http/sse), preserve it
            existing_type = existing_config.get("type", "stdio")
            if existing_type in ("http", "sse"):
                self.logger.info(
                    f"Server {server_name} already configured for remote connection "
                    f"(type={existing_type}, url={existing_config.get('url')}), "
                    f"skipping stdio registration from cline_mcp_settings.json"
                )
                return

        # Register the server (stdio mode from cline_mcp_settings.json)
        self.config[server_name] = config
        self.logger.info(f"Registered server: {server_name}")
