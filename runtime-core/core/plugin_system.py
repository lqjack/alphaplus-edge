# core/plugin_system.py
"""
DEPRECATED: This plugin system is deprecated in favor of MCP (Model Context Protocol).

This module is kept for backward compatibility only and will be removed in a future version.
Please migrate to using MCP servers instead.

Migration Guide:
- Old Plugin System -> New MCP Servers
- Plugin.initialize() -> MCP server startup
- Plugin methods -> MCP tools
- PluginManager -> MCPExecutor

See: src/core/mcp_executor.py for the new implementation.
"""

import warnings
import importlib
import inspect
import pkgutil
import logging
from dataclasses import dataclass
from typing import Dict, List, Type, Optional, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Issue deprecation warning when module is imported
warnings.warn(
    "The plugin_system module is deprecated and will be removed in a future version. "
    "Please migrate to MCP (Model Context Protocol) using src/core/mcp_executor.py",
    DeprecationWarning,
    stacklevel=2
)


@dataclass
class PluginMetadata:
    """插件元数据 - DEPRECATED"""
    name: str
    description: str
    version: str
    author: str
    dependencies: List[str]
    entry_point: str
    lazy_load: bool = True


class IPlugin(ABC):
    """插件接口基类 - DEPRECATED"""
    
    @classmethod
    @abstractmethod
    def get_metadata(cls) -> PluginMetadata:
        pass
    
    @abstractmethod
    def initialize(self, plugin_manager: 'PluginManager'):
        pass
    
    @abstractmethod
    def shutdown(self):
        pass


class PluginManager:
    """插件管理器 - DEPRECATED"""
    
    def __init__(self):
        logger.warning("PluginManager is deprecated. Use MCPExecutor instead.")
        self._plugins: Dict[str, Type[IPlugin]] = {}
        self._instances: Dict[str, IPlugin] = {}
        self._metadata: Dict[str, PluginMetadata] = {}
        self._loaded: Dict[str, bool] = {}
        
    def register_plugin(self, plugin_class: Type[IPlugin]):
        # 跳过BaseMonitorPlugin及其子类的注册
        if plugin_class.__name__ == 'BaseMonitorPlugin':
            logger.debug(f"Skipping registration of base plugin: {plugin_class.__name__}")
            return
            
        metadata = plugin_class.get_metadata()
        if metadata.name in self._plugins:
            logger.info(f"Plugin {metadata.name} already registered")
            return
        
        self._plugins[metadata.name] = plugin_class
        self._metadata[metadata.name] = metadata
        self._loaded[metadata.name] = False
        logger.info(f"Registered plugin: {metadata.name}")
        
    def discover_plugins(self, package_path: str):
        package = importlib.import_module(package_path)
        for _, module_name, _ in pkgutil.iter_modules(package.__path__):
            full_module_name = f"{package_path}.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
                for _, cls in inspect.getmembers(module, inspect.isclass):
                    if issubclass(cls, IPlugin) and cls != IPlugin:
                        self.register_plugin(cls)
            except ImportError as e:
                logger.error(f"Failed to load module {module_name}: {e}")
    
    def get_plugin(self, name: str) -> Optional[IPlugin]:
        if name not in self._plugins:
            return None
            
        if not self._loaded[name]:
            self._load_plugin(name)
            
        return self._instances.get(name)
    
    def _load_plugin(self, name: str):
        if name not in self._plugins or self._loaded[name]:
            return
            
        metadata = self._metadata[name]
        
        for dep in metadata.dependencies:
            self._load_plugin(dep)
        
        plugin_class = self._plugins[name]
        plugin_instance = plugin_class()
        plugin_instance.initialize(self)
        
        if hasattr(plugin_instance, 'set_plugin_manager'):
        # 获取方法对象
          set_plugin_manager_method = getattr(plugin_instance, 'set_plugin_manager')
          # 检查是否可调用
          if callable(set_plugin_manager_method):
              # 传递当前插件管理器实例
              set_plugin_manager_method(self)

        self._instances[name] = plugin_instance
        self._loaded[name] = True
        logger.info(f"Loaded plugin: {name}")
    
    def load_all(self):
        for name in self._plugins:
            self._load_plugin(name)
    
    def shutdown(self):
        for name, instance in list(self._instances.items()):
            try:
                instance.shutdown()
                self._loaded[name] = False
                logger.info(f"Shutdown plugin: {name}")
            except Exception as e:
                logger.error(f"Error shutting down plugin {name}: {e}")
        
        self._instances.clear()
    
    def get_plugin_metadata(self, name: str) -> Optional[PluginMetadata]:
        return self._metadata.get(name)
    
    def list_plugins(self) -> List[str]:
        return list(self._plugins.keys())
    
    def is_loaded(self, name: str) -> bool:
        return self._loaded.get(name, False)


class PluginLoader:
    """DEPRECATED: Use MCP server loading instead"""
    
    @staticmethod
    def load_from_entrypoint(entry_point: str) -> Type[IPlugin]:
        logger.warning("PluginLoader is deprecated. Use MCP server configuration instead.")
        module_path, class_name = entry_point.split(":")
        module = importlib.import_module(module_path)
        plugin_class = getattr(module, class_name)
        
        if not issubclass(plugin_class, IPlugin):
            raise TypeError(f"{class_name} is not a valid plugin class")
            
        return plugin_class
    
    @staticmethod
    def load_from_config(config: Dict[str, Any]) -> Type[IPlugin]:
        entry_point = config.get("entry_point")
        if not entry_point:
            raise ValueError("Missing entry_point in plugin config")
            
        return PluginLoader.load_from_entrypoint(entry_point)
