"""
MCP Dependency Type Definitions

Shared type definitions for MCP server dependency management.
Used by all MCP servers to maintain consistent dependency loading patterns.
"""
from enum import Enum
from typing import Any, Optional


class DependencyStatus(Enum):
    """Dependency loading status"""
    NOT_LOADED = "not_loaded"
    LOADING = "loading"
    LOADED = "loaded"
    FAILED = "failed"


class DependencyInfo:
    """Information about a dependency"""
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.status = DependencyStatus.NOT_LOADED
        self.instance: Optional[Any] = None
        self.error: Optional[Exception] = None

    def set_loaded(self, instance: Any):
        """Mark dependency as loaded"""
        self.status = DependencyStatus.LOADED
        self.instance = instance
        self.error = None

    def set_failed(self, error: Exception):
        """Mark dependency as failed to load"""
        self.status = DependencyStatus.FAILED
        self.instance = None
        self.error = error

    def is_available(self) -> bool:
        """Check if dependency is available"""
        return self.status == DependencyStatus.LOADED and self.instance is not None
