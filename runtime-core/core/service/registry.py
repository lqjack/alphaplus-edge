# -*- coding: utf-8 -*-
"""
Service Registry Module.
Provides service discovery, URL resolution, and alias management.
"""

import logging
from typing import Dict, Optional, Tuple
from core.service_ports import (
    SERVICE_PORTS,
    SERVICE_ALIASES,
    get_port,
    parse_service_alias,
    get_service_list,
)

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """
    Central registry for all services.
    Manages service URLs, aliases, and port resolution.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._service_ports = SERVICE_PORTS
        self._service_aliases = SERVICE_ALIASES
        logger.info("[ServiceRegistry] Initialized")

    def parse_alias(self, alias: str) -> Tuple[str, str]:
        """
        Parse service alias into (service_name, protocol).

        Args:
            alias: Service alias (e.g., "stock_market_mcp", "wechat_api")

        Returns:
            Tuple of (service_name, protocol)
        """
        return parse_service_alias(alias)

    def get_url(self, service_name: str, protocol: str = "api") -> str:
        """
        Get the URL for a service.

        Args:
            service_name: Name of the service
            protocol: Protocol type (mcp, api, http)

        Returns:
            Service URL
        """
        try:
            port = get_port(service_name, protocol)
        except KeyError:
            logger.warning(f"Service {service_name} not found, using fallback port")
            port = 10500 + (hash(service_name) % 100)

        # Determine base URL based on protocol
        if protocol in ("mcp", "stdio"):
            # MCP services don't have HTTP URLs
            return f"stdio://localhost:{port}"
        else:
            return f"http://localhost:{port}"

    def get_service_list(self) -> list:
        """Get list of all registered services."""
        return get_service_list()

    def get_port(self, service_name: str, protocol: str = "api") -> int:
        """Get port for a service."""
        try:
            return get_port(service_name, protocol)
        except KeyError:
            return 10500 + (hash(service_name) % 100)


# Global registry instance
_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> ServiceRegistry:
    """Get the global service registry instance."""
    global _registry
    if _registry is None:
        _registry = ServiceRegistry()
    return _registry
