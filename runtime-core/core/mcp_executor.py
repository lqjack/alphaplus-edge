# -*- coding: utf-8 -*-
"""
Service Executor
Provides a thread-safe, low-latency mechanism for calling services (MCP or API).
Now includes MCP Gateway integration for auto-start and unified management.
"""

import asyncio
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from core.gateway_policy import dev_allow_direct_server
from core.mcp_gateway import MCPGateway, get_mcp_gateway
from core.service_manager import get_service_manager

logger = logging.getLogger(__name__)

class ServiceExecutor:
    """
    A singleton class that manages a background thread for running all service communications.
    This ensures that all service calls are thread-safe and benefit from persistent
    connections without re-creating event loops for each call.
    
    Now integrates with MCP Gateway for:
    - Auto-start of services when called
    - Unified service registry and status tracking
    - Load balancing for multiple instances
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            if not cls._instance:
                cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, use_gateway: bool = True):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._service_manager = get_service_manager()
        self._loop = None
        self._thread = None
        self._runtime_lock = threading.RLock()
        self._initialized = True

        # Initialize MCP Gateway
        self._use_gateway = use_gateway
        if use_gateway:
            self._gateway = get_mcp_gateway(self._service_manager)
            logger.info("[ServiceExecutor] MCP Gateway integration enabled")
        else:
            self._gateway = None

    @property
    def gateway(self) -> MCPGateway:
        """Get the MCP Gateway instance"""
        return self._gateway

    def _thread_target(self):
        """Target for the background thread, runs the asyncio event loop."""
        logger.info("ServiceExecutor background thread started.")
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
        logger.info("ServiceExecutor background thread event loop stopped.")

    def start(self):
        """Starts the background thread and event loop."""
        with self._runtime_lock:
            if self._thread is not None and self._thread.is_alive():
                logger.warning("ServiceExecutor already running.")
                return

            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._thread_target, name="ServiceExecutorThread")
            self._thread.daemon = True
            self._thread.start()

            # Discover services
            self._service_manager.discover_services()

            # Register services with gateway if enabled
            if self._use_gateway and self._gateway:
                self._register_services_with_gateway()

    def _register_services_with_gateway(self):
        """Register discovered services with the gateway for tracking"""
        if not self._gateway:
            return
        
        for alias, config in self._service_manager.services.items():
            try:
                # Parse service name and protocol
                if alias.endswith("_mcp"):
                    service_name = alias[:-4]
                    protocol = "mcp"
                elif alias.endswith("_api"):
                    service_name = alias[:-4]
                    protocol = "api"
                else:
                    service_name = alias
                    protocol = config.protocol

                # Register service pool
                self._gateway.registry.register_service(
                    service_name=service_name,
                    protocol=protocol
                )
            except Exception as e:
                logger.debug(f"[ServiceExecutor] Could not register {alias} with gateway: {e}")

    def shutdown(self):
        """Stops the event loop and joins the background thread."""
        with self._runtime_lock:
            if self._loop and self._loop.is_running():
                logger.info("Shutting down ServiceExecutor...")

                # Shutdown the service manager itself
                future = asyncio.run_coroutine_threadsafe(self._service_manager.shutdown(), self._loop)
                try:
                    future.result(timeout=10)
                except:
                    pass

                self._loop.call_soon_threadsafe(self._loop.stop)
                self._thread.join(timeout=5)
                self._loop.close()
                logger.info("ServiceExecutor shut down successfully.")

    @staticmethod
    def _is_loop_executor_shutdown_error(exc: Exception) -> bool:
        if not isinstance(exc, RuntimeError):
            return False
        message = str(exc).lower()
        return (
            "cannot schedule new futures after shutdown" in message
            or "cannot schedule new futures after interpreter shutdown" in message
        )

    def _restart_background_loop(self, reason: Exception | str) -> None:
        with self._runtime_lock:
            logger.warning(f"[ServiceExecutor] Restarting background loop after failure: {reason}")
            old_loop = self._loop
            old_thread = self._thread
            self._loop = None
            self._thread = None

            if old_loop is not None:
                try:
                    if old_loop.is_running():
                        old_loop.call_soon_threadsafe(old_loop.stop)
                except Exception as exc:
                    logger.debug(f"[ServiceExecutor] Failed to stop old loop cleanly: {exc}")

            if old_thread is not None and old_thread.is_alive():
                old_thread.join(timeout=5)

            if old_loop is not None:
                try:
                    if not old_loop.is_closed():
                        old_loop.close()
                except Exception as exc:
                    logger.debug(f"[ServiceExecutor] Failed to close old loop cleanly: {exc}")

            self.start()
            time.sleep(0.1)
    
    def submit_call(self, service_alias, function_name, arguments, timeout=None, use_gateway: bool = None):
        """
        Submits a call to be executed on the background event loop.

        Args:
            service_alias (str): The alias of the service (e.g., 'wechat_mcp' or 'wechat_api').
            function_name (str): The name of the function/tool to call.
            arguments (Dict[str, Any]): The arguments for the call.
            timeout (int, optional): Timeout in seconds.
            use_gateway (bool, optional): Force gateway usage. Defaults to self._use_gateway.

        Returns:
            Any: The result from the call.
        """
        # Determine if we should use gateway
        if use_gateway is None:
            use_gateway = self._use_gateway and self._gateway is not None
        elif not use_gateway and not dev_allow_direct_server():
            logger.warning(
                "[Executor] Direct call blocked for %s.%s; routing via gateway "
                "(set DEV_ALLOW_DIRECT_SERVER=1 to override)",
                service_alias,
                function_name,
            )
            use_gateway = bool(self._gateway)
            if not use_gateway and self._use_gateway:
                self._gateway = get_mcp_gateway(self._service_manager)
                use_gateway = self._gateway is not None
        
        logger.info(f"[Executor] submit_call invoked for {service_alias}.{function_name} with timeout={timeout}, use_gateway={use_gateway}")
        
        if not self._loop or not self._thread or not self._thread.is_alive():
            # Double check if loop is running to avoid race conditions
            if self._loop and self._loop.is_running():
                 logger.debug("Loop is running but thread variable seems stale. Re-attaching if possible.")
            else:
                 self.start()
                 # Wait briefly for the thread and loop to be fully active
                 time.sleep(0.1)

        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Use gateway if enabled
                if use_gateway:
                    async def _do_call_via_gateway():
                        return await self._call_via_gateway(service_alias, function_name, arguments, timeout)
                    
                    future = asyncio.run_coroutine_threadsafe(_do_call_via_gateway(), self._loop)
                else:
                    # Original implementation
                    async def _do_call():
                        logger.info(f"[Executor] Starting _do_call for {service_alias}.{function_name}")
                        try:
                            client = await self._service_manager.get_client(service_alias)
                            logger.info(f"[Executor] Got client for {service_alias}, calling tool...")
                            result = await client.call(function_name, arguments)
                            logger.info(f"[Executor] Call {service_alias}.{function_name} completed.")
                            return result
                        except Exception as e:
                            logger.error(f"[Executor] Error in _do_call for {service_alias}: {e}")
                            raise

                    future = asyncio.run_coroutine_threadsafe(_do_call(), self._loop)

                # Timeout logic
                if timeout is None:
                    if 'batch' in function_name.lower() or 'sync' in function_name.lower():
                        timeout = 300
                    else:
                        timeout = 60
                
                logger.info(f"[Executor] Waiting for result from {service_alias}.{function_name} (timeout={timeout}s)...")
                
                if not self._thread.is_alive():
                     logger.error("[Executor] Background thread is dead! Restarting...")
                     self.start()
                     # Re-submit
                     if use_gateway:
                         future = asyncio.run_coroutine_threadsafe(_do_call_via_gateway(), self._loop)
                     else:
                         future = asyncio.run_coroutine_threadsafe(_do_call(), self._loop)

                try:
                    result = future.result(timeout=timeout)
                    
                    # Specialized logging for AI calls to track "completeness"
                    if "ai" in service_alias.lower() or "chat_completion" in function_name:
                        logger.info(f"[Executor] AI Call Result (truncated): {str(result)[:500]}...")
                        # If result has content, log the text part specifically
                        if hasattr(result, 'content'):
                            logger.debug(f"[Executor] AI Response Content: {result.content}")
                    
                    logger.info(f"[Executor] Successfully received result for {service_alias}.{function_name}")
                    return result
                except TimeoutError:
                    logger.error(f"[Executor] Timeout waiting for {service_alias}.{function_name} after {timeout}s")
                    raise

            except TimeoutError:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    raise

            except Exception as e:
                if self._is_loop_executor_shutdown_error(e) and attempt < max_retries - 1:
                    self._restart_background_loop(e)
                    continue
                logger.error(f"Service call failed: {e}")
                raise

    async def _call_via_gateway(self, service_alias: str, function_name: str, 
                               arguments: Dict[str, Any], timeout: int) -> Any:
        """Make a call through the MCP Gateway"""
        # Parse service name and protocol from alias
        if service_alias.endswith("_mcp"):
            service_name = service_alias[:-4]
            protocol = "mcp"
        elif service_alias.endswith("_api"):
            service_name = service_alias[:-4]
            protocol = "api"
        else:
            service_name = service_alias
            protocol = "mcp"
        
        logger.info(f"[Executor] Calling via gateway: {service_name}.{function_name}")
        
        try:
            # Use gateway's call method which handles auto-start
            gateway_alias = service_alias if service_alias.endswith(("_mcp", "_api")) else f"{service_name}_{protocol}"
            result = await self._gateway.call(gateway_alias, function_name, arguments)
            logger.info(f"[Executor] Gateway call completed for {service_alias}.{function_name}")
            return result
        except Exception as e:
            logger.error(f"[Executor] Gateway call failed: {e}")
            # Fallback to direct service manager call
            logger.info("[Executor] Falling back to direct service manager call")
            client = await self._service_manager.get_client(service_alias)
            return await client.call(function_name, arguments)

    # === Gateway-specific methods ===

    def list_services(self) -> List[Dict]:
        """List all registered services with their status (via gateway)"""
        if self._gateway:
            return self._gateway.list_services()
        return []

    def get_service_status(self, service_name: str, protocol: str = "mcp") -> Dict:
        """Get status of a specific service (via gateway)"""
        if self._gateway:
            return self._gateway.get_service_status(service_name, protocol)
        return {"status": "gateway_disabled"}

    def start_service(self, service_name: str, protocol: str = "mcp") -> Optional[str]:
        """Manually start a service instance"""
        if not self._gateway:
            return None
        
        if not self._loop or not self._thread or not self._thread.is_alive():
            self.start()
            time.sleep(0.5)
        
        async def _start():
            return await self._gateway.start_service_instance(service_name, protocol)
        
        future = asyncio.run_coroutine_threadsafe(_start(), self._loop)
        try:
            return future.result(timeout=30)
        except Exception as e:
            logger.error(f"[Executor] Failed to start service {service_name}: {e}")
            return None

    def stop_service(self, instance_id: str) -> bool:
        """Manually stop a service instance"""
        if not self._gateway:
            return False
        
        if not self._loop or not self._thread or not self._thread.is_alive():
            return False
        
        async def _stop():
            return await self._gateway.stop_service_instance(instance_id)
        
        future = asyncio.run_coroutine_threadsafe(_stop(), self._loop)
        try:
            return future.result(timeout=30)
        except Exception as e:
            logger.error(f"[Executor] Failed to stop instance {instance_id}: {e}")
            return False

    def enable_gateway(self, enabled: bool = True):
        """Enable or disable gateway usage"""
        self._use_gateway = enabled
        if self._gateway:
            self._gateway.enable_auto_start(enabled)
        logger.info(f"[ServiceExecutor] Gateway {'enabled' if enabled else 'disabled'}")

# Compatibility Alias
MCPExecutor = ServiceExecutor

_executor_instance = None

def get_service_executor():
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = ServiceExecutor()
    return _executor_instance

def get_mcp_executor():
    """Compatibility wrapper"""
    return get_service_executor()
