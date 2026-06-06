# -*- coding: utf-8 -*-
"""
Service Manager
Unified management for all services (MCP and API).
Supports plugin discovery, isolated virtual environments, and multiple protocols.
"""

import os
import asyncio
import logging
import subprocess
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from contextlib import AsyncExitStack

# Protocol clients
from core.protocol_client import BaseProtocolClient, ProtocolClientFactory
from core.service_ports import (
    SERVICE_PORTS,
    SERVICE_ALIASES,
    PROTOCOL_OFFSETS,
    get_port,
    parse_service_alias,
    get_service_list,
    validate_port,
)

logger = logging.getLogger(__name__)

class ServiceConfig:
    """Service Configuration"""
    def __init__(self, name: str, protocol: str = "mcp", **kwargs):
        self.name = name
        self.protocol = protocol
        self.config = {"name": name, "protocol": protocol, **kwargs}
        
    def get(self, key, default=None):
        return self.config.get(key, default)

class ServiceManager:
    """Manager for all services"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, servers_dir: Optional[str] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        if servers_dir is None:
            # Support both src/servers (new) and mcp_legacy/servers (legacy)
            base_dir = Path(__file__).parent.parent
            src_servers = base_dir / "servers"
            legacy_servers = base_dir / "mcp_legacy" / "servers"
            
            if src_servers.exists():
                self.servers_dir = src_servers
            else:
                self.servers_dir = legacy_servers
        else:
            self.servers_dir = Path(servers_dir)
            
        self.services: Dict[str, ServiceConfig] = {}
        self.clients: Dict[str, BaseProtocolClient] = {}
        self.processes: Dict[str, Any] = {}
        self.exit_stack = AsyncExitStack()
        self._initialized = True
        
    def discover_services(self):
        """Discover services in the servers directory"""
        logger.info(f"Discovering services in: {self.servers_dir}")
        if not self.servers_dir.exists():
            logger.warning(f"Servers directory not found: {self.servers_dir}")
            return

        count = 0
        for server_dir in self.servers_dir.iterdir():
            if not server_dir.is_dir():
                continue
                
            service_name = server_dir.name
            self._load_service(service_name, server_dir)
            count += 1
        logger.info(f"Discovered {count} potential services. Total registered configs: {len(self.services)}")

    def _load_service(self, service_name: str, service_dir: Path):
        """Load service configuration from its directory"""
        # Default to MCP if mcp_server.py or server.py exists
        mcp_entry = self._find_entry(service_dir, ["mcp_server.py", "server.py", "main.py"])
        api_entry = self._find_entry(service_dir, ["api_server.py"])
        
        if mcp_entry:
            # Register MCP service
            python_path = self._get_venv_python(service_dir)
            logger.debug(f"Registering MCP service: {service_name} at {mcp_entry}")
            
            # Get port from configuration
            try:
                mcp_port = get_port(service_name, "mcp")
            except KeyError:
                mcp_port = self._get_fallback_port(service_name, "mcp")
            
            self.services[f"{service_name}_mcp"] = ServiceConfig(
                name=service_name,
                protocol="mcp",
                port=mcp_port,
                command=str(python_path),
                args=[str(mcp_entry)],
                cwd=str(service_dir)
            )
            
        if api_entry:
            # Register API service with port from configuration
            python_path = self._get_venv_python(service_dir)
            logger.debug(f"Registering API service: {service_name}")
            
            try:
                api_port = get_port(service_name, "api")
            except KeyError:
                api_port = self._get_fallback_port(service_name, "api")
            
            self.services[f"{service_name}_api"] = ServiceConfig(
                name=service_name,
                protocol="api",
                port=api_port,
                base_url=f"http://localhost:{api_port}",
                command=str(python_path),
                args=[str(api_entry)],
                cwd=str(service_dir)
            )

    def _find_entry(self, service_dir: Path, names: List[str]) -> Optional[Path]:
        for name in names:
            path = service_dir / name
            if path.exists():
                return path
        return None

    def _get_venv_python(self, service_dir: Path) -> Path:
        """Get Python interpreter for the service's virtual environment"""
        for venv_name in [".mcp_venv", ".venv"]:
            venv_path = service_dir / venv_name
            if os.name == 'nt':
                python_path = venv_path / "Scripts" / "python.exe"
            else:
                python_path = venv_path / "bin" / "python"

            # Use a more robust check for directory existence
            # Try to check if the venv directory exists and is accessible
            venv_exists = False
            try:
                # First try the standard path check
                if os.path.exists(venv_path) and os.path.isdir(venv_path):
                    venv_exists = True
                # If that fails, try to stat the directory directly
                elif os.path.isdir(venv_path):  # This can work when exists/isdir fails
                    venv_exists = True
            except (OSError, PermissionError):
                # If we can't access the path, assume it doesn't exist
                venv_exists = False

            if venv_exists and python_path.exists():
                return python_path
        return Path(sys.executable)

    def _get_fallback_port(self, service_name: str, protocol: str) -> int:
        """
        Get fallback port for unknown services.
        Uses hash-based allocation in the 10500-10599 range.
        """
        base = 10500
        offset = abs(hash(f"{service_name}_{protocol}")) % 100
        return base + offset

    def _get_port_for_service(self, service_name: str) -> int:
        """
        Get a stable port for a service based on its name.
        Uses fixed port mapping from service_ports.py configuration.
        """
        # Parse the alias to get service name and protocol
        service, protocol = parse_service_alias(service_name)
        
        try:
            return get_port(service, protocol)
        except KeyError:
            # Fallback for unknown services
            return self._get_fallback_port(service, protocol)

    def validate_service_port(self, service_alias: str, expected_port: int) -> bool:
        """
        Validate if the port matches the configuration.
        
        Args:
            service_alias: Service alias (e.g., "wechat_api", "ai_mcp")
            expected_port: Port to validate
        
        Returns:
            True if port is correct, False otherwise
        """
        service, protocol = parse_service_alias(service_alias)
        return validate_port(expected_port, service, protocol)

    def get_service_info(self, service_alias: str) -> Dict[str, Any]:
        """
        Get full service information including port validation.
        
        Args:
            service_alias: Service alias (e.g., "wechat_api")
        
        Returns:
            Dictionary with service details
        """
        service, protocol = parse_service_alias(service_alias)
        
        try:
            port = get_port(service, protocol)
        except KeyError:
            port = self._get_fallback_port(service, protocol)
        
        return {
            "service_name": service,
            "protocol": protocol,
            "port": port,
            "configured": service in SERVICE_PORTS,
        }

    def list_all_services(self) -> List[Dict[str, Any]]:
        """
        List all configured services with their ports.
        
        Returns:
            List of service information dictionaries
        """
        result = []
        for service_name in get_service_list():
            for protocol, port in SERVICE_PORTS[service_name].items():
                alias = f"{service_name}_{protocol}"
                result.append({
                    "alias": alias,
                    "service_name": service_name,
                    "protocol": protocol,
                    "port": port,
                })
        return result

    @staticmethod
    def get_protocol_for_service(service_name: str) -> str:
        """
        Get protocol for a service based on environment variable.
        Mirrors the logic from job_manager_mcp.py line 123:
        
        Usage:
            # Default to "mcp", can be overridden via SERVER_PROTOCOL env var
            # Or per-service via PROTOCOL_{SERVICE_NAME} env var
        
        Example:
            SERVER_PROTOCOL=api  # All services use API
            PROTOCOL_WECHAT=api  # Only wechat uses API
        """
        import os
        
        # Check per-service override first (e.g., PROTOCOL_WECHAT=api)
        per_service_key = f"PROTOCOL_{service_name.upper()}"
        per_service_protocol = os.getenv(per_service_key)
        if per_service_protocol:
            return per_service_protocol.lower()
        
        # Check global SERVER_PROTOCOL (from job_manager_mcp.py line 123)
        global_protocol = os.getenv("SERVER_PROTOCOL")
        if global_protocol:
            return global_protocol.lower()
        
        # Default to mcp (as per job_manager_mcp.py)
        return "mcp"

    def _dynamic_discover_service(self, service_name: str) -> bool:
        """
        Dynamically discover and load a service that wasn't found in the registry.
        Searches both src/servers and mcp_legacy/servers directories.
        """
        # Clean up service name (remove _mcp/_api suffixes)
        base_name = service_name.replace("_mcp", "").replace("_api", "")
        
        # Search directories
        search_dirs = []
        base_dir = Path(__file__).parent.parent
        src_servers = base_dir / "servers"
        legacy_servers = base_dir / "mcp_legacy" / "servers"
        
        if src_servers.exists():
            search_dirs.append(src_servers)
        if legacy_servers.exists():
            search_dirs.append(legacy_servers)
        
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
                
            # Look for the service directory
            service_dir = search_dir / base_name
            if service_dir.exists() and service_dir.is_dir():
                logger.info(f"[ServiceManager] Found service {base_name} in {service_dir}")
                self._load_service(base_name, service_dir)
                return True
            
            # Also try case-insensitive search
            for item in search_dir.iterdir():
                if item.is_dir() and item.name.lower() == base_name.lower():
                    logger.info(f"[ServiceManager] Found service {base_name} (case-insensitive) in {item}")
                    self._load_service(item.name, item)
                    return True
        
        # Try to discover all services if we haven't discovered any yet
        if len(self.services) == 0:
            logger.info("[ServiceManager] No services discovered yet, running full discovery...")
            self.discover_services()
            return service_name in [cfg.name for cfg in self.services.values()]
        
        return False

    async def get_client(self, service_alias: str) -> BaseProtocolClient:
        """Get or create a client for a service"""
        logger.info(f"[ServiceManager] get_client requested for: {service_alias}")
        
        if service_alias in self.clients:
            logger.info(f"[ServiceManager] Client cache hit for: {service_alias}")
            try:
                 # Check if client connection is actually alive/valid if possible
                 # If it's an MCP client, we might want to ensure it's connected, 
                 # but for now just returning the cached instance.
                 return self.clients[service_alias]
            except Exception as e:
                 logger.warning(f"[ServiceManager] Cached client error: {e}, will recreate")
                 del self.clients[service_alias]

        logger.info(f"[ServiceManager] Cache miss for {service_alias}, resolving config...")
        
        if service_alias not in self.services:
            # Try finding by name without _mcp/_api suffix
            found = False
            for alias, cfg in self.services.items():
                if cfg.name == service_alias:
                    service_alias = alias
                    found = True
                    break
            if not found:
                # Dynamic service discovery - try to find and load the service
                logger.warning(f"[ServiceManager] Service {service_alias} not found, attempting dynamic discovery...")
                if self._dynamic_discover_service(service_alias):
                    # Service was discovered, try to find it again
                    for alias, cfg in self.services.items():
                        if cfg.name == service_alias or alias == service_alias or alias.startswith(f"{service_alias}_"):
                            service_alias = alias
                            found = True
                            logger.info(f"[ServiceManager] Dynamically discovered service: {service_alias}")
                            break
                if not found:
                    logger.error(f"[ServiceManager] Service {service_alias} NOT found in registry")
                    raise ValueError(f"Service {service_alias} not found")
        
        logger.info(f"[ServiceManager] Resolved service alias: {service_alias}")
        config = self.services[service_alias]
        
        # For non-MCP protocols (like API), we manage the process ourselves here.
        # For MCP (stdio), the MCPClientManager starts the process via stdio_client.
        if config.protocol.lower() != "mcp" and config.get("command"):
            logger.info(f"[ServiceManager] Ensuring local process running for non-MCP service: {service_alias}")
            await self._ensure_process_running(service_alias)
        elif config.protocol.lower() == "mcp":
            logger.info(f"Delegating process startup for {service_alias} to MCPClientManager")
            if not config.config.get("name"):
                 # ProtocolClientFactory needs a 'name' key for MCP
                 config.config["name"] = config.name
                 logger.info(f"Added missing 'name' key to {service_alias} config: {config.name}")
            
        import time
        start_time = time.time()
        logger.info(f"Connecting to service client: {service_alias} (protocol: {config.protocol})")
        
        try:
            logger.info(f"[ServiceManager] Creating client instance via factory for {service_alias}")
            client = ProtocolClientFactory.create_client(config.config)
            logger.info(f"[ServiceManager] Client created, calling connect()...")
            await client.connect()
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Successfully connected to {service_alias} in {elapsed:.2f}ms")
            self.clients[service_alias] = client
            return client
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"Failed to connect to {service_alias} after {elapsed:.2f}ms: {e}")
            raise

    async def _ensure_process_running(self, service_alias: str):
        if service_alias in self.processes:
            process = self.processes[service_alias]
            if process.returncode is None:
                return
                
        config = self.services[service_alias]
        command = config.get("command")
        args = config.get("args", [])
        cwd = config.get("cwd")
        
        # Calculate dynamic PYTHONPATH relatively
        src_path = Path(__file__).parent.parent
        servers_path = src_path / "servers"
        
        # Combine paths with OS-specific path separator
        paths = [str(src_path), str(servers_path)]
        existing_pythonpath = os.environ.get("PYTHONPATH", "")
        if existing_pythonpath:
            paths.append(existing_pythonpath)
        new_pythonpath = os.pathsep.join(paths)
        
        import time
        start_time = time.time()
        logger.info(f"Starting process for {service_alias}: command='{command}', args={args}, cwd='{cwd}'")
        
        try:
            process = await asyncio.create_subprocess_exec(
                command,
                *args,
                cwd=cwd,
                env={**os.environ, "PYTHONPATH": new_pythonpath},
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Process {service_alias} started with PID {process.pid} (startup took {elapsed:.2f}ms)")
            self.processes[service_alias] = process
            
            # Start a task to read and log stderr output from the server
            asyncio.create_task(self._log_stderr(service_alias, process))
            
            # Quick check if it crashes immediately
            await asyncio.sleep(0.5)
            if process.returncode is not None:
                # Capture any remaining stderr for immediate reporting
                _, stderr = await process.communicate()
                error_output = stderr.decode().strip() if stderr else "No error output on stderr"
                logger.error(f"Process {service_alias} exited immediately with code {process.returncode}. Error details: {error_output}")
                raise RuntimeError(f"Service {service_alias} failed to start. Return code: {process.returncode}")
                
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"Failed to start process {service_alias} after {elapsed:.2f}ms: {str(e)}")
            raise

    async def _log_stderr(self, service_alias: str, process: asyncio.subprocess.Process):
        """Asynchronously read and log stderr from a service process to capture server-side details"""
        try:
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                
                content = line.decode().strip()
                if content:
                    logger.info(f"[{service_alias}] {content}")
        except Exception as e:
            logger.debug(f"Error reading stderr from {service_alias}: {e}")
        
    async def shutdown(self):
        """Shutdown all clients and processes"""
        for client in self.clients.values():
            await client.close()
        self.clients.clear()
        
        for process in self.processes.values():
            if process.returncode is None:
                process.terminate()
                await process.wait()
        self.processes.clear()

def get_service_manager():
    return ServiceManager()
