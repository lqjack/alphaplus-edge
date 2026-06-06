"""
Dependency Manager for Xiaohongshu Server

Manages lazy loading of Xiaohongshu APIs and database dependencies.
"""
import sys
import os
from typing import Optional

# Import shared types from core
from core.mcp_dep_types import DependencyInfo, DependencyStatus


class XiaohongshuDependencyManager:
    """Manages lazy loading of Xiaohongshu-specific dependencies"""

    def __init__(self):
        self._deps = {}
        self._lock = None  # We'll add async import if needed
        self._initialized = False

    def register_dependency(self, name: str, description: str = "") -> None:
        """Register a dependency for lazy loading"""
        self._deps[name] = DependencyInfo(name, description)

    def get_dependency(self, name: str):
        """Get a loaded dependency instance"""
        dep = self._deps.get(name)
        return dep.instance if dep and dep.is_available() else None

    def is_available(self, name: str) -> bool:
        """Check if a dependency is available"""
        dep = self._deps.get(name)
        return dep.is_available() if dep else False

    def initialize_all(self) -> None:
        """Initialize all registered dependencies"""
        if self._initialized:
            return

        print("INFO: Initializing Xiaohongshu MCP server dependencies...", file=sys.stderr)

        # Initialize dependencies in order
        self._init_xiaohongshu_apis()
        self._init_database_dependencies()
        self._init_config_dependencies()

        self._initialized = True
        print("INFO: Xiaohongshu dependencies initialized successfully", file=sys.stderr)

    def _init_xiaohongshu_apis(self) -> None:
        """Initialize Xiaohongshu-specific dependencies"""
        try:
            # Register Xiaohongshu API dependencies
            self.register_dependency("xiaohongshu_api", "Xiaohongshu XHS downloader class")
            self.register_dependency("json_parser", "JSON parsing utilities")

            # Try to import Xiaohongshu downloader implementation
            try:
                from source import XHS

                self._deps["xiaohongshu_api"].set_loaded(XHS)
            except ImportError:
                print("WARNING: Xiaohongshu API client not available", file=sys.stderr)
                self._deps["xiaohongshu_api"].set_loaded(None)

            # Import JSON utilities
            try:
                import json
                self._deps["json_parser"].set_loaded(json)
            except ImportError:
                print("WARNING: JSON parser not available", file=sys.stderr)
                self._deps["json_parser"].set_loaded(None)

        except Exception as e:
            print(f"WARNING: Xiaohongshu API dependencies loading failed: {e}", file=sys.stderr)

    def _init_database_dependencies(self) -> None:
        """Initialize database dependencies"""
        try:
            # Register database dependencies
            self.register_dependency("account_adapter", "Account database adapter")
            self.register_dependency("article_adapter", "Article database adapter")
            self.register_dependency("database_adapter", "Database adapter")
            self.register_dependency("is_mongodb", "MongoDB detection")
            self.register_dependency("sql_models", "SQLAlchemy models")

            # Try to import database adapters
            try:
                from api.rest.mongodb_adapter import account_adapter, article_adapter, DatabaseAdapter
                self._deps["account_adapter"].set_loaded(account_adapter)
                self._deps["article_adapter"].set_loaded(article_adapter)
                self._deps["database_adapter"].set_loaded(DatabaseAdapter)

                # Check if MongoDB is available
                if hasattr(DatabaseAdapter, 'is_mongodb'):
                    self._deps["is_mongodb"].set_loaded(DatabaseAdapter.is_mongodb)
                else:
                    self._deps["is_mongodb"].set_loaded(lambda: False)
            except ImportError:
                print("WARNING: MongoDB adapters not available", file=sys.stderr)
                self._deps["account_adapter"].set_loaded(None)
                self._deps["article_adapter"].set_loaded(None)
                self._deps["database_adapter"].set_loaded(None)
                self._deps["is_mongodb"].set_loaded(lambda: False)

            # SQLAlchemy models are only required when DB_TYPE is not MongoDB.
            if os.getenv("DB_TYPE", "mongo").lower() == "mongo":
                print("INFO: SQL models skipped because DB_TYPE=mongo", file=sys.stderr)
                self._deps["sql_models"].set_loaded(None)
            else:
                try:
                    from storage import models
                    self._deps["sql_models"].set_loaded(models)
                except ImportError:
                    print("WARNING: SQL models not available", file=sys.stderr)
                    self._deps["sql_models"].set_loaded(None)

        except Exception as e:
            print(f"WARNING: Database dependencies loading failed: {e}", file=sys.stderr)

    def _init_config_dependencies(self) -> None:
        """Initialize configuration dependencies"""
        try:
            # Register config dependencies
            self.register_dependency("logger", "Logging system")

            # Try to import logger
            try:
                from core.logger import setup_logger
                logger_instance = setup_logger("mcp-server-xiaohongshu", log_to_console=False)
                self._deps["logger"].set_loaded(logger_instance)
            except ImportError:
                # Fallback to basic logging
                import logging
                logger_instance = logging.getLogger("mcp-server-xiaohongshu")
                logger_instance.setLevel(logging.INFO)
                self._deps["logger"].set_loaded(logger_instance)

        except Exception as e:
            print(f"WARNING: Config dependencies loading failed: {e}", file=sys.stderr)


# Global dependency manager instance
_xiaohongshu_dependency_manager = None


def get_dependency_manager() -> XiaohongshuDependencyManager:
    """Get global Xiaohongshu dependency manager instance"""
    global _xiaohongshu_dependency_manager
    if _xiaohongshu_dependency_manager is None:
        _xiaohongshu_dependency_manager = XiaohongshuDependencyManager()
    return _xiaohongshu_dependency_manager
