"""
Core Dependency Types

Defines common types and protocols for dependency management across all MCP servers.
"""
from typing import Protocol, Any, Dict, Optional, List


class DependencyInfo:
    """Information about a dependency"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.instance = None
        self.status = "unloaded"
        self.os_specific = False
        self.os_list = []
    
    def set_loaded(self, instance: Any) -> None:
        """Mark dependency as loaded"""
        self.instance = instance
        self.status = "loaded"
    
    def is_available(self) -> bool:
        """Check if dependency is available"""
        return self.instance is not None and self.status == "loaded"


class DependencyManagerProtocol(Protocol):
    """Protocol for dependency managers"""
    
    def get_dependency(self, name: str) -> Optional[Any]:
        """Get a loaded dependency instance"""
        ...
    
    def is_available(self, name: str) -> bool:
        """Check if a dependency is available"""
        ...
    
    def get_available_dependencies(self) -> Dict[str, Any]:
        """Get all available dependencies grouped by category"""
        ...
    
    def initialize_all(self) -> None:
        """Initialize all registered dependencies"""
        ...


# Cross-Platform Automation Dependency Types
CROSS_PLATFORM_AUTOMATION_ENGINE = "cross_platform_automation_engine"
MACOS_ADAPTER = "macos_adapter"
WINDOWS_ADAPTER = "windows_adapter"
ADAPTIVE_ELEMENT_LOCATOR = "adaptive_element_locator"
UNIFIED_ELEMENT_LOCATOR = "unified_element_locator"
LLM_TASK_PLANNER = "llm_task_planner"
INTELLIGENT_EXECUTION_MONITOR = "intelligent_execution_monitor"
STATE_PERSISTENCE_LAYER = "state_persistence_layer"
CONFIG_MANAGER = "config_manager"
WINDOW_MANAGER = "window_manager"
OCR_PROCESSOR = "ocr_processor"
OPENAI_VISION_LOCATOR = "openai_vision_locator"