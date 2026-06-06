"""
Config Manager for Cross-Platform Automation

Handles configuration management including:
- Loading/saving external configuration files
- Managing tunable parameters for timeouts, retry counts, and sensitivity
- Platform-specific settings
- Environment-specific adaptation capabilities
"""

import json
import os
import logging
from typing import Dict, Any, Optional, List
from .interfaces import IConfigManager
from .dependency_types import CONFIG_MANAGER


class ConfigManager(IConfigManager):
    """Configuration management component"""

    def __init__(self, dependency_manager):
        self.dep_manager = dependency_manager
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.config_manager")

        # Configuration storage
        self._config_data: Dict[str, Any] = {}
        self._platform_configs: Dict[str, Dict[str, Any]] = {}
        self._tunable_parameters: Dict[str, Any] = {}

        # Configuration file paths
        self._main_config_path = "config/automation_config.json"
        self._platform_config_dir = "config/platforms"
        self._tunable_params_path = "config/tunable_parameters.json"

        # Load initial configuration
        self._load_initial_configuration()

    def _load_initial_configuration(self):
        """Load initial configuration from files"""
        try:
            # Load main configuration
            self._config_data = self._load_json_file(self._main_config_path) or {}

            # Load platform-specific configurations
            self._platform_configs = self._load_platform_configurations()

            # Load tunable parameters
            self._tunable_parameters = self._load_json_file(self._tunable_params_path) or {}

            self.logger.info("Initial configuration loaded successfully")

        except Exception as e:
            self.logger.warning(f"Failed to load initial configuration: {e}")
            # Set defaults
            self._config_data = {}
            self._platform_configs = {}
            self._tunable_parameters = {}

    def _load_json_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Load JSON file with error handling"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                self.logger.debug(f"Configuration file not found: {file_path}")
                return None
        except Exception as e:
            self.logger.error(f"Failed to load JSON file {file_path}: {e}")
            return None

    def _save_json_file(self, file_path: str, data: Dict[str, Any]) -> bool:
        """Save JSON file with error handling"""
        try:
            # Ensure directory exists
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.logger.debug(f"Saved configuration to {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save JSON file {file_path}: {e}")
            return False

    def _load_platform_configurations(self) -> Dict[str, Dict[str, Any]]:
        """Load all platform-specific configurations"""
        platform_configs = {}

        try:
            if os.path.exists(self._platform_config_dir):
                for filename in os.listdir(self._platform_config_dir):
                    if filename.endswith('.json'):
                        platform_name = filename[:-5]  # Remove .json extension
                        file_path = os.path.join(self._platform_config_dir, filename)
                        config_data = self._load_json_file(file_path)
                        if config_data:
                            platform_configs[platform_name] = config_data
                            self.logger.debug(f"Loaded platform config for {platform_name}")
            else:
                self.logger.debug(f"Platform config directory not found: {self._platform_config_dir}")
        except Exception as e:
            self.logger.error(f"Failed to load platform configurations: {e}")

        return platform_configs

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from specified path"""
        config_data = self._load_json_file(config_path)
        return config_data if config_data is not None else {}

    def save_config(self, config_path: str, config_data: Dict[str, Any]) -> bool:
        """Save configuration to specified path"""
        return self._save_json_file(config_path, config_data)

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key (supports dot notation)"""
        try:
            # Handle dot notation (e.g., "platform.macos.timeout")
            keys = key.split('.')
            value = self._config_data

            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default

            return value
        except Exception as e:
            self.logger.warning(f"Failed to get config value for key '{key}': {e}")
            return default

    def set_config_value(self, key: str, value: Any) -> bool:
        """Set a configuration value by key (supports dot notation)"""
        try:
            # Handle dot notation (e.g., "platform.macos.timeout")
            keys = key.split('.')
            config = self._config_data

            # Navigate to the parent of the target key
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]

            # Set the value
            config[keys[-1]] = value

            # Save to file
            self._save_json_file(self._main_config_path, self._config_data)

            return True
        except Exception as e:
            self.logger.error(f"Failed to set config value for key '{key}': {e}")
            return False

    def get_platform_config(self, platform: str) -> Dict[str, Any]:
        """Get configuration for a specific platform"""
        return self._platform_configs.get(platform.lower(), {})

    def update_platform_config(self, platform: str, config_data: Dict[str, Any]) -> bool:
        """Update configuration for a specific platform"""
        try:
            platform = platform.lower()
            self._platform_configs[platform] = config_data

            # Save to file
            platform_file = os.path.join(self._platform_config_dir, f"{platform}.json")
            return self._save_json_file(platform_file, config_data)
        except Exception as e:
            self.logger.error(f"Failed to update platform config for '{platform}': {e}")
            return False

    def get_tunable_parameter(self, param_name: str, default: Any = None) -> Any:
        """Get a tunable parameter value"""
        return self._tunable_parameters.get(param_name, default)

    def set_tunable_parameter(self, param_name: str, value: Any) -> bool:
        """Set a tunable parameter value"""
        try:
            self._tunable_parameters[param_name] = value

            # Save to file
            self._save_json_file(self._tunable_params_path, self._tunable_parameters)

            return True
        except Exception as e:
            self.logger.error(f"Failed to set tunable parameter '{param_name}': {e}")
            return False

    def reload_config(self) -> bool:
        """Reload configuration from files"""
        try:
            self._load_initial_configuration()
            self.logger.info("Configuration reloaded successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {e}")
            return False

    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration data"""
        return {
            "main_config": self._config_data.copy(),
            "platform_configs": {k: v.copy() for k, v in self._platform_configs.items()},
            "tunable_parameters": self._tunable_parameters.copy()
        }