"""
Core Dependency Manager

Base dependency management system for DataProAI servers.
Provides lazy loading of heavy dependencies to avoid blocking server startup.

Usage:
    from core.deps import DependencyManager, DependencyInfo, DependencyStatus

    class MyServerDeps(DependencyManager):
        def __init__(self):
            super().__init__()
            self._register_dependencies()

        def _register_dependencies(self):
            self.register("llm_client", "LLM client for AI communication")
            self.register("database", "Database connection")

    deps = MyServerDeps()
    llm = deps.get("llm_client")
"""

import sys
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import importlib

logger = logging.getLogger(__name__)


class DependencyStatus(str, Enum):
    """Dependency loading status"""

    NOT_LOADED = "NOT_LOADED"
    LOADING = "LOADING"
    LOADED = "LOADED"
    FAILED = "FAILED"


@dataclass
class DependencyInfo:
    """Information about a registered dependency"""

    name: str
    description: str = ""
    status: DependencyStatus = DependencyStatus.NOT_LOADED
    instance: Any = None
    error: Optional[str] = None
    loader: Optional[Callable] = None  # Function to load the dependency

    # OS-specific support
    os_specific: bool = False
    os_list: List[str] = field(default_factory=list)

    def is_available(self) -> bool:
        """Check if dependency is loaded and available"""
        return self.status == DependencyStatus.LOADED and self.instance is not None

    def set_loaded(self, instance: Any):
        """Mark dependency as loaded"""
        self.instance = instance
        self.status = DependencyStatus.LOADED
        self.error = None

    def set_failed(self, error: str):
        """Mark dependency as failed"""
        self.status = DependencyStatus.FAILED
        self.error = error

    def set_loading(self):
        """Mark dependency as loading"""
        self.status = DependencyStatus.LOADING


class DependencyManager:
    """
    Base dependency manager with lazy loading support.

    Provides:
    - Lazy loading of heavy dependencies
    - OS-specific dependency filtering
    - Status tracking and error handling
    - Simple registration API
    """

    def __init__(self, server_name: str = "unknown"):
        self.server_name = server_name
        self._deps: Dict[str, DependencyInfo] = {}
        self._initialized = False
        self._logger = logging.getLogger(f"deps.{server_name}")

    def register(
        self,
        name: str,
        description: str = "",
        loader: Optional[Callable] = None,
        os_specific: bool = False,
        os_list: Optional[List[str]] = None,
    ) -> DependencyInfo:
        """
        Register a dependency for lazy loading.

        Args:
            name: Unique name for the dependency
            description: Human-readable description
            loader: Optional function to load the dependency
            os_specific: Whether this dependency is OS-specific
            os_list: List of supported OS names

        Returns:
            DependencyInfo object
        """
        dep_info = DependencyInfo(
            name=name,
            description=description,
            loader=loader,
            os_specific=os_specific,
            os_list=os_list or [],
        )
        self._deps[name] = dep_info
        self._logger.debug(f"Registered dependency: {name}")
        return dep_info

    def get(self, name: str, auto_load: bool = True) -> Any:
        """
        Get a dependency instance.

        Args:
            name: Dependency name
            auto_load: If True, auto-load if not yet loaded

        Returns:
            Dependency instance or None
        """
        dep = self._deps.get(name)
        if not dep:
            self._logger.warning(f"Unknown dependency: {name}")
            return None

        if dep.is_available():
            return dep.instance

        if auto_load and dep.loader and dep.status != DependencyStatus.LOADING:
            self._load_dependency(name)

        return dep.instance if dep.is_available() else None

    def _load_dependency(self, name: str) -> bool:
        """
        Load a dependency using its loader function.

        Args:
            name: Dependency name

        Returns:
            True if loaded successfully
        """
        dep = self._deps.get(name)
        if not dep:
            return False

        if dep.is_available():
            return True

        dep.set_loading()

        try:
            if dep.loader:
                instance = dep.loader()
                dep.set_loaded(instance)
                self._logger.info(f"Loaded dependency: {name}")
                return True
            else:
                # No loader - try direct import
                instance = importlib.import_module(name)
                dep.set_loaded(instance)
                self._logger.info(f"Imported dependency: {name}")
                return True
        except Exception as e:
            dep.set_failed(str(e))
            self._logger.error(f"Failed to load {name}: {e}")
            return False

    def is_available(self, name: str) -> bool:
        """Check if a dependency is available"""
        dep = self._deps.get(name)
        return dep.is_available() if dep else False

    def get_status(self, name: str) -> DependencyStatus:
        """Get the loading status of a dependency"""
        dep = self._deps.get(name)
        return dep.status if dep else DependencyStatus.NOT_LOADED

    def initialize_all(self) -> None:
        """
        Initialize all registered dependencies.
        Override in subclass for custom initialization order.
        """
        if self._initialized:
            return

        self._logger.info(f"Initializing dependencies for {self.server_name}...")

        for name in self._deps:
            self._load_dependency(name)

        self._initialized = True
        self._logger.info(f"Dependencies initialized: {self.get_status_summary()}")

    def get_status_summary(self) -> Dict[str, str]:
        """Get summary of all dependency statuses"""
        return {name: dep.status.value for name, dep in self._deps.items()}

    def get_available(self) -> Dict[str, Any]:
        """Get all available (loaded) dependencies"""
        return {
            name: dep.instance for name, dep in self._deps.items() if dep.is_available()
        }

    def get_all_info(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed info about all dependencies"""
        return {
            name: {
                "description": dep.description,
                "status": dep.status.value,
                "available": dep.is_available(),
                "error": dep.error,
                "os_specific": dep.os_specific,
                "os_list": dep.os_list,
            }
            for name, dep in self._deps.items()
        }


def get_dependency_manager():
    """
    Factory function to get the appropriate dependency manager.

    This can be overridden in each server to return their specific manager.
    """
    # Default implementation returns a basic manager
    # Servers should override this
    return DependencyManager("default")
